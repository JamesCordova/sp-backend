import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: str


class AcademicYearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    status: str


class MeOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    school_roles: list[dict]
    family_memberships: list[dict]
    teacher_classrooms: list[dict] = []


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    school_id: uuid.UUID
    student_code: str
    first_name: str
    last_name: str
    status: str


class FamilyMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    relationship_label: str
    family_role: str
    status: str


class FamilyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    status: str
    members: list[FamilyMemberOut] = []


class CreateFamilyIn(BaseModel):
    school_id: uuid.UUID
    name: str


class InviteMemberIn(BaseModel):
    email: str | None = None
    phone: str | None = None
    relationship: str
    family_role: str = "MEMBER"


class InvitationOut(BaseModel):
    id: uuid.UUID
    expires_at: datetime
    status: str
    token: str


class AcceptInvitationIn(BaseModel):
    token: str
    relationship: str | None = None


class LinkStudentIn(BaseModel):
    student_code: str
    relationship_type: str


class FamilyStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    family_id: uuid.UUID
    student_id: uuid.UUID
    relationship_type: str
    status: str


class FamilyStudentWithStudentOut(FamilyStudentOut):
    student_code: str
    first_name: str
    last_name: str


class PendingFamilyStudentOut(BaseModel):
    id: uuid.UUID
    family_id: uuid.UUID
    family_name: str
    student_id: uuid.UUID
    student_name: str
    relationship_type: str
    status: str
    created_at: datetime


class VerifyFamilyStudentIn(BaseModel):
    approve: bool


class AuthorizationIn(BaseModel):
    family_member_id: uuid.UUID
    student_id: uuid.UUID
    authorized: bool = True
    start_date: date | None = None
    end_date: date | None = None


class AuthorizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    family_member_id: uuid.UUID
    student_id: uuid.UUID
    authorized: bool
    status: str


class PickupSessionIn(BaseModel):
    school_id: uuid.UUID
    academic_year_id: uuid.UUID
    session_date: date
    start_time: time
    end_time: time | None = None


class PickupSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    session_date: date
    start_time: time
    end_time: time | None
    status: str


class PickupRequestIn(BaseModel):
    pickup_session_id: uuid.UUID
    student_id: uuid.UUID
    intended_collector_member_id: uuid.UUID


class PickupRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pickup_session_id: uuid.UUID
    student_id: uuid.UUID
    requested_by_member_id: uuid.UUID
    intended_collector_member_id: uuid.UUID
    turn_number: int | None
    status: str
    requested_at: datetime
    called_at: datetime | None


class PickupRequestQueueOut(BaseModel):
    id: uuid.UUID
    turn_number: int | None
    status: str
    requested_at: datetime
    called_at: datetime | None
    student_id: uuid.UUID
    student_name: str
    requested_by_member_id: uuid.UUID
    requested_by_name: str
    intended_collector_member_id: uuid.UUID
    intended_collector_name: str


class DeliverRequestIn(BaseModel):
    collector_member_id: uuid.UUID
    verification_method: str
    observation: str | None = None


class PickupDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    pickup_request_id: uuid.UUID
    student_id: uuid.UUID
    collector_member_id: uuid.UUID
    verification_method: str
    status: str
    delivered_at: datetime
    observation: str | None
