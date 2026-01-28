## Purpose and Scope
- A minimal FastAPI + PostgreSQL bank backend supporting user auth, account lifecycle, deposits, withdrawals, transfers, and transaction history. Authentication uses HTTP Basic (username/password) checked per request to scope account access.


### Key Features
- User registration and authentication using HTTP Basic Auth
- Multiple accounts per user
- Deposit and withdrawal operations
- Inter-account transfers with balance validation
- Transaction history retrieval
- Complete authorization and ownership checks


### Technology Stack
- **FastAPI**: Modern, fast web framework for building APIs
- **asyncpg**: High-performance PostgreSQL database driver
- **PostgreSQL**: Reliable ACID-compliant relational database
- **Pydantic**: Data validation using Python type annotations
- **bcrypt**: Secure password hashing
- **pytest + httpx**: Comprehensive async testing framework

## Setup and Installation
- Prereqs: Python 3.14+ with `uv`, Docker + Docker Compose, `psql`.
- Configure env: `cp .env.example .env` and adjust DB credentials/ports as needed.
- Start infra: `make db-up` to boot PostgreSQL, then `make db-migrate` to apply migrations.
- Install deps: `uv sync` then `uv pip install -e .` to install the app in editable mode.
- Run API: `make api` (serves on http://localhost:8000; OpenAPI at `/docs`).
- Tests: `pytest` (uses in-memory ASGI client; no external DB writes).

## How to Use the API
Authentication
All endpoints except /auth/register require HTTP Basic Authentication.
- Register: `POST /auth/register` with `{"username":"u","password":"p"}`.
- Authenticate: pass HTTP Basic credentials (`u:p`) on subsequent calls.
- Accounts:
  - `POST /accounts/` creates an account for the authenticated user.
  - `GET /accounts/` lists the user’s accounts; `GET /accounts/{id}` fetches one.
- Transactions:
  - `POST /transactions/deposit` `{account_id, amount>0}` adds funds to owned account.
  - `POST /transactions/withdrawal` `{account_id, amount>0}` subtracts funds; 400 if insufficient balance.
  - `POST /transactions/transfer` `{from, to, amount>0}` moves funds between distinct accounts; validates ownership of `from` and existence of `to`.
  - `GET /transactions/account/{id}` returns chronological transactions for an owned account.
- Error model: 401 for missing/invalid auth, 404 for missing resources, 400 for business rule violations (e.g., insufficient funds), 422 for schema/validation errors (e.g., non-positive amount).

## Code Documentation Highlights
- Pydantic models document request/response shapes (`CreateTransactionRequest`, `CreateTransferRequest`, `Transaction`, `CreateAccountResponse`).
- Inline docstrings describe each router’s responsibility and validation rules (auth, users, accounts, transactions).
- Validation enforced via Annotated/Pydantic constraints (e.g., positive `amount`, distinct transfer accounts) keeps API contracts explicit and auto-documented in OpenAPI.

## Transaction Safety and Race Condition Prevention
Critical Design Pattern:
All financial operations use atomic SQL queries with Common Table Expressions (CTEs) to prevent race conditions:
``` bash
WITH authorization_check AS (
    -- Verify user owns the account
    SELECT 1 FROM accounts a
    JOIN users u ON a.user_id = u.id
    WHERE a.id = $1 AND u.username = $2
),
account_update AS (
    -- Update balance only if authorized
    UPDATE accounts
    SET balance = balance + $3
    WHERE id = $1 AND EXISTS (SELECT 1 FROM authorization_check)
    RETURNING id, balance
),
transaction_record AS (
    -- Record transaction only if update succeeded
    INSERT INTO transactions (from_account_id, to_account_id, amount)
    SELECT $1, $2, $3
    WHERE EXISTS (SELECT 1 FROM account_update)
    RETURNING id
)
SELECT * FROM account_update
```
Why This Matters:

Atomicity: All operations (check, update, record) happen in a single transaction
No TOCTOU: Time-of-check to time-of-use vulnerabilities eliminated
Consistency: Transaction records only created for successful operations
Isolation: PostgreSQL's MVCC ensures concurrent transactions don't interfere


## Design Decisions and Rationale
- FastAPI for async-first request handling and automatic OpenAPI generation; pairs well with Pydantic v2 for schema validation.
- asyncpg for low-latency PostgreSQL access; explicit SQL keeps control over locking and balance updates.
- HTTP Basic chosen for simplicity; credential verification occurs on every endpoint to scope queries per user.
- Transactional SQL blocks wrap balance mutations to ensure atomic deposits/withdrawals/transfers; business rules (ownership, sufficient funds) enforced in SQL plus Python guards.
- Tests use FastAPI’s ASGI transport + httpx AsyncClient to run quickly without network calls, mirroring real request flows.
- Trade-offs: Basic auth is not suitable for production (prefer OAuth/JWT); no rate limiting or multi-currency support; optimistic concurrency relies on SQL updates without explicit row locking beyond transaction scope.
