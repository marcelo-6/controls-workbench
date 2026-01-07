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
