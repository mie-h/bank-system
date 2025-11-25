"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    database_url: str = "postgresql://bank:bankpassword@localhost:5433/bank_db"

    # TODO(Mie): I don't get this error
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BANK_",
    )
