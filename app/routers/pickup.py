import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import PickupRequestIn, PickupRequestOut
from app.services import pickup_service

router = APIRouter(prefix="/pickup", tags=["pickup"])


@router.post("/requests", response_model=PickupRequestOut)
async def create_request(
    payload: PickupRequestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pickup_service.create_pickup_request(
        db,
        user=user,
        pickup_session_id=payload.pickup_session_id,
        student_id=payload.student_id,
        intended_collector_member_id=payload.intended_collector_member_id,
    )


@router.post("/requests/{request_id}/cancel", response_model=PickupRequestOut)
async def cancel_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await pickup_service.cancel_pickup_request(db, user=user, request_id=request_id)
