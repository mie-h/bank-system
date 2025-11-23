"""API endpoints for transaction operations."""

from collections.abc import Mapping  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from enum import Enum
from typing import TYPE_CHECKING, Annotated

from asyncpg import Connection  # noqa: TC002
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bank_system.db import get_conn

if TYPE_CHECKING:
    from asyncpg import Record


router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionType(Enum):
    """String constants for transaction types.

    DEPOSIT : str
        Constant for deposit transactions.
    WITHDRAWAL : str
        Constant for withdrawal transactions.
    """

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


class DepositCreate(BaseModel):
    """Request model for creating a deposit transaction.

    account_id : int
        The ID of the account to deposit into.
    amount : Decimal
        The amount to deposit.
    """

    account_id: int
    amount: Decimal


class Transaction(BaseModel):
    """Response model for a transaction.

    id : int
        The ID of the transaction.
    account_id : int
        The ID of the account associated with the transaction.
    amount : Decimal
        The amount of the transaction.
    transaction_type : str
        The type of the transaction (e.g., 'deposit', 'withdrawal').
    """

    id: int
    account_id: int
    amount: Decimal
    transaction_type: str


class WithdrawalCreate(BaseModel):
    """Request model for creating a withdrawal transaction.

    account_id : int
        The ID of the account to withdraw from.
    amount : Decimal
        The amount to withdraw.
    """

    account_id: int
    amount: Decimal


class TransferCreate(BaseModel):
    """Request model for creating a transfer transaction.

    from_account_id : int
        The ID of the account to transfer from.
    to_account_id : int
        The ID of the account to transfer to.
    amount : Decimal
        The amount to transfer.
    """

    from_account_id: int
    to_account_id: int
    amount: Decimal


@router.post(
    path="/deposit", response_model=Transaction, status_code=status.HTTP_201_CREATED
)
async def create_deposit(
    payload: DepositCreate,
    conn: Annotated[Connection, Depends(get_conn)],
) -> Transaction:
    """Create a deposit transaction for an account.

    account_id : int
        The ID of the account to deposit into.
    amount : Decimal
        The amount to deposit.

    Returns:
        Transaction
            The created deposit transaction.
    """
    if payload.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit amount must be positive",
        )

    async with conn.transaction():
        account = await conn.fetchrow(
            "SELECT id, balance FROM accounts WHERE id = $1",
            payload.account_id,
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        _ = await conn.execute(
            "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
            payload.amount,
            payload.account_id,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO transactions (account_id, amount, transaction_type)
            VALUES ($1, $2, $3)
            RETURNING id, account_id, amount, transaction_type
            """,
            payload.account_id,
            payload.amount,
            TransactionType.DEPOSIT.value,
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create deposit transaction",
        )

    return Transaction.model_validate(dict(row))


@router.post(
    path="/withdrawal", response_model=Transaction, status_code=status.HTTP_201_CREATED
)
async def create_withdrawal(
    payload: WithdrawalCreate,
    conn: Annotated[Connection, Depends(get_conn)],
) -> Transaction:
    """Create a withdrawal transaction for an account.

    account_id : int
        The ID of the account to withdraw from.
    amount : Decimal
        The amount to withdraw.

    Returns:
        Transaction
            The created withdrawal transaction.
    """
    if payload.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Withdrawal amount must be positive",
        )

    async with conn.transaction():
        account = await conn.fetchrow(
            "SELECT id, balance FROM accounts WHERE id = $1",
            payload.account_id,
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        if account["balance"] < payload.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient funds",
            )
        _ = await conn.execute(
            "UPDATE accounts SET balance = balance - $1 WHERE id = $2",
            payload.amount,
            payload.account_id,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO transactions (account_id, amount, transaction_type)
            VALUES ($1, $2, $3)
            RETURNING id, account_id, amount, transaction_type
            """,
            payload.account_id,
            payload.amount,
            TransactionType.WITHDRAWAL.value,
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create withdrawal transaction",
        )

    return Transaction.model_validate(dict(row))


@router.post(
    path="/transfer", response_model=Transaction, status_code=status.HTTP_201_CREATED
)
async def create_transfer(
    payload: TransferCreate,
    conn: Annotated[Connection, Depends(get_conn)],
) -> Mapping[str, Transaction]:
    """Create a transfer transaction between two accounts.

    from_account_id : int
        The ID of the account to transfer from.
    to_account_id : int
        The ID of the account to transfer to.
    amount : Decimal
        The amount to transfer.

    Returns:
        Mapping[str, Transaction]
            A mapping of transfer types to their respective transfer transactions.
    """
    if payload.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transfer amount must be positive",
        )

    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transfer to the same account",
        )

    async with conn.transaction():
        from_account = await conn.fetchrow(
            "SELECT id, balance FROM accounts WHERE id = $1",
            payload.from_account_id,
        )
        to_account = await conn.fetchrow(
            "SELECT id, balance FROM accounts WHERE id = $1",
            payload.to_account_id,
        )
        if from_account is None or to_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both accounts not found",
            )
        if from_account["balance"] < payload.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient funds in the source account",
            )
        transfer_operations = [
            (payload.from_account_id, -payload.amount, TransactionType.WITHDRAWAL),
            (payload.to_account_id, payload.amount, TransactionType.DEPOSIT),
        ]

        transactions: list[Record] = []
        for account_id, balance_change, txn_type in transfer_operations:
            _ = await conn.execute(
                "UPDATE accounts SET balance = balance + $1 WHERE id = $2",
                balance_change,
                account_id,
            )
            row = await conn.fetchrow(
                """
                INSERT INTO transactions (account_id, amount, transaction_type)
                VALUES ($1, $2, $3)
                RETURNING id, account_id, amount, transaction_type
                """,
                account_id,
                payload.amount,
                txn_type.value,
            )
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create transfer transaction",
                )
            transactions.append(row)

    return {
        "from": Transaction.model_validate(dict(transactions[0])),
        "to": Transaction.model_validate(dict(transactions[1])),
    }


@router.get("/account/{account_id}", response_model=list[Transaction])
async def get_transactions_by_account(
    account_id: int,
    conn: Annotated[Connection, Depends(get_conn)],
) -> list[Transaction]:
    """Get all transactions for a specific account.

    account_id : int
        The ID of the account to retrieve transactions for.

    Returns:
        list[Transaction]
            A list of transactions associated with the account.
    """
    rows = await conn.fetch(
        """
        SELECT id, account_id, amount, transaction_type
        FROM transactions
        WHERE account_id = $1
        ORDER BY id DESC
        """,
        account_id,
    )

    return [Transaction.model_validate(dict(row)) for row in rows]
