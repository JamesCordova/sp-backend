import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_school_role
from app.database import get_db
from app.models import PickupDelivery, PickupRequest, PickupSession
from app.models import User
from app.schemas import (
    FamilyStudentOut,
    PickupDeliveryOut,
    PickupSessionIn,
    PickupSessionOut,
    VerifyFamilyStudentIn,
)
from app.services import family_service

router = APIRouter(prefix="/admin", tags=["admin"])


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
