## Local setup

Requirements:
- Python v14
- Docker + Docker Compose
- uv (Python project manager)
- psql CLI (`brew install postgresql`)


git clone <repo>
cd bank-system

1. Configure environment
cp .env.example .env


2. Start PostgreSQL
make db-up

3. Run migrations
make db-migrate

3. Install dependencies
uv sync

4. Run the API
uv run uvicorn bank_system.main:app --reload


API docs: http://localhost:8000/docs