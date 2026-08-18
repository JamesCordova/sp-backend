import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_school_role
from app.database import get_db
from app.models import (
    AcademicYear,
    Classroom,
    Family,
    FamilyStudent,
    PickupDelivery,
    PickupRequest,
    PickupSession,
    SchoolUserRole,
    Student,
    User,
)
from app.schemas import (
    AcademicYearOut,
    AssignTeacherIn,
    ClassroomIn,
    ClassroomOut,
    FamilyStudentOut,
    GrantRoleIn,
    PendingFamilyStudentOut,
    PickupDeliveryOut,
    PickupSessionIn,
    PickupSessionOut,
    SchoolUserRoleOut,
    StudentIn,
    StudentOut,
    TeacherClassroomOut,
    VerifyFamilyStudentIn,
)
from app.services import admin_service, family_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/schools/{school_id}/classrooms", response_model=list[ClassroomOut])
async def list_classrooms(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    rows = (
        await db.execute(
            select(Classroom)
            .join(AcademicYear, AcademicYear.id == Classroom.academic_year_id)
            .where(AcademicYear.school_id == school_id, Classroom.deleted_at.is_(None))
            .order_by(Classroom.name)
        )
    ).scalars().all()
    return rows


@router.post("/schools/{school_id}/classrooms", response_model=ClassroomOut)
async def create_classroom(
    school_id: uuid.UUID,
    payload: ClassroomIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    return await admin_service.create_classroom(
        db,
        school_id=school_id,
        academic_year_id=payload.academic_year_id,
        name=payload.name,
        grade=payload.grade,
        section=payload.section,
    )


@router.get("/schools/{school_id}/students", response_model=list[StudentOut])
async def list_students(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    rows = (
        await db.execute(
            select(Student)
            .where(Student.school_id == school_id, Student.deleted_at.is_(None))
            .order_by(Student.first_name)
        )
    ).scalars().all()
    return rows


@router.post("/schools/{school_id}/students", response_model=StudentOut)
async def create_student(
    school_id: uuid.UUID,
    payload: StudentIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    return await admin_service.create_student(
        db,
        school_id=school_id,
        student_code=payload.student_code,
        first_name=payload.first_name,
        last_name=payload.last_name,
        birth_date=payload.birth_date,
        classroom_id=payload.classroom_id,
    )


@router.post("/schools/{school_id}/classrooms/{classroom_id}/teachers", response_model=TeacherClassroomOut)
async def assign_teacher(
    school_id: uuid.UUID,
    classroom_id: uuid.UUID,
    payload: AssignTeacherIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    return await admin_service.assign_teacher(
        db, classroom_id=classroom_id, email=payload.email, is_primary=payload.is_primary
    )


@router.get("/schools/{school_id}/roles", response_model=list[SchoolUserRoleOut])
async def list_school_roles(
    school_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    rows = (
        await db.execute(
            select(SchoolUserRole, User)
            .join(User, User.id == SchoolUserRole.user_id)
            .where(SchoolUserRole.school_id == school_id, SchoolUserRole.status == "ACTIVE")
        )
    ).all()
    return [
        SchoolUserRoleOut(
            id=sur.id,
            user_id=sur.user_id,
            email=u.email,
            full_name=u.full_name,
            role=sur.role.name,
            status=sur.status,
        )
        for sur, u in rows
    ]


@router.post("/schools/{school_id}/roles", response_model=SchoolUserRoleOut)
async def grant_role(
    school_id: uuid.UUID,
    payload: GrantRoleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_school_role(school_id, {"ADMIN"}, user, db)
    link = await admin_service.grant_school_role(db, school_id=school_id, email=payload.email, role_name=payload.role)
    target_user = await db.get(User, link.user_id)
    return SchoolUserRoleOut(
        id=link.id,
        user_id=link.user_id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=payload.role,
        status=link.status,
    )


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
