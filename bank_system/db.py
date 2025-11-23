"""Database connection management."""

from collections.abc import AsyncIterator  # noqa: TC003
from typing import Annotated

import asyncpg
from fastapi import Depends

from bank_system.core.config import settings

_pool: asyncpg.Pool | None = None


# TODO(Mie): what to do with global pool?
async def get_pool() -> asyncpg.Pool:
    """Get or create a global asyncpg connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url)
    return _pool


async def get_conn(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> AsyncIterator[asyncpg.pool.PoolConnectionProxy]:
    """Get a database connection from the pool."""
    async with pool.acquire() as conn:
        yield conn
