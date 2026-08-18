import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    FamilyMember,
    FamilyStudent,
    SchoolUserRole,
    Student,
    StudentEnrollment,
    TeacherClassroom,
    User,
)
from app.schemas import StudentOut

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}", response_model=StudentOut)
async def get_student(
    student_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    student = await db.get(Student, student_id)
    if student is None or student.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")

    is_verified_family = (
        await db.execute(
            select(FamilyStudent)
            .join(FamilyMember, FamilyMember.family_id == FamilyStudent.family_id)
            .where(
                FamilyStudent.student_id == student_id,
                FamilyStudent.status == "VERIFIED",
                FamilyMember.user_id == user.id,
                FamilyMember.status == "ACTIVE",
            )
        )
    ).scalars().first() is not None

    is_school_admin = (
        await db.execute(
            select(SchoolUserRole).where(
                SchoolUserRole.school_id == student.school_id,
                SchoolUserRole.user_id == user.id,
                SchoolUserRole.status == "ACTIVE",
            )
        )
    ).scalars().first() is not None

    is_assigned_teacher = (
        await db.execute(
            select(TeacherClassroom)
            .join(StudentEnrollment, StudentEnrollment.classroom_id == TeacherClassroom.classroom_id)
            .where(
                StudentEnrollment.student_id == student_id,
                StudentEnrollment.status == "ACTIVE",
                TeacherClassroom.teacher_user_id == user.id,
                TeacherClassroom.status == "ACTIVE",
            )
        )
    ).scalars().first() is not None

    if not (is_verified_family or is_school_admin or is_assigned_teacher):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a este estudiante")

    return student
