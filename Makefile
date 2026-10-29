.PHONY: sync quality test case0 tree dev dev-down api worker web

sync:
	uv sync --all-groups

quality:
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check

test:
	uv run pytest

case0:
	uv run --package space-pv-cli space-pv case0 --demo

dev:
	docker compose up --build

dev-down:
	docker compose down

api:
	uv run --package space-pv-api uvicorn space_pv_api.main:app --reload

worker:
	uv run --package space-pv-orchestration celery -A space_pv_orchestration.celery_app:celery_app worker -l INFO -Q celery,analytics,ingestion,orbit,pv

web:
	cd apps/space-pv-web && npm install && npm run dev

tree:
	find . -maxdepth 4 -not -path './.git/*' | sort
