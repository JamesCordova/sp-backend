import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    FamilyMember,
    FamilyStudent,
    PickupAuthorization,
    PickupDelivery,
    PickupRequest,
    PickupSession,
    Student,
    StudentEnrollment,
    TeacherClassroom,
    User,
)


async def _log(
    db: AsyncSession,
    *,
    school_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    new_values: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            school_id=school_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            new_values=new_values,
        )
    )


async def _find_verified_family_member_for_student(
    db: AsyncSession, user: User, student_id: uuid.UUID
) -> FamilyMember:
    """Familiar activo del usuario actual, cuya familia tiene un vínculo VERIFIED con el estudiante."""
    stmt = (
        select(FamilyMember)
        .join(FamilyStudent, FamilyStudent.family_id == FamilyMember.family_id)
        .where(
            FamilyMember.user_id == user.id,
            FamilyMember.status == "ACTIVE",
            FamilyMember.deleted_at.is_(None),
            FamilyStudent.student_id == student_id,
            FamilyStudent.status == "VERIFIED",
        )
    )
    result = await db.execute(stmt)
    member = result.scalars().first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes un vínculo familiar verificado con este estudiante",
        )
    return member


async def _has_active_authorization(
    db: AsyncSession, family_member_id: uuid.UUID, student_id: uuid.UUID
) -> bool:
    today = datetime.now(timezone.utc).date()
    stmt = select(PickupAuthorization).where(
        PickupAuthorization.family_member_id == family_member_id,
        PickupAuthorization.student_id == student_id,
        PickupAuthorization.authorized.is_(True),
        PickupAuthorization.status == "ACTIVE",
        PickupAuthorization.deleted_at.is_(None),
        (PickupAuthorization.start_date.is_(None)) | (PickupAuthorization.start_date <= today),
        (PickupAuthorization.end_date.is_(None)) | (PickupAuthorization.end_date >= today),
    )
    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def create_pickup_request(
    db: AsyncSession,
    *,
    user: User,
    pickup_session_id: uuid.UUID,
    student_id: uuid.UUID,
    intended_collector_member_id: uuid.UUID,
) -> PickupRequest:
    session_obj = await db.get(PickupSession, pickup_session_id)
    if session_obj is None or session_obj.status != "OPEN":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La jornada de recojo no está abierta")

    student = await db.get(Student, student_id)
    if student is None or student.status != "ACTIVE" or student.school_id != session_obj.school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estudiante inválido para este colegio")

    requester_member = await _find_verified_family_member_for_student(db, user, student_id)

    collector = await db.get(FamilyMember, intended_collector_member_id)
    if collector is None or collector.family_id != requester_member.family_id or collector.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La persona que recogerá debe ser un miembro activo de la misma familia",
        )

    if not await _has_active_authorization(db, collector.id, student_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esa persona no está autorizada para recoger a este estudiante",
        )

    existing = await db.execute(
        select(PickupRequest).where(
            PickupRequest.pickup_session_id == pickup_session_id,
            PickupRequest.student_id == student_id,
            PickupRequest.status.notin_(["CANCELLED", "REJECTED", "COMPLETED"]),
        )
    )
    if existing.scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una solicitud activa para hoy")

    max_turn = await db.execute(
        select(func.max(PickupRequest.turn_number)).where(
            PickupRequest.pickup_session_id == pickup_session_id
        )
    )
    next_turn = (max_turn.scalar() or 0) + 1

    request_obj = PickupRequest(
        pickup_session_id=pickup_session_id,
        student_id=student_id,
        requested_by_member_id=requester_member.id,
        intended_collector_member_id=collector.id,
        turn_number=next_turn,
        status="QUEUED",
    )
    db.add(request_obj)
    await db.flush()

    await _log(
        db,
        school_id=session_obj.school_id,
        user_id=user.id,
        action="PICKUP_REQUEST_CREATED",
        entity_type="pickup_requests",
        entity_id=request_obj.id,
        new_values={"turn_number": next_turn, "student_id": str(student_id)},
    )
    await db.commit()
    await db.refresh(request_obj)
    return request_obj


