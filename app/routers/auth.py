from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import FamilyMember, SchoolUserRole, User
from app.schemas import MeOut

router = APIRouter(prefix="/me", tags=["auth"])


@router.get("", response_model=MeOut)
async def read_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    school_roles = (
        (
            await db.execute(
                select(SchoolUserRole).where(
                    SchoolUserRole.user_id == user.id, SchoolUserRole.status == "ACTIVE"
                )
            )
        )
        .scalars()
        .all()
    )
    family_memberships = (
        (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.user_id == user.id,
                    FamilyMember.status == "ACTIVE",
                    FamilyMember.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )

    return MeOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        school_roles=[
            {"school_id": str(r.school_id), "role": r.role.name} for r in school_roles
        ],
        family_memberships=[
            {
                "family_id": str(m.family_id),
                "family_member_id": str(m.id),
                "family_role": m.family_role,
                "relationship": m.relationship_label,
            }
            for m in family_memberships
        ],
    )
