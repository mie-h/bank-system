"""API endpoints for account management."""

from http import HTTPStatus
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bank_system.core.auth import verify_credentials
from bank_system.db import get_conn

router = APIRouter(prefix="/accounts", tags=["accounts"])


class CreateAccountResponse(BaseModel):
    """Response model for an account."""

    id: int
    balance: float


# TODO(Mie): What error handling is needed here?
# Up to how many accounts a user can have?
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_account(
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[asyncpg.Connection, Depends(get_conn)],
) -> CreateAccountResponse:
    """Create a new account for a user."""
    row = await conn.fetchrow(
        """
        INSERT INTO accounts (user_id, balance)
        SELECT id, 0
        FROM users
        WHERE username = $1
        RETURNING id, user_id, balance
        """,
        username,
    )

    assert row is not None
    return CreateAccountResponse.model_validate(dict(row))


@router.get("/{account_id}", response_model=CreateAccountResponse)
async def get_account(
    account_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[asyncpg.Connection, Depends(get_conn)],
) -> CreateAccountResponse:
    """Get account details by account ID."""
    row = await conn.fetchrow(
        """
        SELECT
            id, balance
        FROM accounts
        WHERE id = $1
        AND user_id = (
            SELECT id
            FROM users
            WHERE username = $2
        )
        """,
        account_id,
        username,
    )

    if row is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Account not found",
        )

    return CreateAccountResponse.model_validate(dict(row))


@router.get("/", response_model=list[CreateAccountResponse])
async def get_accounts(
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[asyncpg.Connection, Depends(get_conn)],
) -> list[CreateAccountResponse]:
    """Get all accounts for a specific user."""
    try:
        rows = await conn.fetch(
            """
            SELECT id, user_id, balance
            FROM accounts
            WHERE user_id = (
                SELECT id
                FROM users
                WHERE username = $1
            )
            ORDER BY created_at DESC
            """,
            username,
        )
    except asyncpg.NoDataFoundError as err:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="User has no accounts",
        ) from err
    except asyncpg.ForeignKeyViolationError as err:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid user ID",
        ) from err

    return [CreateAccountResponse.model_validate(dict(row)) for row in rows]
