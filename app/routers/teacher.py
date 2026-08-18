import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import DeliverRequestIn, PickupDeliveryOut, PickupRequestOut
from app.services import pickup_service

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.get("/classrooms/{classroom_id}/queue", response_model=list[PickupRequestOut])
async def get_queue(
    classroom_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pickup_service.classroom_queue(db, user=user, classroom_id=classroom_id)


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
