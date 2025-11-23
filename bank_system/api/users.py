"""User-related API endpoints."""

from typing import Annotated

import asyncpg
from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bank_system.db import get_conn

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    """Request model for creating a new user.

    username : str
        The username of the new user.
    """

    username: str


class User(BaseModel):
    """Response model for a user.

    id : int
        The ID of the user.
    username : str
        The username of the user.
    """

    id: int
    username: str


@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate, conn: Annotated[Connection, Depends(get_conn)]
) -> User:
    """Create a new user.

    username : str
        The username of the new user.

    Returns:
        User
            The created user.
    """
    try:
        row = await conn.fetchrow(
            "INSERT INTO users (username) VALUES ($1) RETURNING id, username",
            payload.username,
        )
    except asyncpg.UniqueViolationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        ) from err

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )

    return User.model_validate(dict(row))


# TODO(Mie): What error handling is needed here?
@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: int, conn: Annotated[Connection, Depends(get_conn)]
) -> User:
    """Get user details by user ID.

    user_id : int
        The ID of the user to retrieve.

    Returns:
        User
            The user details.
    """
    row = await conn.fetchrow(
        "SELECT id, username FROM users WHERE id = $1",
        user_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return User.model_validate(dict(row))
