.PHONY: lint format test changelog precommit

lint:
	cd backend && uv run ruff check .

format:
	cd backend && uv run ruff format .

test:
	cd backend && uv run pytest

precommit:
	cd backend && uv run pre-commit run --all-files

changelog:
	git-cliff -o CHANGELOG.md

up:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

build:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache 

up-prod:
	docker compose up --build

zip:
	zip -r controls-workbench-src.zip . -x "*/.git/*" "*/.venv/*" "*/node_modules/*" "*/data/*" "*/dist/*" "*/build/*" "*/__pycache__/*"