async def _classroom_for_student(db: AsyncSession, student_id: uuid.UUID) -> uuid.UUID:
    stmt = (
        select(StudentEnrollment.classroom_id)
        .where(StudentEnrollment.student_id == student_id, StudentEnrollment.status == "ACTIVE")
        .order_by(StudentEnrollment.start_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    classroom_id = result.scalar_one_or_none()
    if classroom_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El estudiante no tiene aula asignada")
    return classroom_id


async def _require_teacher_for_request(db: AsyncSession, user: User, request_obj: PickupRequest) -> None:
    classroom_id = await _classroom_for_student(db, request_obj.student_id)
    stmt = select(TeacherClassroom).where(
        TeacherClassroom.classroom_id == classroom_id,
        TeacherClassroom.teacher_user_id == user.id,
        TeacherClassroom.status == "ACTIVE",
    )
    result = await db.execute(stmt)
    if result.scalars().first() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes asignada el aula de este estudiante")


async def call_pickup_request(db: AsyncSession, *, user: User, request_id: uuid.UUID) -> PickupRequest:
    request_obj = await db.get(PickupRequest, request_id)
    if request_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    if request_obj.status not in ("PENDING", "QUEUED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La solicitud no está en espera")

    await _require_teacher_for_request(db, user, request_obj)

    request_obj.status = "CALLED"
    request_obj.called_at = datetime.now(timezone.utc)
    await _log(
        db,
        school_id=None,
        user_id=user.id,
        action="PICKUP_REQUEST_CALLED",
        entity_type="pickup_requests",
        entity_id=request_obj.id,
    )
    await db.commit()
    await db.refresh(request_obj)
    return request_obj


async def deliver_pickup_request(
    db: AsyncSession,
    *,
    user: User,
    request_id: uuid.UUID,
    collector_member_id: uuid.UUID,
    verification_method: str,
    observation: str | None,
) -> PickupDelivery:
    request_obj = await db.get(PickupRequest, request_id)
    if request_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    if request_obj.status not in ("CALLED", "IN_PROGRESS"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La solicitud no está lista para entrega")

    await _require_teacher_for_request(db, user, request_obj)

    collector = await db.get(FamilyMember, collector_member_id)
    if collector is None or collector.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Persona que recoge inválida")

    # Regla de negocio central: quien recoge debe estar autorizado, sin importar
    # quién fue el "intended_collector" original de la solicitud.
    if not await _has_active_authorization(db, collector.id, request_obj.student_id):
        request_obj.status = "REJECTED"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Persona no autorizada para recoger a este estudiante. Solicitud rechazada.",
        )

    delivery = PickupDelivery(
        pickup_request_id=request_obj.id,
        student_id=request_obj.student_id,
        collector_member_id=collector.id,
        verified_by_user_id=user.id,
        verification_method=verification_method,
        status="DELIVERED",
        observation=observation,
    )
    db.add(delivery)

    request_obj.status = "COMPLETED"

    await _log(
        db,
        school_id=None,
        user_id=user.id,
        action="PICKUP_DELIVERED",
        entity_type="pickup_deliveries",
        entity_id=None,
        new_values={
            "pickup_request_id": str(request_obj.id),
            "collector_member_id": str(collector.id),
            "verification_method": verification_method,
        },
    )

    await db.commit()
    await db.refresh(delivery)
    return delivery


async def cancel_pickup_request(db: AsyncSession, *, user: User, request_id: uuid.UUID) -> PickupRequest:
    request_obj = await db.get(PickupRequest, request_id)
    if request_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud no encontrada")
    if request_obj.status not in ("PENDING", "QUEUED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya no se puede cancelar esta solicitud")

    requester = await db.get(FamilyMember, request_obj.requested_by_member_id)
    if requester is None or requester.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo quien solicitó puede cancelar")

    request_obj.status = "CANCELLED"
    request_obj.cancelled_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(request_obj)
    return request_obj


async def classroom_queue(db: AsyncSession, *, user: User, classroom_id: uuid.UUID) -> list[PickupRequest]:
    stmt = select(TeacherClassroom).where(
        TeacherClassroom.classroom_id == classroom_id,
        TeacherClassroom.teacher_user_id == user.id,
        TeacherClassroom.status == "ACTIVE",
    )
    result = await db.execute(stmt)
    if result.scalars().first() is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes esa aula asignada")

    stmt = (
        select(PickupRequest)
        .join(StudentEnrollment, StudentEnrollment.student_id == PickupRequest.student_id)
        .where(
            StudentEnrollment.classroom_id == classroom_id,
            StudentEnrollment.status == "ACTIVE",
            PickupRequest.status.in_(["PENDING", "QUEUED", "CALLED", "IN_PROGRESS"]),
        )
        .order_by(PickupRequest.turn_number.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
