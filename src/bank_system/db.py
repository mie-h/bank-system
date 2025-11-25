"""Database connection management."""

from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager
from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI
from loguru import logger

from bank_system.core.auth import clear_users
from bank_system.core.config import Settings

_pool: asyncpg.Pool | None = None


# TODO(Mie): what to do with global pool?
async def get_pool() -> asyncpg.Pool:
    """Get or create a global asyncpg connection pool."""
    assert _pool is not None
    return _pool


@asynccontextmanager
async def lifespan(_app: FastAPI | None = None) -> AsyncIterator[None]:
    """Lifespan context manager to manage the database connection pool."""
    settings = Settings()
    clear_users()
    async with asyncpg.create_pool(settings.database_url) as pool:
        logger.info("Database pool created, connecting to {}", settings.database_url)
        global _pool  # noqa: PLW0603
        _pool = pool
        yield
        _pool = None


async def get_conn(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AsyncIterator[asyncpg.pool.PoolConnectionProxy]:
    """Get a database connection from the pool."""
    async with pool.acquire() as conn:
        yield conn
