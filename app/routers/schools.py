import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import PickupSession, School, User
from app.schemas import PickupSessionOut, SchoolOut

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("", response_model=list[SchoolOut])
async def list_schools(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(select(School).where(School.status == "ACTIVE", School.deleted_at.is_(None)))
    ).scalars().all()
    return rows


@router.get("/{school_id}/pickup-sessions/current", response_model=PickupSessionOut)
async def get_current_session(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    stmt = (
        select(PickupSession)
        .where(
            PickupSession.school_id == school_id,
            PickupSession.session_date == today,
            PickupSession.status == "OPEN",
        )
        .order_by(PickupSession.start_time.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    session_obj = result.scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay una jornada de recojo abierta hoy para este colegio",
        )
    return session_obj
