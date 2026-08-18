import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import FamilyMember, SchoolUserRole, TeacherClassroom, User

bearer_scheme = HTTPBearer()


def decode_supabase_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """Verifica el JWT emitido por Supabase Auth (HS256, JWT secret del proyecto)."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        ) from exc
    return payload


async def get_current_user(
    payload: dict = Depends(decode_supabase_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin subject")

    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        # El trigger de Postgres crea el perfil al registrarse en Supabase Auth;
        # si no existe todavía, el registro no terminó de propagarse.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de usuario no encontrado")
    if user.status != "ACTIVE" or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta bloqueada o inactiva")
    return user


async def require_school_role(
    school_id: uuid.UUID,
    allowed_roles: set[str],
    user: User,
    db: AsyncSession,
) -> SchoolUserRole:
    stmt = (
        select(SchoolUserRole)
        .where(
            SchoolUserRole.school_id == school_id,
            SchoolUserRole.user_id == user.id,
            SchoolUserRole.status == "ACTIVE",
        )
    )
    result = await db.execute(stmt)
    roles = result.scalars().all()
    for role in roles:
        if role.role.name in allowed_roles:
            return role
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes ese rol en el colegio")


async def require_family_membership(
    family_id: uuid.UUID,
    user: User,
    db: AsyncSession,
    allowed_family_roles: set[str] | None = None,
) -> FamilyMember:
    stmt = select(FamilyMember).where(
        FamilyMember.family_id == family_id,
        FamilyMember.user_id == user.id,
        FamilyMember.status == "ACTIVE",
        FamilyMember.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No perteneces a esta familia")
    if allowed_family_roles and member.family_role not in allowed_family_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tu rol familiar no permite esta acción")
    return member


async def require_teacher_of_classroom(
    classroom_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> TeacherClassroom:
    stmt = select(TeacherClassroom).where(
        TeacherClassroom.classroom_id == classroom_id,
        TeacherClassroom.teacher_user_id == user.id,
        TeacherClassroom.status == "ACTIVE",
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes esa aula asignada")
    return link
