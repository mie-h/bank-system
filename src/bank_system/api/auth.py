"""Authentication endpoints."""

from http import HTTPStatus
from typing import Annotated

import asyncpg
from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel

from bank_system.core.auth import register_user, verify_credentials
from bank_system.db import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    username: str
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest, conn: Annotated[Connection, Depends(get_conn)]
) -> None:
    """Register a new user with username and password stored in memory."""
    try:
        _ = await conn.fetchrow(
            "INSERT INTO users (username) VALUES ($1) RETURNING id",
            request.username,
        )
    except asyncpg.UniqueViolationError:
        logger.warning(
            "Username already exists. Reregistering user {}", request.username
        )

    try:
        register_user(request.username, request.password)
    except ValueError as err:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(err),
        ) from err


@router.get("/me")
async def get_current_user(
    username: Annotated[str, Depends(verify_credentials)],
) -> dict[str, str]:
    """Get the currently authenticated user."""
    return {"username": username}
