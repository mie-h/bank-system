"""Authentication utilities for the bank system API."""

from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

# In-memory user storage (username -> hashed_password)
# Data will be cleared when the app restarts
_users: dict[str, str] = {}


def clear_users():
    """Clear in-memory user storage."""
    _users.clear()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def register_user(username: str, password: str) -> None:
    """Register a new user in memory.

    Args:
        username: The username to register.
        password: The plain text password.

    Raises:
        ValueError: If username already exists.
    """
    if username in _users:
        msg = "Username already exists"
        raise ValueError(msg)

    _users[username] = hash_password(password)


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> str:
    """Verify HTTP Basic Auth credentials.

    Args:
        credentials: The HTTP Basic Auth credentials from the request.

    Returns:
        The authenticated username.

    Raises:
        HTTPException: If credentials are invalid.
    """
    username = credentials.username
    password = credentials.password

    if username not in _users:
        # User not found - hash a dummy password to prevent timing attacks
        bcrypt.checkpw(b"dummy", bcrypt.gensalt())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    if not verify_password(password, _users[username]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return username
