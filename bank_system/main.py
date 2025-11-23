"""Main application module for the bank system.

This module provides the FastAPI application instance and configures
all API routers for users, accounts, and transactions.
"""

from fastapi import FastAPI

from bank_system.api.accounts import router as accounts_router
from bank_system.api.transactions import router as transactions_router
from bank_system.api.users import router as user_router

app = FastAPI()


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True}


app.include_router(user_router)
app.include_router(accounts_router)
app.include_router(transactions_router)
