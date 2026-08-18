import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_family_membership
from app.database import get_db
from app.models import Family, FamilyMember, FamilyStudent, PickupAuthorization, Student, User
from app.schemas import (
    AcceptInvitationIn,
    AuthorizationIn,
    AuthorizationOut,
    CreateFamilyIn,
    FamilyMemberOut,
    FamilyOut,
    FamilyStudentOut,
    FamilyStudentWithStudentOut,
    InviteMemberIn,
    InvitationOut,
    LinkStudentIn,
)
from app.services import family_service

router = APIRouter(prefix="/families", tags=["families"])


@router.post("", response_model=FamilyMemberOut)
async def create_family(
    payload: CreateFamilyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await family_service.create_family(db, user=user, school_id=payload.school_id, name=payload.name)


@router.get("/{family_id}", response_model=FamilyOut)
async def get_family(
    family_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_family_membership(family_id, user, db)
    family = await db.get(Family, family_id)
    if family is None or family.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Familia no encontrada")
    members = (
        (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.family_id == family_id,
                    FamilyMember.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    return FamilyOut(
        id=family.id,
        school_id=family.school_id,
        name=family.name,
        status=family.status,
        members=[FamilyMemberOut.model_validate(m) for m in members],
    )


@router.get("/{family_id}/students", response_model=list[FamilyStudentWithStudentOut])
async def list_family_students(
    family_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_family_membership(family_id, user, db)
    rows = (
        await db.execute(
            select(FamilyStudent, Student)
            .join(Student, Student.id == FamilyStudent.student_id)
            .where(FamilyStudent.family_id == family_id)
        )
    ).all()
    return [
        FamilyStudentWithStudentOut(
            id=fs.id,
            family_id=fs.family_id,
            student_id=fs.student_id,
            relationship_type=fs.relationship_type,
            status=fs.status,
            student_code=student.student_code,
            first_name=student.first_name,
            last_name=student.last_name,
        )
        for fs, student in rows
    ]


@router.get("/{family_id}/authorizations", response_model=list[AuthorizationOut])
async def list_family_authorizations(
    family_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_family_membership(family_id, user, db)
    rows = (
        await db.execute(
            select(PickupAuthorization)
            .join(FamilyMember, FamilyMember.id == PickupAuthorization.family_member_id)
            .where(
                FamilyMember.family_id == family_id,
                PickupAuthorization.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    return rows


@router.post("/{family_id}/invitations", response_model=InvitationOut)
async def create_invitation(
    family_id: uuid.UUID,
    payload: InviteMemberIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inviter = await require_family_membership(family_id, user, db, allowed_family_roles={"OWNER", "ADMIN"})
    invitation, raw_token = await family_service.invite_member(
        db,
        inviter=inviter,
        email=payload.email,
        phone=payload.phone,
        relationship=payload.relationship,
        family_role=payload.family_role,
    )
    # El MVP no envía email/SMS: el token se devuelve aquí para que el
    # OWNER/ADMIN lo comparta manualmente con la persona invitada.
    return InvitationOut(
        id=invitation.id,
        expires_at=invitation.expires_at,
        status=invitation.status,
        token=raw_token,
    )


@router.post("/invitations/accept", response_model=FamilyMemberOut)
async def accept_invitation(
    payload: AcceptInvitationIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await family_service.accept_invitation(db, user=user, token=payload.token)


@router.post("/{family_id}/students/link", response_model=FamilyStudentOut)
async def link_student(
    family_id: uuid.UUID,
    payload: LinkStudentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    requester = await require_family_membership(family_id, user, db, allowed_family_roles={"OWNER", "ADMIN"})
    return await family_service.request_student_link(
        db,
        requester=requester,
        student_code=payload.student_code,
        relationship_type=payload.relationship_type,
    )


@router.post("/{family_id}/authorizations", response_model=AuthorizationOut)
async def set_authorization(
    family_id: uuid.UUID,
    payload: AuthorizationIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_family_membership(family_id, user, db, allowed_family_roles={"OWNER", "ADMIN"})
    return await family_service.set_pickup_authorization(
        db,
        actor=user,
        family_id=family_id,
        family_member_id=payload.family_member_id,
        student_id=payload.student_id,
        authorized=payload.authorized,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
