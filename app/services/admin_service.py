import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AcademicYear,
    Classroom,
    Role,
    SchoolUserRole,
    Student,
    StudentEnrollment,
    TeacherClassroom,
    User,
)


async def create_classroom(
    db: AsyncSession, *, school_id: uuid.UUID, academic_year_id: uuid.UUID, name: str, grade: str, section: str | None
) -> Classroom:
    year = await db.get(AcademicYear, academic_year_id)
    if year is None or year.school_id != school_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Año académico inválido para este colegio")

    classroom = Classroom(academic_year_id=academic_year_id, name=name, grade=grade, section=section)
    db.add(classroom)
    await db.commit()
    await db.refresh(classroom)
    return classroom


async def create_student(
    db: AsyncSession,
    *,
    school_id: uuid.UUID,
    student_code: str,
    first_name: str,
    last_name: str,
    birth_date: date | None,
    classroom_id: uuid.UUID | None,
) -> Student:
    existing = await db.execute(
        select(Student).where(Student.school_id == school_id, Student.student_code == student_code)
    )
    if existing.scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un estudiante con ese código")

    student = Student(
        school_id=school_id,
        student_code=student_code,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
    )
    db.add(student)
    await db.flush()

    if classroom_id is not None:
        classroom = await db.get(Classroom, classroom_id)
        if classroom is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aula inválida")
        db.add(
            StudentEnrollment(
                student_id=student.id,
                classroom_id=classroom_id,
                start_date=date.today(),
            )
        )

    await db.commit()
    await db.refresh(student)
    return student


async def _get_user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay ninguna cuenta registrada con ese correo. La persona debe crear su cuenta primero.",
        )
    return user


async def assign_teacher(
    db: AsyncSession, *, classroom_id: uuid.UUID, email: str, is_primary: bool
) -> TeacherClassroom:
    user = await _get_user_by_email(db, email)

    existing = await db.execute(
        select(TeacherClassroom).where(
            TeacherClassroom.classroom_id == classroom_id, TeacherClassroom.teacher_user_id == user.id
        )
    )
    link = existing.scalars().first()
    if link is not None:
        link.status = "ACTIVE"
        link.is_primary = is_primary
    else:
        link = TeacherClassroom(classroom_id=classroom_id, teacher_user_id=user.id, is_primary=is_primary)
        db.add(link)

    await db.commit()
    await db.refresh(link)
    return link


async def grant_school_role(db: AsyncSession, *, school_id: uuid.UUID, email: str, role_name: str) -> SchoolUserRole:
    if role_name not in ("ADMIN", "TEACHER", "PARENT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol inválido")

    user = await _get_user_by_email(db, email)
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalars().first()
    if role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Rol no configurado en el sistema")

    existing = await db.execute(
        select(SchoolUserRole).where(
            SchoolUserRole.school_id == school_id,
            SchoolUserRole.user_id == user.id,
            SchoolUserRole.role_id == role.id,
        )
    )
    link = existing.scalars().first()
    if link is not None:
        link.status = "ACTIVE"
    else:
        link = SchoolUserRole(school_id=school_id, user_id=user.id, role_id=role.id)
        db.add(link)

    await db.commit()
    await db.refresh(link)
    return link
