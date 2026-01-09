###############################################################################
# Controls Workbench - Makefile
#
# Goals:
# - One command release flow: bump versions (backend+frontend) + generate changelog
#   + commit "Release version X.Y.Z" + tag "vX.Y.Z"
# - pnpm as the frontend package manager
# - uv for backend tooling
# - Helpful "Langflow-ish" targets: check-tools, clean_all, etc.
#
# Common commands:
#   make init
#   make lint
#   make format
#   make test
#   make precommit
#   make changelog
#   make release
#   make push-release
#
# Release notes:
# - Backend/Frontend files store versions WITHOUT the leading "v" (e.g. 0.0.8)
# - Git tag IS prefixed with "v" (e.g. v0.0.8)
###############################################################################

.ONESHELL:
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
# Silence "Entering/Leaving directory ..." for recursive make calls
MAKEFLAGS += --no-print-directory

# ----------------------------
# Paths
# ----------------------------
BACKEND_DIR    := backend
FRONTEND_DIR   := frontend
BACKEND_FILE   := $(BACKEND_DIR)/pyproject.toml
FRONTEND_FILE  := $(FRONTEND_DIR)/package.json
CHANGELOG_FILE := CHANGELOG.md

# ----------------------------
# Tools (override if needed)
# ----------------------------
PY        ?= python3
UV        ?= uv
PNPM      ?= pnpm
GIT_CLIFF ?= git-cliff

