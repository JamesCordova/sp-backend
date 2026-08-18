import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_school_role
from app.database import get_db
from app.models import (
    AcademicYear,
    Family,
    FamilyStudent,
    PickupDelivery,
    PickupRequest,
    PickupSession,
    Student,
    User,
)
from app.schemas import (
    AcademicYearOut,
    FamilyStudentOut,
    PendingFamilyStudentOut,
    PickupDeliveryOut,
    PickupSessionIn,
    PickupSessionOut,
    VerifyFamilyStudentIn,
)
from app.services import family_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/schools/{school_id}/academic-years", response_model=list[AcademicYearOut])
async def list_academic_years(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    rows = (
        await db.execute(select(AcademicYear).where(AcademicYear.school_id == school_id))
    ).scalars().all()
    return rows


@router.get("/schools/{school_id}/pickup-sessions", response_model=list[PickupSessionOut])
async def list_pickup_sessions(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    rows = (
        await db.execute(
            select(PickupSession)
            .where(PickupSession.school_id == school_id)
            .order_by(PickupSession.session_date.desc(), PickupSession.start_time.desc())
        )
    ).scalars().all()
    return rows


@router.get("/schools/{school_id}/family-students", response_model=list[PendingFamilyStudentOut])
async def list_family_students_for_review(
    school_id: uuid.UUID,
    review_status: str = "PENDING",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    stmt = (
        select(FamilyStudent, Family, Student)
        .join(Family, Family.id == FamilyStudent.family_id)
        .join(Student, Student.id == FamilyStudent.student_id)
        .where(Family.school_id == school_id, FamilyStudent.status == review_status)
        .order_by(FamilyStudent.created_at.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        PendingFamilyStudentOut(
            id=fs.id,
            family_id=fs.family_id,
            family_name=family.name,
            student_id=fs.student_id,
            student_name=f"{student.first_name} {student.last_name}",
            relationship_type=fs.relationship_type,
            status=fs.status,
            created_at=fs.created_at,
        )
        for fs, family, student in rows
    ]


@router.post("/schools/{school_id}/pickup-sessions", response_model=PickupSessionOut)
async def create_session(
    school_id: uuid.UUID,
    payload: PickupSessionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    session_obj = PickupSession(
        school_id=school_id,
        academic_year_id=payload.academic_year_id,
        session_date=payload.session_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(session_obj)
    await db.commit()
    await db.refresh(session_obj)
    return session_obj


@router.post("/schools/{school_id}/family-students/{family_student_id}/verify", response_model=FamilyStudentOut)
async def verify_family_student(
    school_id: uuid.UUID,
    family_student_id: uuid.UUID,
    payload: VerifyFamilyStudentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    return await family_service.verify_student_link(
        db, admin_user=user, family_student_id=family_student_id, approve=payload.approve
    )


@router.get("/schools/{school_id}/deliveries", response_model=list[PickupDeliveryOut])
async def list_deliveries(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    stmt = (
        select(PickupDelivery)
        .join(PickupRequest, PickupRequest.id == PickupDelivery.pickup_request_id)
        .join(PickupSession, PickupSession.id == PickupRequest.pickup_session_id)
        .where(PickupSession.school_id == school_id)
        .order_by(PickupDelivery.delivered_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
