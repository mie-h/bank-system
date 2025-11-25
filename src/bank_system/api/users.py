"""User-related API endpoints."""

from http import HTTPStatus
from typing import Annotated

from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException

from bank_system.core.auth import verify_credentials
from bank_system.db import get_conn

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(verify_credentials)]
)


# TODO(Mie): What error handling is needed here?
@router.get("/{username}")
async def get_user(
    username: str, conn: Annotated[Connection, Depends(get_conn)]
) -> None:
    """Check if a user exists by username."""
    row = await conn.fetchrow(
        "SELECT 1 FROM users WHERE username = $1",
        username,
    )
    if row is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User not found",
        )
