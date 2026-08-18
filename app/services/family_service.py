import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Family,
    FamilyInvitation,
    FamilyMember,
    FamilyStudent,
    PickupAuthorization,
    School,
    Student,
    User,
)

INVITATION_TTL_HOURS = 72


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_family(db: AsyncSession, *, user: User, school_id: uuid.UUID, name: str) -> FamilyMember:
    school = await db.get(School, school_id)
    if school is None or school.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Colegio inválido")

    family = Family(school_id=school_id, name=name)
    db.add(family)
    await db.flush()

    owner = FamilyMember(
        family_id=family.id,
        user_id=user.id,
        relationship_label="Titular",
        family_role="OWNER",
        status="ACTIVE",
    )
    db.add(owner)
    await db.commit()
    await db.refresh(owner)
    return owner


async def invite_member(
    db: AsyncSession,
    *,
    inviter: FamilyMember,
    email: str | None,
    phone: str | None,
    relationship: str,
    family_role: str,
) -> tuple[FamilyInvitation, str]:
    if family_role not in ("OWNER", "ADMIN", "MEMBER"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol familiar inválido")

    raw_token = secrets.token_urlsafe(32)
    invitation = FamilyInvitation(
        family_id=inviter.family_id,
        invited_by_member_id=inviter.id,
        email=email,
        phone=phone,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=INVITATION_TTL_HOURS),
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    # El token en claro se entrega una sola vez aquí; el envío por email/SMS
    # queda fuera del alcance del MVP (ver backend/README.md).
    return invitation, raw_token


async def accept_invitation(db: AsyncSession, *, user: User, token: str) -> FamilyMember:
    token_hash = _hash_token(token)
    stmt = select(FamilyInvitation).where(FamilyInvitation.token_hash == token_hash)
    result = await db.execute(stmt)
    invitation = result.scalar_one_or_none()

    if invitation is None or invitation.status != "PENDING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación inválida")
    if invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = "EXPIRED"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación expirada")

    existing = await db.execute(
        select(FamilyMember).where(
            FamilyMember.family_id == invitation.family_id,
            FamilyMember.user_id == user.id,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya perteneces a esta familia")

    member = FamilyMember(
        family_id=invitation.family_id,
        user_id=user.id,
        relationship_label="Invitado",
        family_role="MEMBER",
        status="ACTIVE",
    )
    db.add(member)

    invitation.status = "ACCEPTED"
    invitation.accepted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(member)
    return member


async def request_student_link(
    db: AsyncSession,
    *,
    requester: FamilyMember,
    student_code: str,
    relationship_type: str,
) -> FamilyStudent:
    family = await db.get(Family, requester.family_id)
    stmt = select(Student).where(
        Student.school_id == family.school_id,
        Student.student_code == student_code,
        Student.status == "ACTIVE",
    )
    result = await db.execute(stmt)
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado en el colegio")

    existing = await db.execute(
        select(FamilyStudent).where(
            FamilyStudent.family_id == family.id,
            FamilyStudent.student_id == student.id,
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un vínculo con este estudiante")

    link = FamilyStudent(
        family_id=family.id,
        student_id=student.id,
        relationship_type=relationship_type,
        status="PENDING",
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def verify_student_link(
    db: AsyncSession, *, admin_user: User, family_student_id: uuid.UUID, approve: bool
) -> FamilyStudent:
    link = await db.get(FamilyStudent, family_student_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vínculo no encontrado")
    if link.status != "PENDING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El vínculo ya fue revisado")

    link.status = "VERIFIED" if approve else "REJECTED"
    link.verified_by_user_id = admin_user.id
    link.verified_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(link)
    return link


async def set_pickup_authorization(
    db: AsyncSession,
    *,
    actor: User,
    family_id: uuid.UUID,
    family_member_id: uuid.UUID,
    student_id: uuid.UUID,
    authorized: bool,
    start_date,
    end_date,
) -> PickupAuthorization:
    collector = await db.get(FamilyMember, family_member_id)
    if collector is None or collector.family_id != family_id or collector.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Miembro familiar inválido")

    link = await db.execute(
        select(FamilyStudent).where(
            FamilyStudent.family_id == family_id,
            FamilyStudent.student_id == student_id,
            FamilyStudent.status == "VERIFIED",
        )
    )
    if link.scalars().first() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El colegio aún no ha verificado el vínculo de esta familia con el estudiante",
        )

    existing = await db.execute(
        select(PickupAuthorization).where(
            PickupAuthorization.family_member_id == family_member_id,
            PickupAuthorization.student_id == student_id,
            PickupAuthorization.deleted_at.is_(None),
        )
    )
    auth = existing.scalars().first()
    if auth is None:
        auth = PickupAuthorization(
            family_member_id=family_member_id,
            student_id=student_id,
            authorized=authorized,
            start_date=start_date,
            end_date=end_date,
            status="ACTIVE" if authorized else "REVOKED",
            created_by_user_id=actor.id,
        )
        db.add(auth)
    else:
        auth.authorized = authorized
        auth.start_date = start_date
        auth.end_date = end_date
        auth.status = "ACTIVE" if authorized else "REVOKED"
        auth.updated_by_user_id = actor.id

    await db.commit()
    await db.refresh(auth)
    return auth