# ----------------------------
# UX / Colors
# ----------------------------
RED    := \033[0;31m
GREEN  := \033[0;32m
YELLOW := \033[1;33m
CYAN   := \033[0;36m
NC     := \033[0m

# ----------------------------
# Release knobs
# ----------------------------
DRY_RUN ?= 0

# Auto-bumped version from git-cliff unless overridden:
RAW_BUMPED_VERSION := $(shell $(GIT_CLIFF) --bumped-version 2>/dev/null || true)
VERSION ?= $(RAW_BUMPED_VERSION)

# Normalize VERSION:
# - allow VERSION=v1.2.3 or VERSION=1.2.3
NORMALIZED_VERSION := $(patsubst v%,%,$(patsubst V%,%,$(VERSION)))
TAG := v$(NORMALIZED_VERSION)

# Validate normalized version format: 1.2.3
VALID_VERSION := $(shell echo "$(NORMALIZED_VERSION)" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$$' || true)

# ----------------------------
# Helpers
# ----------------------------
define RUN
@if [ "$(DRY_RUN)" = "1" ]; then \
	echo "[DRY RUN] $(1)"; \
else \
	$(1); \
fi
endef

define REQUIRE_CMD
@command -v $(1) >/dev/null 2>&1 || { echo -e "$(RED)ERROR: Missing required tool: $(1)$(NC)"; exit 1; }
endef

define REQUIRE_OK
	@$(1) >/dev/null 2>&1 || { echo -e "$(RED)ERROR: $(2)$(NC)"; exit 1; }
endef


# ----------------------------
# Phony targets
# ----------------------------
.PHONY: help \
	check-tools check-tools-release check-clean show-version next-version \
	init install-backend install-frontend \
	lint format test precommit changelog \
	up build up-prod zip \
	clean_python_cache clean_pnpm_cache clean_frontend_build clean_all \
	bump-version update-backend-version update-frontend-version update-versions \
	commit-release tag-release release push-release

# ----------------------------
# Help
# ----------------------------
help: ## Show available commands
	@printf "\n$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)\n"
	@printf "$(GREEN)                  CONTROLS WORKBENCH MAKE COMMANDS                  $(NC)\n"
	@printf "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)\n\n"
	@printf "$(CYAN)Targets:$(NC)\n"
	@awk 'BEGIN{FS=":.*##"} /^[a-zA-Z0-9_.-]+:.*##/{printf "  \033[0;32m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\n$(CYAN)Examples:$(NC)\n"
	@printf "  make release\n"
	@printf "  make release VERSION=0.0.8\n"
	@printf "  make release DRY_RUN=1\n\n"

# ----------------------------
# Tool checks
# ----------------------------
check-tools: ## Check common dev tools (must be runnable, not just present)
	$(call REQUIRE_CMD,git)
	$(call REQUIRE_CMD,$(PY))
	$(call REQUIRE_CMD,$(UV))

	$(call REQUIRE_OK,$(UV) --version,uv is installed but not runnable)

	# Node must be runnable in WSL (pnpm depends on it)
	$(call REQUIRE_CMD,node)
	$(call REQUIRE_OK,node --version,node is installed but not runnable)

	# pnpm must be runnable (not just found on PATH)
	$(call REQUIRE_CMD,$(PNPM))
	$(call REQUIRE_OK,$(PNPM) --version,pnpm is found but fails to run (often because node is missing in WSL))

	@printf "$(GREEN)OK: git, python, uv, node, pnpm$(NC)\n"

	@command -v docker >/dev/null 2>&1 && printf "$(GREEN)OK: docker$(NC)\n" || printf "$(YELLOW)WARN: docker not found (only needed for make up/build)$(NC)\n"
	@command -v zip >/dev/null 2>&1 && printf "$(GREEN)OK: zip$(NC)\n" || printf "$(YELLOW)WARN: zip not found (only needed for make zip)$(NC)\n"

check-tools-release: ## Check tools required for release flow
	$(call REQUIRE_CMD,git)
	$(call REQUIRE_CMD,$(PY))
	$(call REQUIRE_CMD,$(UV))
	$(call REQUIRE_CMD,$(GIT_CLIFF))

	$(call REQUIRE_OK,$(UV) --version,uv is installed but not runnable)
	$(call REQUIRE_OK,$(GIT_CLIFF) --version,git-cliff is installed but not runnable)

	# Release updates frontend version too, so ensure node+pnpm actually run
	$(call REQUIRE_CMD,node)
	$(call REQUIRE_OK,node --version,node is installed but not runnable)

	$(call REQUIRE_CMD,$(PNPM))
	$(call REQUIRE_OK,$(PNPM) --version,pnpm is found but fails to run (often because node is missing in WSL))

	@printf "$(GREEN)OK: release tooling present (git, python, uv, git-cliff, node, pnpm)$(NC)\n"


check-clean: ## Ensure git working tree is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		printf "$(RED)ERROR: Working tree not clean. Commit or stash before release.$(NC)\n"; \
		git status --porcelain; \
		exit 1; \
	fi

show-version: ## Print computed VERSION / TAG
	@printf "VERSION=%s\n" "$(VERSION)"
	@printf "NORMALIZED_VERSION=%s\n" "$(NORMALIZED_VERSION)"
	@printf "TAG=%s\n" "$(TAG)"

next-version: check-tools-release ## Show version git-cliff would bump to
	@if [ -z "$(RAW_BUMPED_VERSION)" ]; then \
		printf "$(YELLOW)git-cliff did not return a bumped version. Check git-cliff config / commit conventions.$(NC)\n"; \
		exit 1; \
	fi
	@printf "Next version: %s\n" "$(RAW_BUMPED_VERSION)"

# ----------------------------
# Install
# ----------------------------
init: check-tools ## Install backend + frontend deps
	@$(MAKE) install-backend
	@$(MAKE) install-frontend
	@printf "$(GREEN)Dependencies installed.$(NC)\n"

install-backend: ## Install backend deps (uv)
	@printf "Installing backend dependencies...\n"
	$(call RUN,cd $(BACKEND_DIR) && $(UV) sync --frozen)

install-frontend: ## Install frontend deps (pnpm)
	@printf "Installing frontend dependencies...\n"
	$(call RUN,cd $(FRONTEND_DIR) && $(PNPM) install --frozen-lockfile)

# ----------------------------
# Quality
# ----------------------------
lint: ## Ruff lint (backend)
	$(call RUN,cd $(BACKEND_DIR) && $(UV) run ruff check .)

format: ## Ruff format (backend)
	$(call RUN,cd $(BACKEND_DIR) && $(UV) run ruff format .)

test: ## Pytest (backend)
	$(call RUN,cd $(BACKEND_DIR) && $(UV) run pytest)

precommit: ## pre-commit (backend env)
	$(call RUN,cd $(BACKEND_DIR) && $(UV) run pre-commit run --all-files)

# ----------------------------
# Changelog
# ----------------------------
changelog: check-tools-release ## Generate CHANGELOG.md using git-cliff
	@printf "$(GREEN)Generating changelog...$(NC)\n"
	$(call RUN,$(GIT_CLIFF) -o $(CHANGELOG_FILE))

# ----------------------------
# Docker / Packaging
# ----------------------------
up: ## docker compose up (dev overrides)
	$(call RUN,docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build)

build: ## docker compose build (dev overrides, no cache)
	$(call RUN,docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache)

up-prod: ## docker compose up (prod)
	$(call RUN,docker compose up --build)

zip: ## Zip source tree (excluding common junk)
	$(call RUN,zip -r controls-workbench-src.zip . \
		-x "*/.git/*" "*/.venv/*" "*/node_modules/*" "*/data/*" "*/dist/*" "*/build/*" "*/__pycache__/*")

# ----------------------------
# Clean
# ----------------------------
clean_python_cache: ## Remove python cache/bytecode
	@printf "Cleaning Python caches...\n"
	$(call RUN,find . -type d -name '__pycache__' -exec rm -rf {} +)
	$(call RUN,find . -type f -name '*.py[cod]' -delete)
	$(call RUN,find . -type d -name '.mypy_cache' -exec rm -rf {} +)
	$(call RUN,find . -type d -name '.pytest_cache' -exec rm -rf {} +)
	@printf "$(GREEN)Python caches cleaned.$(NC)\n"

clean_pnpm_cache: ## Prune pnpm store + remove node_modules
	@printf "Cleaning pnpm artifacts...\n"
	$(call RUN,cd $(FRONTEND_DIR) && $(PNPM) store prune)
	$(call RUN,rm -rf $(FRONTEND_DIR)/node_modules)
	@printf "$(GREEN)pnpm store pruned + node_modules removed.$(NC)\n"

clean_frontend_build: ## Remove frontend build outputs
	@printf "Cleaning frontend build outputs...\n"
	$(call RUN,rm -rf $(FRONTEND_DIR)/dist)
	$(call RUN,rm -rf $(FRONTEND_DIR)/build)
	@printf "$(GREEN)Frontend build outputs cleaned.$(NC)\n"

clean_all: clean_python_cache clean_pnpm_cache clean_frontend_build ## Clean everything dev-generated
	@printf "$(GREEN)All caches/build outputs cleaned.$(NC)\n"

# ----------------------------
# Release flow
# ----------------------------
bump-version: check-tools-release ## Validate release version and ensure tag doesn't already exist
	@if [ -z "$(VERSION)" ]; then \
		printf "$(RED)ERROR: VERSION is empty. Provide VERSION=1.2.3 or fix git-cliff config.$(NC)\n"; \
		exit 1; \
	fi
	@if [ -z "$(VALID_VERSION)" ]; then \
		printf "$(RED)ERROR: Invalid version '%s' (normalized: '%s'). Expected 1.2.3$(NC)\n" "$(VERSION)" "$(NORMALIZED_VERSION)"; \
		exit 1; \
	fi
	@if git rev-parse -q --verify "refs/tags/$(TAG)" >/dev/null; then \
		printf "$(RED)ERROR: Tag %s already exists.$(NC)\n" "$(TAG)"; \
		exit 1; \
	fi
	@printf "Release version: %s  (tag: %s)\n" "$(NORMALIZED_VERSION)" "$(TAG)"

update-backend-version: ## Update backend/pyproject.toml version (uv if available; python fallback)
	@printf "Updating backend version -> %s\n" "$(NORMALIZED_VERSION)"
	$(call RUN,cd $(BACKEND_DIR) && { \
		$(UV) version $(NORMALIZED_VERSION) >/dev/null 2>&1 || \
		$(UV) version --set $(NORMALIZED_VERSION) >/dev/null 2>&1 || \
		$(PY) -c "import re,sys,pathlib; p=pathlib.Path('pyproject.toml'); v=sys.argv[1]; t=p.read_text(encoding='utf-8'); new,n=re.subn(r'(?m)^(version\\s*=\\s*\\\")[^\\\"]*(\\\")', lambda m: m.group(1)+v+m.group(2), t, count=1); (n==1) or (_ for _ in ()).throw(SystemExit('ERROR: version = \"...\" not found in {}'.format(p))); p.write_text(new, encoding='utf-8')" "$(NORMALIZED_VERSION)"; \
		$(PY) -c "import re,sys,pathlib; p=pathlib.Path('pyproject.toml'); expected=sys.argv[1]; t=p.read_text(encoding='utf-8'); m=re.search(r'(?m)^version\\s*=\\s*\\\"([^\\\"]+)\\\"\\s*$$', t); assert m, 'ERROR: Could not read version from {}'.format(p); actual=m.group(1); assert actual==expected, 'ERROR: pyproject.toml version mismatch. expected={}, actual={}'.format(expected, actual); print('Verified backend version:', actual)" "$(NORMALIZED_VERSION)"; \
	})

# update-backend-version: ## Update backend/pyproject.toml version (uv if available; python fallback)
# 	@printf "Updating backend version -> %s\n" "$(NORMALIZED_VERSION)"
# 	$(call RUN,cd $(BACKEND_DIR) && ( \
# 		$(UV) version $(NORMALIZED_VERSION) >/dev/null 2>&1 || \
# 		$(UV) version --set $(NORMALIZED_VERSION) >/dev/null 2>&1 || \
# 		$(PY) -c "import re,sys,pathlib; p=pathlib.Path('pyproject.toml'); v=sys.argv[1]; t=p.read_text(encoding='utf-8'); new,n=re.subn(r'(?m)^(version\\s*=\\s*\")[^\"]*(\")', lambda m: m.group(1)+v+m.group(2), t, count=1); (n==1) or (_ for _ in ()).throw(SystemExit('ERROR: version = \"...\" not found in {}'.format(p))); p.write_text(new, encoding='utf-8')" "$(NORMALIZED_VERSION)" ))

update-frontend-version: ## Update frontend/package.json version (keeps one-line JSON)
	@printf "Updating frontend version -> %s\n" "$(NORMALIZED_VERSION)"
	$(call RUN,$(PY) -c "import json,sys,pathlib; p=pathlib.Path(sys.argv[1]); v=sys.argv[2]; \
d=json.loads(p.read_text(encoding='utf-8')); d['version']=v; \
p.write_text(json.dumps(d, separators=(',',':'))+'\\n', encoding='utf-8')" \
"$(FRONTEND_FILE)" "$(NORMALIZED_VERSION)")

update-versions: bump-version ## Update backend + frontend versions
	@$(MAKE) update-backend-version
	@$(MAKE) update-frontend-version

commit-release: ## Create release commit (Release version X.Y.Z)
	@printf "$(GREEN)Creating release commit...$(NC)\n"
	@if [ "$(DRY_RUN)" = "1" ]; then \
		echo "[DRY RUN] git add -A"; \
		echo "[DRY RUN] git commit -m \"Release version $(NORMALIZED_VERSION)\""; \
		exit 0; \
	fi
	git add -A
	if git diff --cached --quiet; then \
		printf "$(RED)ERROR: No staged changes to commit. Did versions/changelog change?$(NC)\n"; \
		exit 1; \
	fi
	git commit -m "Release version $(NORMALIZED_VERSION)"

tag-release: ## Create annotated tag vX.Y.Z
	@printf "$(GREEN)Tagging %s...$(NC)\n" "$(TAG)"
	@if [ "$(DRY_RUN)" = "1" ]; then \
		echo "[DRY RUN] git tag -a \"$(TAG)\" -m \"Release $(TAG)\""; \
		exit 0; \
	fi
	git tag -a "$(TAG)" -m "Release $(TAG)"


release: check-tools-release check-clean update-versions ## Bump versions + changelog + commit + tag
	@$(MAKE) changelog
	@$(MAKE) commit-release
	@$(MAKE) tag-release
	@printf "$(GREEN)Release complete: %s$(NC)\n" "$(TAG)"

push-release: ## Push commit + tags to origin
	@if [ "$(DRY_RUN)" = "1" ]; then \
		echo "[DRY RUN] git push"; \
		echo "[DRY RUN] git push --tags"; \
		exit 0; \
	fi
	git push
	git push --tags
	@printf "$(GREEN)Pushed commit + tags.$(NC)\n"

