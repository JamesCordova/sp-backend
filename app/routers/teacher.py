import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import DeliverRequestIn, PickupDeliveryOut, PickupRequestOut, PickupRequestQueueOut
from app.services import pickup_service

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/classrooms/{classroom_id}/queue", response_model=list[PickupRequestQueueOut])
async def get_queue(
    classroom_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await pickup_service.classroom_queue(db, user=user, classroom_id=classroom_id)
    return [
        PickupRequestQueueOut(
            id=req.id,
            turn_number=req.turn_number,
            status=req.status,
            requested_at=req.requested_at,
            called_at=req.called_at,
            student_id=student.id,
            student_name=f"{student.first_name} {student.last_name}",
            requested_by_member_id=req.requested_by_member_id,
            requested_by_name=requester_user.full_name,
            intended_collector_member_id=req.intended_collector_member_id,
            intended_collector_name=collector_user.full_name,
        )
        for req, student, requester_user, collector_user in rows
    ]


@router.post("/requests/{request_id}/call", response_model=PickupRequestOut)
async def call_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pickup_service.call_pickup_request(db, user=user, request_id=request_id)


@router.post("/requests/{request_id}/deliver", response_model=PickupDeliveryOut)
async def deliver_request(
    request_id: uuid.UUID,
    payload: DeliverRequestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pickup_service.deliver_pickup_request(
        db,
        user=user,
        request_id=request_id,
        collector_member_id=payload.collector_member_id,
        verification_method=payload.verification_method,
        observation=payload.observation,
    )
