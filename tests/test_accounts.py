from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bank_system.api.accounts import router as accounts_router
from bank_system.api.auth import router as auth_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(accounts_router)
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


async def test__create_account__success(
    client: AsyncClient,
) -> None:
    response = await client.post("/accounts/")
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert "id" in data


async def test__create_account__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    response = await unauthed_client.post("/accounts/")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test__create_account__multiple_accounts(
    client: AsyncClient,
) -> None:
    response1 = await client.post("/accounts/")
    assert response1.status_code == HTTPStatus.CREATED
    response2 = await client.post("/accounts/")
    assert response2.status_code == HTTPStatus.CREATED
    data1 = response1.json()
    data2 = response2.json()
    assert data1["id"] != data2["id"]


async def test__get_account__success(
    client: AsyncClient,
) -> None:
    create_response = await client.post("/accounts/")
    assert create_response.status_code == HTTPStatus.CREATED
    account_id = create_response.json()["id"]

    get_response = await client.get(f"/accounts/{account_id}")
    assert get_response.status_code == HTTPStatus.OK
    data = get_response.json()
    assert data["id"] == account_id


async def test__get_account__not_found(
    client: AsyncClient,
) -> None:
    get_response = await client.get("/accounts/9999")
    assert get_response.status_code == HTTPStatus.NOT_FOUND


async def test__get_account__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    get_response = await unauthed_client.get("/accounts/1")
    assert get_response.status_code == HTTPStatus.UNAUTHORIZED


async def test__get_accounts__gets_multiple(
    client: AsyncClient,
) -> None:
    num_accounts = 2
    for _ in range(num_accounts):
        _ = await client.post("/accounts/")

    get_response = await client.get("/accounts/")

    assert get_response.status_code == HTTPStatus.OK
    data = get_response.json()
    assert isinstance(data, list)
    assert len(data) >= num_accounts  # At least the two we just created


async def test__get_accounts__unauthenticated(
    unauthed_client: AsyncClient,
) -> None:
    get_response = await unauthed_client.get("/accounts/")
    assert get_response.status_code == HTTPStatus.UNAUTHORIZED


async def test__get_accounts__no_accounts(
    client: AsyncClient,
) -> None:
    get_response = await client.get("/accounts/")
    assert get_response.status_code == HTTPStatus.OK
    data = get_response.json()
    assert isinstance(data, list)
    assert len(data) == 0


async def test__create_account__duplicate_account(
    client: AsyncClient,
) -> None:
    response1 = await client.post("/accounts/")
    assert response1.status_code == HTTPStatus.CREATED
    response2 = await client.post("/accounts/")
    assert response2.status_code == HTTPStatus.CREATED
    data1 = response1.json()
    data2 = response2.json()
    assert data1["id"] != data2["id"]
