"""Generic async repository with CRUD operations."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic async repository for SQLAlchemy ORM models."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self._model = model
        self._session = session

    async def get_by_id(self, id_value: str, id_column: str = "") -> ModelType | None:
        """Get entity by primary key."""
        col = getattr(self._model, id_column) if id_column else self._model.__table__.primary_key.columns.values()[0]
        stmt = select(self._model).where(col == id_value)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_field(self, field: str, value: Any) -> ModelType | None:
        """Get entity by a single field value."""
        col = getattr(self._model, field)
        stmt = select(self._model).where(col == value)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModelType]:
        """Get multiple entities with optional filtering."""
        stmt = select(self._model)
        if filters:
            for field, value in filters.items():
                col = getattr(self._model, field)
                stmt = stmt.where(col == value)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count entities with optional filtering."""
        stmt = select(func.count()).select_from(self._model)
        if filters:
            for field, value in filters.items():
                col = getattr(self._model, field)
                stmt = stmt.where(col == value)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def create(self, entity: ModelType) -> ModelType:
        """Create a new entity."""
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def update(self, entity: ModelType) -> ModelType:
        """Update an existing entity."""
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Delete an entity."""
        await self._session.delete(entity)
        await self._session.flush()

    def query(self) -> Select:
        """Start a new select query for advanced filtering."""
        return select(self._model)
