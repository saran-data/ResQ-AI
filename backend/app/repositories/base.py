"""
ResQAI - Generic Base Repository
Type-safe async CRUD operations using the Repository Pattern.
All specific repositories extend this class.
"""

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.models.base import BaseModel
from app.core.logging import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    Generic async repository providing CRUD operations for any SQLAlchemy model.
    
    Usage:
        class UserRepository(BaseRepository[User]):
            def __init__(self, db: AsyncSession):
                super().__init__(User, db)
    """

    def __init__(self, model: Type[ModelType], db: AsyncSession) -> None:
        self._model = model
        self._db = db

    # -------------------------------------------------------
    # CREATE
    # -------------------------------------------------------
    async def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create a new record.

        Args:
            obj_in: Dict of field values to set

        Returns:
            Newly created and refreshed model instance
        """
        db_obj = self._model(**obj_in)
        self._db.add(db_obj)
        await self._db.flush()
        await self._db.refresh(db_obj)
        logger.debug(f"Created {self._model.__name__} id={db_obj.id}")
        return db_obj

    # -------------------------------------------------------
    # READ
    # -------------------------------------------------------
    async def get(self, id: UUID) -> Optional[ModelType]:
        """
        Fetch a single record by primary key.

        Args:
            id: UUID primary key

        Returns:
            Model instance or None
        """
        result = await self._db.execute(
            select(self._model).where(self._model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, id: UUID) -> ModelType:
        """
        Fetch by PK or raise 404 HTTPException.

        Args:
            id: UUID primary key

        Raises:
            HTTPException 404 if not found
        """
        from fastapi import HTTPException, status
        obj = await self.get(id)
        if obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self._model.__name__} with id {id} not found",
            )
        return obj

    async def get_by_field(self, field: str, value: Any) -> Optional[ModelType]:
        """Fetch first record where field == value."""
        result = await self._db.execute(
            select(self._model).where(getattr(self._model, field) == value)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = "created_at",
        order_desc: bool = True,
        filters: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[ModelType], int]:
        """
        Fetch a paginated list with optional filters.

        Args:
            skip: Number of records to skip
            limit: Max records to return
            order_by: Field name to sort by
            order_desc: True for descending order
            filters: Dict of {field: value} equality filters

        Returns:
            Tuple of (records, total_count)
        """
        query = select(self._model)

        # Apply equality filters
        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(self._model, field):
                    query = query.where(getattr(self._model, field) == value)

        # Apply soft-delete filter if model supports it
        if hasattr(self._model, "is_deleted"):
            query = query.where(self._model.is_deleted == False)  # noqa: E712

        # Count total (before pagination)
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar_one()

        # Apply ordering
        if order_by and hasattr(self._model, order_by):
            col = getattr(self._model, order_by)
            query = query.order_by(col.desc() if order_desc else col.asc())

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await self._db.execute(query)
        return list(result.scalars().all()), total

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        query = select(func.count(self._model.id))
        if filters:
            for field, value in filters.items():
                if value is not None and hasattr(self._model, field):
                    query = query.where(getattr(self._model, field) == value)
        if hasattr(self._model, "is_deleted"):
            query = query.where(self._model.is_deleted == False)  # noqa: E712
        result = await self._db.execute(query)
        return result.scalar_one()

    async def exists(self, id: UUID) -> bool:
        """Check if a record with the given ID exists."""
        result = await self._db.execute(
            select(func.count(self._model.id)).where(self._model.id == id)
        )
        return result.scalar_one() > 0

    # -------------------------------------------------------
    # UPDATE
    # -------------------------------------------------------
    async def update(self, id: UUID, obj_in: Dict[str, Any]) -> Optional[ModelType]:
        """
        Update a record by primary key.

        Args:
            id: UUID of record to update
            obj_in: Dict of fields to update (None values are skipped)

        Returns:
            Updated model instance or None if not found
        """
        # Filter out None values
        update_data = {k: v for k, v in obj_in.items() if v is not None}
        if not update_data:
            return await self.get(id)

        await self._db.execute(
            update(self._model)
            .where(self._model.id == id)
            .values(**update_data)
        )
        await self._db.flush()
        obj = await self.get(id)
        if obj:
            await self._db.refresh(obj)
        return obj

    async def update_instance(self, instance: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """Update a model instance directly (avoids extra SELECT)."""
        for field, value in obj_in.items():
            if hasattr(instance, field) and value is not None:
                setattr(instance, field, value)
        await self._db.flush()
        await self._db.refresh(instance)
        return instance

    # -------------------------------------------------------
    # DELETE
    # -------------------------------------------------------
    async def delete(self, id: UUID) -> bool:
        """
        Hard delete a record.
        Prefer soft_delete() for most entities.

        Returns:
            True if deleted, False if not found
        """
        result = await self._db.execute(
            delete(self._model).where(self._model.id == id)
        )
        return result.rowcount > 0

    async def soft_delete(self, id: UUID) -> Optional[ModelType]:
        """
        Soft-delete: set is_deleted=True and deleted_at=now().
        Only works for models with SoftDeleteMixin.

        Returns:
            Updated instance or None if not found
        """
        from datetime import datetime, timezone
        if not hasattr(self._model, "is_deleted"):
            raise NotImplementedError(f"{self._model.__name__} does not support soft delete")

        obj = await self.get_or_raise(id)
        obj.soft_delete()
        await self._db.flush()
        return obj

    # -------------------------------------------------------
    # BULK OPERATIONS
    # -------------------------------------------------------
    async def bulk_create(self, objects: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records in one flush."""
        instances = [self._model(**obj) for obj in objects]
        self._db.add_all(instances)
        await self._db.flush()
        for instance in instances:
            await self._db.refresh(instance)
        return instances

    async def get_by_ids(self, ids: List[UUID]) -> List[ModelType]:
        """Fetch multiple records by their IDs."""
        result = await self._db.execute(
            select(self._model).where(self._model.id.in_(ids))
        )
        return list(result.scalars().all())
