import os
import shutil
import subprocess
from typing import TYPE_CHECKING, cast

import pytest
from testing.postgresql import (  # pyright: ignore[reportMissingTypeStubs]
    Postgresql,
    PostgresqlFactory,
)

from bank_system.db import lifespan

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def database_factory(pytestconfig: pytest.Config) -> Callable[[], Postgresql]:
    def run_migrations(db: Postgresql):
        migration_loc = pytestconfig.rootpath / "migrations"
        flyway = shutil.which("flyway")
        assert flyway is not None

        params = db.dsn()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        try:
            _ = subprocess.run(
                [
                    flyway,
                    f"-url=jdbc:postgresql://{params['host']}:{params['port']}/{params['database']}",
                    f"-user={params['user']}",
                    f"-locations=filesystem:{migration_loc}",
                    "migrate",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print("--- Flyway stdout ---")  # noqa: T201
            print(cast(str, e.stdout))  # noqa: T201
            print("--- Flyway stderr ---")  # noqa: T201
            print(cast(str, e.stderr))  # noqa: T201
            print("---------------------")  # noqa: T201
            raise

    return PostgresqlFactory(cache_initialized_db=True, on_initialized=run_migrations)


@pytest.fixture(autouse=True)
async def database(database_factory: Callable[[], Postgresql]):
    pg = database_factory()
    os.environ["BANK_DATABASE_URL"] = pg.url()  # pyright: ignore[reportUnknownMemberType]
    print(pg.url())  # pyright: ignore[reportUnknownMemberType] # noqa: T201
    async with lifespan():
        yield pg
    pg.stop()
