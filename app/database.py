from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    # Todas las columnas de fecha/hora del esquema son TIMESTAMPTZ (con zona
    # horaria). Sin esto, SQLAlchemy mapea `datetime` a TIMESTAMP "naive" por
    # defecto, y asyncpg rechaza cualquier datetime con tzinfo (p. ej.
    # datetime.now(timezone.utc)) al intentar guardarlo.
    type_annotation_map = {datetime: DateTime(timezone=True)}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
