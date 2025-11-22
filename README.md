# Local Setup

## Requirements

-   **Python v14**

-   **Docker + Docker Compose**

-   **uv** (Python project manager)

-   **psql CLI**\
    Install with:

    ``` bash
    brew install postgresql
    ```

------------------------------------------------------------------------

## Setup Instructions

### 1. Clone the repository

``` bash
git clone <repo>
cd bank-system
```

### 2. Configure environment variables

``` bash
cp .env.example .env
```

### 3. Start PostgreSQL

``` bash
make db-up
```

### 4. Run database migrations

``` bash
make db-migrate
```

### 5. Install dependencies

``` bash
uv sync
```

### 6. Run the API

``` bash
uv run uvicorn bank_system.main:app --reload
```

------------------------------------------------------------------------

## API Documentation

http://localhost:8000/docs
