.PHONY: db-up api

db-up:
	 docker compose up -d db

db-migrate:
	 docker compose run --rm flyway

api:
	 uv run uvicorn bank_system.main:app --reload


