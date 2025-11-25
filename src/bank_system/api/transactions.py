"""API endpoints for transaction operations."""

from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Annotated, NewType, TypedDict, cast

from annotated_types import Gt
from asyncpg import Connection  # noqa: TC002
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from bank_system.core.auth import verify_credentials
from bank_system.db import get_conn

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"],
    dependencies=[Depends(verify_credentials)],
)

AccountId = NewType("AccountId", int)


class CreateDepositRequest(BaseModel):
    """Request model for creating deposit transaction."""

    account_id: AccountId
    amount: Annotated[Decimal, Gt(0)]


class CreateWithdrawalRequest(BaseModel):
    """Request model for creating withdrawal transaction."""

    account_id: AccountId
    amount: Annotated[Decimal, Gt(0)]


class CreateTransferRequest(BaseModel):
    """Request model for creating a transfer transaction."""

    from_: Annotated[AccountId, Field(alias="from")]
    to: AccountId
    amount: Annotated[Decimal, Gt(0)]

    @field_validator("to", mode="after")
    @classmethod
    def _different_accounts(cls, to: AccountId, info: ValidationInfo) -> AccountId:
        """Validate that from and to accounts are different."""
        if "from_" in info.data and info.data["from_"] == to:
            msg = "Cannot transfer to the same account."
            raise ValueError(msg)
        return to


class _DepositRecord(TypedDict):
    to_account_id: AccountId
    to_account_balance: Decimal


class _WithdrawalRecord(TypedDict):
    from_account_id: AccountId
    from_account_balance: Decimal


class _TransferRecord(TypedDict):
    from_account_id: AccountId | None
    from_account_balance: Decimal | None
    to_account_id: AccountId | None


class Transaction(BaseModel):
    """Model representing a transaction."""

    from_account_id: Annotated[
        AccountId | None, Field(alias="from", exclude_if=lambda x: x is None)
    ]
    to_account_id: Annotated[
        AccountId | None, Field(alias="to", exclude_if=lambda x: x is None)
    ]
    amount: Decimal
    created_at: datetime


@router.post(path="/deposit", status_code=HTTPStatus.CREATED)
async def create_deposit(
    request: CreateDepositRequest,
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Create a deposit transaction for an account."""
    async with conn.transaction():
        record = cast(
            _DepositRecord | None,
            await conn.fetchrow(
                """
                WITH check_to_account AS (
                    SELECT 1
                    FROM accounts AS a
                    JOIN users AS u ON a.user_id = u.id
                    WHERE a.id = $2 AND u.username = $4
                ), deposit AS (
                    UPDATE accounts
                    SET balance = balance + $3
                    WHERE id = $2 AND EXISTS (SELECT 1 FROM check_to_account)
                    RETURNING id, balance
                ), transaction AS (
                    INSERT INTO transactions (from_account_id, to_account_id, amount)
                    SELECT $1, $2, $3
                    WHERE EXISTS (SELECT 1 FROM deposit)
                    RETURNING id
                )
                SELECT
                    deposit.id AS to_account_id,
                    deposit.balance AS to_account_balance
                FROM deposit
                """,
                None,
                request.account_id,
                request.amount,
                username,
            ),
        )
        if record is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Account not found"
            )


@router.post(path="/withdrawal", status_code=HTTPStatus.CREATED)
async def create_withdrawal(
    request: CreateWithdrawalRequest,
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Create a withdrawal transaction for an account."""
    async with conn.transaction():
        record = cast(
            _WithdrawalRecord | None,
            await conn.fetchrow(
                """
                WITH from_account_check AS (
                    SELECT 1
                    FROM accounts AS a
                    JOIN users AS u ON a.user_id = u.id
                    WHERE a.id = $1 AND u.username = $4
                ),
                withdrawal AS (
                    UPDATE accounts
                    SET balance = balance - $3
                    WHERE id = $1 AND EXISTS (SELECT 1 FROM from_account_check)
                    RETURNING id, balance
                ), transaction AS (
                    INSERT INTO transactions (from_account_id, to_account_id, amount)
                    SELECT $1, $2, $3
                    WHERE EXISTS (SELECT 1 FROM withdrawal)
                    RETURNING id
                )
                SELECT
                    withdrawal.id AS from_account_id,
                    withdrawal.balance AS from_account_balance
                FROM withdrawal
                """,
                request.account_id,
                None,
                request.amount,
                username,
            ),
        )
        if record is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Account not found"
            )

        if record["from_account_balance"] < 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Insufficient funds in this account",
            )


# TODO(Mie): Figure out how writing with multiple statements could result in deadlocks
# depending on isolation level.
@router.post(path="/transfer", status_code=HTTPStatus.CREATED)
async def create_transfer(
    request: CreateTransferRequest,
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> None:
    """Create a transfer transaction between two accounts.

    Returns:
        A mapping of transfer types to their respective transfer transactions.
    """
    async with conn.transaction():
        record = cast(
            _TransferRecord | None,
            await conn.fetchrow(
                """
                WITH from_account_check AS (
                    SELECT 1
                    FROM accounts AS a
                    JOIN users AS u ON a.user_id = u.id
                    WHERE a.id = $1 AND u.username = $4)
                , withdrawal AS (
                    UPDATE accounts
                    SET balance = balance - $3
                    WHERE id = $1 AND EXISTS (SELECT 1 FROM from_account_check)
                    RETURNING id, balance
                ), deposit AS (
                    UPDATE accounts
                    SET balance = balance + $3
                    WHERE id = $2
                    RETURNING id
                ), transaction AS (
                    INSERT INTO transactions (from_account_id, to_account_id, amount)
                    SELECT $1, $2, $3
                    WHERE EXISTS (SELECT 1 FROM withdrawal)
                    AND EXISTS (SELECT 1 FROM deposit)
                    RETURNING id
                )
                SELECT
                    withdrawal.id AS from_account_id,
                    withdrawal.balance AS from_account_balance,
                    deposit.id AS to_account_id
                FROM withdrawal
                FULL JOIN deposit ON TRUE
                """,
                request.from_,
                request.to,
                request.amount,
                username,
            ),
        )

        if record is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="From account and to account not found",
            )

        if record.get("from_account_id") is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="From account not found",
            )
        if record.get("to_account_id") is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="To account not found",
            )
        from_balance = record.get("from_account_balance")
        if from_balance is not None and from_balance < 0:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Insufficient funds in from account",
            )


@router.get("/account/{account_id}")
async def get_transactions_by_account(
    account_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> list[Transaction]:
    """Get all transactions for a specific account."""
    records = await conn.fetch(
        """
        SELECT
            from_account_id AS from,
            to_account_id AS to,
            amount,
            created_at
        FROM transactions
        WHERE (from_account_id = $1 OR to_account_id = $1)
        AND EXISTS (
            SELECT 1
            FROM accounts AS a
            JOIN users AS u ON a.user_id = u.id
            WHERE a.id = $1 AND u.username = $2
        )
        ORDER BY created_at DESC
        """,
        account_id,
        username,
    )

    if not records:
        account_exists = cast(
            int | None,
            await conn.fetchval(
                """
                SELECT 1
                FROM accounts AS a
                JOIN users AS u ON a.user_id = u.id
                WHERE a.id = $1
                AND u.username = $2
                """,
                account_id,
                username,
            ),
        )

        if account_exists is None:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Account not found",
            )

    return [Transaction.model_validate(dict(record)) for record in records]
