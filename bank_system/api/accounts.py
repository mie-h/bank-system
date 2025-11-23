"""API endpoints for account management."""

from typing import Annotated

from asyncpg import Connection  # noqa: TC002
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bank_system.db import get_conn

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    """Request model for creating a new account.

    user_id : int
        The ID of the user to create the account for.
    """

    user_id: int


class Account(BaseModel):
    """Response model for an account.

    id: int
        The ID of the account.
    user_id: int
        The ID of the user who owns the account.
    balance: float
        The current balance of the account.
    """

    id: int
    user_id: int
    balance: float


# TODO(Mie): What error handling is needed here?
# Up to how many accounts a user can have?
@router.post("/", response_model=Account, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    conn: Annotated[Connection, Depends(get_conn)],
) -> Account:
    """Create a new account for a user.

    user_id : int
        The ID of the user to create the account for.

    Returns:
        Account
            The created account.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO accounts (user_id, balance)
        VALUES ($1, $2)
        RETURNING id, user_id, balance
        """,
        payload.user_id,
        0.0,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account",
        )

    return Account.model_validate(dict(row))


@router.get("/{account_id}", response_model=Account)
async def get_account(
    account_id: int,
    conn: Annotated[Connection, Depends(get_conn)],
) -> Account:
    """Get account details by account ID.

    account_id : int
        The ID of the account to retrieve.

    Returns:
        Account
            The account details.
    """
    row = await conn.fetchrow(
        "SELECT id, user_id, balance FROM accounts WHERE id = $1",
        account_id,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    return Account.model_validate(dict(row))


@router.get("/user/{user_id}", response_model=list[Account])
async def get_accounts_by_user(
    user_id: int,
    conn: Annotated[Connection, Depends(get_conn)],
):
    """Get all accounts for a specific user.

    user_id : int
        The ID of the user whose accounts to retrieve.

    Returns:
        list[Account]
            A list of accounts belonging to the user.
    """
    rows = await conn.fetch(
        """
        SELECT id, user_id, balance
        FROM accounts
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )
    if not rows:
        # TODO(Mie): What should I return here?
        return None

    return [Account.model_validate(dict(row)) for row in rows]
