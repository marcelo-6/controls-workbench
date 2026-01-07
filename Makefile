.PHONY: lint format test changelog precommit release bump-version update-backend update-frontend changelog-gen commit-all tag

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

# Auto-bump version using git-cliff unless overridden
RAW_VERSION := $(shell git-cliff --bumped-version 2>/dev/null)
VERSION ?= $(RAW_VERSION)
DRY_RUN ?= 0

check = $(shell echo "RAW_VERSION $(RAW_VERSION)")

FRONTEND_DIR = frontend
BACKEND_DIR = backend
BACKEND_FILE = $(BACKEND_DIR)/pyproject.toml
FRONTEND_FILE = $(FRONTEND_DIR)/package.json

# Validate version format (must look like 1.2.3)
VALID_VERSION = $(shell echo "$(VERSION)" | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$$' || true)

# Escape version for sed
ESCAPED_VERSION = $(shell printf '%s\n' "v$(VERSION)" | sed 's/[&/\]/\\&/g')

define run
	@if [ "$(DRY_RUN)" = "1" ]; then \
		echo "[DRY RUN] $(1)"; \
	else \
		sh -c "$(1)"; \
	fi
endef

release: bump-version update-backend update-frontend changelog-gen commit-all tag
	@echo "Release $(VERSION) completed."

# ----------------------------------------
# 1. Version bump (auto or forced)
# ----------------------------------------
bump-version:
	@if [ -z "$(VALID_VERSION)" ]; then \
		echo "ERROR: Invalid version detected: '$(VERSION)'"; \
		echo "git cliff --bump probably failed."; \
		exit 1; \
	fi
	@echo "Using version: $(VERSION)"
	@if [ "$(DRY_RUN)" = "1" ]; then echo "[DRY RUN] Version bump only simulated"; fi

# ----------------------------------------
# 2. Update backend version (pyproject.toml)
# ----------------------------------------
update-backend:
	@echo "Updating backend version in $(BACKEND_FILE)"
	$(call run, sed -i 's/^version = ".*"/version = "$(ESCAPED_VERSION)"/' $(BACKEND_FILE))

# ----------------------------------------
# 3. Update frontend version (package.json)
# ----------------------------------------
update-frontend:
	@echo "Updating frontend version in $(FRONTEND_FILE)"
	$(call run, sed -i 's/"version": *".*"/"version": "$(ESCAPED_VERSION)"/' $(FRONTEND_FILE))
# ----------------------------------------
# 4. Generate changelog
# ----------------------------------------
changelog-gen:
	@echo "Generating changelog..."
	$(call run, git cliff -o CHANGELOG.md)

# ----------------------------------------
# 5. Commit all changes
# ----------------------------------------
commit-all:
	$(call run, git add .)
	$(call run, git commit -m "chore: release v$(VERSION)" || echo "Nothing to commit.")

# ----------------------------------------
# 6. Tag the release
# ----------------------------------------
tag:
	$(call run, git tag v$(VERSION))
	$(call run, git push)
	$(call run, git push --tags)