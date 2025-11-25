from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bank_system.api.accounts import router as accounts_router
from bank_system.api.auth import router as auth_router
from bank_system.api.transactions import router as transactions_router
from bank_system.api.users import router as user_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(accounts_router)
    app.include_router(transactions_router)
    return app


@pytest.fixture
async def unauthed_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@dataclass
class UserCredentials:
    username: str
    password: str


@pytest.fixture
async def created_user(unauthed_client: AsyncClient) -> UserCredentials:
    username = "testuser"
    password = "testpass"  # noqa: S105
    response = await unauthed_client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert response.status_code == HTTPStatus.CREATED
    return UserCredentials(username=username, password=password)


@pytest.fixture
async def client(
    app: FastAPI, created_user: UserCredentials
) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url=f"http://{created_user.username}:{created_user.password}@test",
    ) as ac:
        yield ac


async def test__create_deposit__success(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    response = await client.post(
        "/transactions/deposit", json={"account_id": account_id, "amount": 100.0}
    )
    assert response.status_code == HTTPStatus.CREATED


async def test__create_deposit__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    response = await unauthed_client.post(
        "/transactions/deposit", json={"account_id": 1, "amount": 100.0}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test__create_deposit__invalid_account(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/transactions/deposit", json={"account_id": 9999, "amount": 100.0}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test__create_deposit__negative_amount(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    response = await client.post(
        "/transactions/deposit", json={"account_id": account_id, "amount": -50.0}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__create_deposit__zero_amount(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    response = await client.post(
        "/transactions/deposit", json={"account_id": account_id, "amount": 0.0}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__create_withdrawal__success(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    # Deposit some funds first
    deposit_response = await client.post(
        "/transactions/deposit", json={"account_id": account_id, "amount": 200.0}
    )
    assert deposit_response.status_code == HTTPStatus.CREATED

    # Now withdraw funds
    withdrawal_response = await client.post(
        "/transactions/withdrawal", json={"account_id": account_id, "amount": 150.0}
    )
    assert withdrawal_response.status_code == HTTPStatus.CREATED


async def test__create_withdrawal__insufficient_funds(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    # Deposit some funds first
    deposit_response = await client.post(
        "/transactions/deposit", json={"account_id": account_id, "amount": 100.0}
    )
    assert deposit_response.status_code == HTTPStatus.CREATED

    # Now attempt to withdraw more than the balance
    withdrawal_response = await client.post(
        "/transactions/withdrawal", json={"account_id": account_id, "amount": 150.0}
    )
    assert withdrawal_response.status_code == HTTPStatus.BAD_REQUEST


async def test__create_withdrawal__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    response = await unauthed_client.post(
        "/transactions/withdrawal", json={"account_id": 1, "amount": 50.0}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test__create_withdrawal__invalid_account(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/transactions/withdrawal", json={"account_id": 9999, "amount": 50.0}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test__create_withdrawal__negative_amount(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    response = await client.post(
        "/transactions/withdrawal", json={"account_id": account_id, "amount": -20.0}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__create_withdrawal__zero_amount(
    client: AsyncClient,
) -> None:
    # First create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    response = await client.post(
        "/transactions/withdrawal", json={"account_id": account_id, "amount": 0.0}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__create_transfer__success(
    client: AsyncClient,
) -> None:
    # Create source account
    source_response = await client.post("/accounts/")
    assert source_response.status_code == HTTPStatus.CREATED
    source_account_id = source_response.json()["id"]

    # Create destination account
    dest_response = await client.post("/accounts/")
    assert dest_response.status_code == HTTPStatus.CREATED
    dest_account_id = dest_response.json()["id"]

    # Deposit funds into source account
    deposit_response = await client.post(
        "/transactions/deposit", json={"account_id": source_account_id, "amount": 300.0}
    )
    assert deposit_response.status_code == HTTPStatus.CREATED

    # Transfer funds from source to destination
    transfer_response = await client.post(
        "/transactions/transfer",
        json={
            "from": source_account_id,
            "to": dest_account_id,
            "amount": 200.0,
        },
    )
    assert transfer_response.status_code == HTTPStatus.CREATED


async def test__create_transfer__insufficient_funds(
    client: AsyncClient,
) -> None:
    # Create source account
    source_response = await client.post("/accounts/")
    assert source_response.status_code == HTTPStatus.CREATED
    source_account_id = source_response.json()["id"]

    # Create destination account
    dest_response = await client.post("/accounts/")
    assert dest_response.status_code == HTTPStatus.CREATED
    dest_account_id = dest_response.json()["id"]

    # Deposit funds into source account
    deposit_response = await client.post(
        "/transactions/deposit", json={"account_id": source_account_id, "amount": 100.0}
    )
    assert deposit_response.status_code == HTTPStatus.CREATED

    # Attempt to transfer more funds than available
    transfer_response = await client.post(
        "/transactions/transfer",
        json={
            "from": source_account_id,
            "to": dest_account_id,
            "amount": 150.0,
        },
    )
    assert transfer_response.status_code == HTTPStatus.BAD_REQUEST


async def test__create_transfer__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    response = await unauthed_client.post(
        "/transactions/transfer",
        json={"from": 1, "to": 2, "amount": 50.0},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test__create_transfer__invalid_account(
    client: AsyncClient,
) -> None:
    # Create source account
    source_response = await client.post("/accounts/")
    assert source_response.status_code == HTTPStatus.CREATED
    source_account_id = source_response.json()["id"]

    # Attempt to transfer to a non-existent destination account
    transfer_response = await client.post(
        "/transactions/transfer",
        json={
            "from": source_account_id,
            "to": 9999,
            "amount": 50.0,
        },
    )
    assert transfer_response.status_code == HTTPStatus.NOT_FOUND


async def test__create_transfer__negative_amount(
    client: AsyncClient,
) -> None:
    # Create source account
    source_response = await client.post("/accounts/")
    assert source_response.status_code == HTTPStatus.CREATED
    source_account_id = source_response.json()["id"]

    # Create destination account
    dest_response = await client.post("/accounts/")
    assert dest_response.status_code == HTTPStatus.CREATED
    dest_account_id = dest_response.json()["id"]

    response = await client.post(
        "/transactions/transfer",
        json={
            "from": source_account_id,
            "to": dest_account_id,
            "amount": -30.0,
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__create_transfer__zero_amount(
    client: AsyncClient,
) -> None:
    # Create source account
    source_response = await client.post("/accounts/")
    assert source_response.status_code == HTTPStatus.CREATED
    source_account_id = source_response.json()["id"]

    # Create destination account
    dest_response = await client.post("/accounts/")
    assert dest_response.status_code == HTTPStatus.CREATED
    dest_account_id = dest_response.json()["id"]

    response = await client.post(
        "/transactions/transfer",
        json={
            "from": source_account_id,
            "to": dest_account_id,
            "amount": 0.0,
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__create_transfer__same_account(
    client: AsyncClient,
) -> None:
    # Create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    response = await client.post(
        "/transactions/transfer",
        json={
            "from": account_id,
            "to": account_id,
            "amount": 50.0,
        },
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test__get_transactions__success(
    client: AsyncClient,
) -> None:
    # Create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    # Deposit some funds
    deposit_response = await client.post(
        "/transactions/deposit", json={"account_id": account_id, "amount": 150.0}
    )
    assert deposit_response.status_code == HTTPStatus.CREATED

    # Retrieve transactions
    transactions_response = await client.get(f"/transactions/account/{account_id}")
    assert transactions_response.status_code == HTTPStatus.OK
    data = transactions_response.json()
    assert isinstance(data, list)
    assert len(data) >= 1  # At least one transaction should exist


async def test__get_transactions__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    response = await unauthed_client.get("/transactions/account/1")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test__get_transactions__invalid_account(
    client: AsyncClient,
) -> None:
    response = await client.get("/transactions/account/9999")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test__get_transactions__no_transactions(
    client: AsyncClient,
) -> None:
    # Create an account
    account_response = await client.post("/accounts/")
    assert account_response.status_code == HTTPStatus.CREATED
    account_id = account_response.json()["id"]

    # Retrieve transactions for the new account (should be none)
    transactions_response = await client.get(f"/transactions/account/{account_id}")
    assert transactions_response.status_code == HTTPStatus.OK
    data = transactions_response.json()
    assert isinstance(data, list)
    assert len(data) == 0  # No transactions should exist yet
