from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bank_system.api.auth import router as auth_router
from bank_system.api.users import router as user_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(user_router)
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


async def test__register__returns_created(unauthed_client: AsyncClient):
    response = await unauthed_client.post(
        "/auth/register", json={"username": "some-test-user", "password": "testpass"}
    )
    assert response.status_code == HTTPStatus.CREATED, response.text


async def test__register__duplicate_username(
    unauthed_client: AsyncClient, created_user: UserCredentials
):
    response = await unauthed_client.post(
        "/auth/register",
        json={"username": created_user.username, "password": "testpass2"},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


async def test__get_user__not_found(client: AsyncClient):
    get_response = await client.get("/users/nonexistentuser")
    assert get_response.status_code == HTTPStatus.NOT_FOUND


async def test__get_user__returns_user(
    client: AsyncClient, created_user: UserCredentials
):
    get_response = await client.get(f"/users/{created_user.username}")
    assert get_response.status_code == HTTPStatus.OK


async def test__get_user__unauthenticated(unauthed_client: AsyncClient):
    get_response = await unauthed_client.get("/users/someuser")
    assert get_response.status_code == HTTPStatus.UNAUTHORIZED


async def test__me__returns_current_user(
    client: AsyncClient, created_user: UserCredentials
):
    response = await client.get("/auth/me")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["username"] == created_user.username


async def test__me__unauthenticated(unauthed_client: AsyncClient):
    response = await unauthed_client.get("/auth/me")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
