import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_family_membership
from app.database import get_db
from app.models import User
from app.schemas import (
    AcceptInvitationIn,
    AuthorizationIn,
    AuthorizationOut,
    FamilyMemberOut,
    FamilyStudentOut,
    InviteMemberIn,
    InvitationOut,
    LinkStudentIn,
)
from app.services import family_service

router = APIRouter(prefix="/families", tags=["families"])


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
