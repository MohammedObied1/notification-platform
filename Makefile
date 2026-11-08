.PHONY: install dev test lint format migrate docker-up docker-down frontend-install frontend-dev frontend-build

install:
	pip install -r requirements-dev.txt

dev:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check app tests

format:
	ruff format app tests && ruff check --fix app tests

migrate:
	alembic upgrade head

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
