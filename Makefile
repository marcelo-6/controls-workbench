###############################################################################
# Controls Workbench - Makefile
#
# Motivation / Intention
# ----------------------
# Keep ONE canonical workflow for both:
#   - Local development (you want to bump versions + generate CHANGELOG.md, but
#     you do NOT want to create tags locally because CI will do that later)
#   - CI pipeline (CI will run the same Make targets and can tag/push)
#
# This Makefile is designed so you can "practice" the workflow locally with
# DRY_RUN=1, and later your CI can run the exact same commands for real.
#
# Key Behaviors
# -------------
# - Versions stored in files are WITHOUT "v" (e.g. 0.0.10)
# - Git tags are WITH "v" (e.g. v0.0.10)
# - Changelog generation supports an "unreleased tagged output" mode so you can
#   produce a CHANGELOG.md entry for vX.Y.Z WITHOUT creating any tags:
#       git-cliff --unreleased --tag v0.0.10 -o CHANGELOG.md
#
# Logging UX
# ----------
# - Each target prints status like:
#     [target] doing something
#     ✓ [target] success message
#     ✗ [target] failure message
# - VERBOSE=1 prints the exact command(s) being executed.
# - DRY_RUN=1 prints the command(s) and SKIPS validations that would fail because
#   files are not actually modified.
#
# Examples (Local)
# ---------------
#   make check-tools
#   make changelog-preview
#   make prepare-release VERSION=v0.0.10
#   make release DRY_RUN=1 VERSION=v0.0.10
#
# Examples (CI Later)
# -------------------
# Most CI systems set CI=true automatically. This Makefile defaults to tagging
# and pushing in CI mode:
#   CI=true make release VERSION=v0.0.10
#
# Override behavior explicitly:
#   make release VERSION=v0.0.10 CREATE_TAG=0 PUSH=0
###############################################################################

.ONESHELL:
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory
.SILENT:  # global silence (only our printf output shows)

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
# Flags
# ----------------------------
DRY_RUN  ?= 0
VERBOSE  ?= 0
SKIP_CHECKS ?= 0

# CI defaults: tag/push only when CI=true (or you override)
CI ?= 0
CI_MODE := $(if $(filter 1 true TRUE yes YES,$(CI)),1,0)
CREATE_TAG ?= $(CI_MODE)
PUSH       ?= $(CI_MODE)

# ----------------------------
# Versioning
# ----------------------------
RAW_BUMPED_VERSION := $(shell $(GIT_CLIFF) --bumped-version 2>/dev/null || true)
VERSION ?= $(RAW_BUMPED_VERSION)

NORMALIZED_VERSION := $(patsubst v%,%,$(patsubst V%,%,$(VERSION)))
TAG := v$(NORMALIZED_VERSION)

VALID_VERSION := $(shell echo "$(NORMALIZED_VERSION)" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$$' || true)

# ----------------------------
# Logging helpers (NO leading '@' - safe inside shell blocks)
# ----------------------------
define LOG
if [ "$(VERBOSE)" = "1" ]; then \
	printf "$(CYAN)[%s]$(NC) %s\n" "$(1)" "$(2)"; \
else \
	printf "$(NC) %s\n" "$(2)"; \
fi
endef

define OK
printf "$(GREEN)✓$(NC) %s\n" "$(2)"
endef

define WARN
if [ "$(VERBOSE)" = "1" ]; then \
	printf "$(YELLOW)!$(NC) [%s] %s\n" "$(1)" "$(2)"; \
else \
	printf "$(YELLOW)!$(NC) %s\n" "$(2)"; \
fi
endef

define FAIL

if [ "$(VERBOSE)" = "1" ]; then \
	printf "$(RED)✗$(NC) [%s] %s\n" "$(1)" "$(2)"; exit 1; \
else \
	printf "$(RED)✗$(NC) %s\n" "$(2)"; exit 1; \
fi
endef

define VPRINT
if [ "$(VERBOSE)" = "1" ]; then \
	printf "$(YELLOW)[%s]$(NC) cmd: %s\n" "$(1)" "$(2)"; \
fi
endef

define RUN
$(call VPRINT,$(1),$(2))
if [ "$(DRY_RUN)" = "1" ]; then \
	printf "$(YELLOW)[%s]$(NC) DRY_RUN: %s\n" "$(1)" "$(2)"; \
else \
	$(2); \
fi
endef

define REQUIRE_CMD
command -v $(1) >/dev/null 2>&1 || { printf "$(RED)✗$(NC) [%s] Missing required tool: %s\n" "$(2)" "$(1)"; exit 1; }
endef

define REQUIRE_OK
$(1) >/dev/null 2>&1 || { printf "$(RED)✗$(NC) [%s] %s\n" "$(3)" "$(2)"; exit 1; }
endef

# ----------------------------
# Phony targets
# ----------------------------
.PHONY: help \
	check-tools check-tools-release check-clean show-version next-version \
	init install-backend install-frontend \
	lint format test precommit \
	changelog-preview changelog-release \
	clean_python_cache clean_pnpm_cache clean_frontend_build clean_all \
	bump-version update-backend-version update-frontend-version update-versions \
	commit-release tag-release push-release \
	prepare-release release

# ----------------------------
# Help
# ----------------------------
help: ## Show available commands
	printf "\n$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)\n"
	printf "$(GREEN)                  CONTROLS WORKBENCH MAKE COMMANDS                  $(NC)\n"
	printf "$(GREEN)═══════════════════════════════════════════════════════════════════$(NC)\n\n"
	printf "$(CYAN)Targets:$(NC)\n"
	awk 'BEGIN{FS=":.*##"} /^[a-zA-Z0-9_.-]+:.*##/{printf "  \033[0;32m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	printf "\n$(CYAN)Examples:$(NC)\n"
	printf "  make prepare-release VERSION=v0.0.10\n"
	printf "  make release DRY_RUN=1 VERSION=v0.0.10\n"
	printf "  CI=true make release VERSION=v0.0.10\n\n"

# ----------------------------
# Tool checks
# ----------------------------
check-tools: ## Check common dev tools (must be runnable, not just present)
	$(call LOG,check-tools,Checking dev tooling...)
	$(call REQUIRE_CMD,git,check-tools)
	$(call REQUIRE_CMD,$(PY),check-tools)
	$(call REQUIRE_CMD,$(UV),check-tools)
	$(call REQUIRE_OK,$(UV) --version,uv is installed but not runnable,check-tools)

	$(call REQUIRE_CMD,node,check-tools)
	$(call REQUIRE_OK,node --version,node is installed but not runnable,check-tools)

	$(call REQUIRE_CMD,$(PNPM),check-tools)
	$(call REQUIRE_OK,$(PNPM) --version,pnpm is found but fails to run (often node missing in WSL),check-tools)

	$(call OK,check-tools,OK: git, python, uv, node, pnpm)

check-tools-release: ## Check tools required for release flow
	$(call LOG,check-tools-release,Checking release tooling...)
	$(call REQUIRE_CMD,git,check-tools-release)
	$(call REQUIRE_CMD,$(PY),check-tools-release)
	$(call REQUIRE_CMD,$(UV),check-tools-release)
	$(call REQUIRE_CMD,$(GIT_CLIFF),check-tools-release)

	$(call REQUIRE_OK,$(UV) --version,uv is installed but not runnable,check-tools-release)
	$(call REQUIRE_OK,$(GIT_CLIFF) --version,git-cliff is installed but not runnable,check-tools-release)

	$(call REQUIRE_CMD,node,check-tools-release)
	$(call REQUIRE_OK,node --version,node is installed but not runnable,check-tools-release)

	$(call REQUIRE_CMD,$(PNPM),check-tools-release)
	$(call REQUIRE_OK,$(PNPM) --version,pnpm is found but fails to run (often node missing in WSL),check-tools-release)

	$(call OK,check-tools-release,OK: release tooling present (git, python, uv, git-cliff, node, pnpm))

check-clean: ## Ensure git working tree is clean
	$(call LOG,check-clean,Checking git working tree is clean...)
	if [ -n "$$(git status --porcelain)" ]; then \
		git status --porcelain; \
		$(call FAIL,check-clean,Working tree not clean. Commit or stash before release.); \
	fi
	$(call OK,check-clean,OK: working tree clean)

show-version: ## Print computed VERSION / TAG
	printf "VERSION=%s\n" "$(VERSION)"
	printf "NORMALIZED_VERSION=%s\n" "$(NORMALIZED_VERSION)"
	printf "TAG=%s\n" "$(TAG)"
	printf "CI_MODE=%s CREATE_TAG=%s PUSH=%s\n" "$(CI_MODE)" "$(CREATE_TAG)" "$(PUSH)"

next-version: ## Show version git-cliff would bump to
	$(call LOG,next-version,Computing bumped version with git-cliff...)
	if [ -z "$(RAW_BUMPED_VERSION)" ]; then \
		$(call FAIL,next-version,git-cliff did not return a bumped version. Check config / commit conventions.); \
	fi
	$(call OK,next-version,Next version: $(RAW_BUMPED_VERSION))

# ----------------------------
# Install
# ----------------------------
init: check-tools ## Install backend + frontend deps
	$(call LOG,init,Installing dependencies...)
	$(MAKE) install-backend
	$(MAKE) install-frontend
	$(call OK,init,Dependencies installed)

install-backend: ## Install backend deps (uv)
	$(call LOG,install-backend,Installing backend dependencies...)
	$(call RUN,install-backend,cd "$(BACKEND_DIR)" && "$(UV)" sync --frozen)
	$(call OK,install-backend,Backend dependencies installed)

install-frontend: ## Install frontend deps (pnpm)
	$(call LOG,install-frontend,Installing frontend dependencies...)
	$(call RUN,install-frontend,cd "$(FRONTEND_DIR)" && "$(PNPM)" install --frozen-lockfile)
	$(call OK,install-frontend,Frontend dependencies installed)

# ----------------------------
# Changelog
# ----------------------------
changelog-preview: ## Generate CHANGELOG.md without tags (Unreleased section)
	if [ "$(SKIP_CHECKS)" != "1" ]; then $(MAKE) check-tools-release; fi
	$(call LOG,changelog-preview,Generating changelog preview (unreleased)...)
	$(call RUN,changelog-preview,"$(GIT_CLIFF)" --unreleased -o "$(CHANGELOG_FILE)")
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,changelog-preview,DRY_RUN: changelog not written.); \
	else \
		$(call OK,changelog-preview,Wrote $(CHANGELOG_FILE)); \
	fi

changelog-release: ## Generate CHANGELOG.md for VERSION without creating git tags
	if [ "$(SKIP_CHECKS)" != "1" ]; then $(MAKE) check-tools-release; fi
	$(call LOG,changelog-release,Generating changelog for $(TAG) (no tags required)...)
	if [ -z "$(VALID_VERSION)" ]; then \
		$(call FAIL,changelog-release,Invalid VERSION='$(VERSION)' (normalized='$(NORMALIZED_VERSION)'). Expected 1.2.3); \
	fi
	$(call RUN,changelog-release,"$(GIT_CLIFF)" --unreleased --tag "$(TAG)" -o "$(CHANGELOG_FILE)")
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,changelog-release,DRY_RUN: changelog not written.); \
	else \
		$(call OK,changelog-release,Wrote $(CHANGELOG_FILE)); \
	fi

# ----------------------------
# Release flow
# ----------------------------
bump-version: ## Validate release version and ensure local tag doesn't already exist
	$(call LOG,bump-version,Validating VERSION and TAG...)
	if [ -z "$(VERSION)" ]; then \
		$(call FAIL,bump-version,VERSION is empty. Provide VERSION=1.2.3 or fix git-cliff config.); \
	fi
	if [ -z "$(VALID_VERSION)" ]; then \
		$(call FAIL,bump-version,Invalid VERSION='$(VERSION)' (normalized='$(NORMALIZED_VERSION)'). Expected 1.2.3); \
	fi
	if git rev-parse -q --verify "refs/tags/$(TAG)" >/dev/null; then \
		$(call FAIL,bump-version,Local tag $(TAG) already exists.); \
	fi
	$(call OK,bump-version,Release version: $(NORMALIZED_VERSION) (tag: $(TAG)))

update-backend-version: ## Update backend/pyproject.toml version + validate
	$(call LOG,update-backend-version,Updating backend version -> $(NORMALIZED_VERSION))
	$(call RUN,update-backend-version,cd "$(BACKEND_DIR)" && "$(UV)" version "$(NORMALIZED_VERSION)" >/dev/null 2>&1)
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,update-backend-version,DRY_RUN: validation skipped.); \
	else \
		if ! grep -q "^version = \"$(NORMALIZED_VERSION)\"$$" pyproject.toml; then \
			$(call FAIL,update-backend-version,Backend pyproject.toml version validation failed.); \
		fi; \
		$(call OK,update-backend-version,Backend version updated successfully); \
	fi

update-frontend-version: ## Update frontend/package.json version + validate
	$(call LOG,update-frontend-version,Updating frontend version -> $(NORMALIZED_VERSION))
	$(call RUN,update-frontend-version,cd "$(FRONTEND_DIR)" && "$(PNPM)" version "$(NORMALIZED_VERSION)" --no-git-tag-version >/dev/null 2>&1)
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,update-frontend-version,DRY_RUN: validation skipped.); \
	else \
		if ! grep -Eq "\"version\"[[:space:]]*:[[:space:]]*\"$(NORMALIZED_VERSION)\"" package.json; then \
			$(call FAIL,update-frontend-version,Frontend package.json version validation failed.); \
		fi; \
		$(call OK,update-frontend-version,Frontend version updated successfully); \
	fi

update-versions: bump-version ## Update backend + frontend versions
	$(call LOG,update-versions,Updating backend + frontend versions...)
	$(MAKE) update-backend-version
	$(MAKE) update-frontend-version
	$(call OK,update-versions,Versions updated)

commit-release: ## Create release commit (Release version X.Y.Z)
	$(call LOG,commit-release,Creating release commit...)
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,commit-release,DRY_RUN: would run git add -A && git commit -m "Release version $(NORMALIZED_VERSION)"); \
		$(call OK,commit-release,DRY_RUN: commit step simulated); \
		exit 0; \
	fi
	git add -A
	if git diff --cached --quiet; then \
		$(call FAIL,commit-release,No staged changes to commit. Did versions/changelog change?); \
	fi
	git commit -m "Release version $(NORMALIZED_VERSION)"
	$(call OK,commit-release,Created commit "Release version $(NORMALIZED_VERSION)")

tag-release: ## Create annotated tag vX.Y.Z
	$(call LOG,tag-release,Tagging release $(TAG)...)
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,tag-release,DRY_RUN: would run git tag -a "$(TAG)" -m "Release $(TAG)"); \
		$(call OK,tag-release,DRY_RUN: tag step simulated); \
		exit 0; \
	fi
	git tag -a "$(TAG)" -m "Release $(TAG)"
	$(call OK,tag-release,Created tag $(TAG))

push-release: ## Push commit + tags to origin
	$(call LOG,push-release,Pushing commit and tags...)
	if [ "$(DRY_RUN)" = "1" ]; then \
		$(call WARN,push-release,DRY_RUN: would run git push && git push --tags); \
		$(call OK,push-release,DRY_RUN: push step simulated); \
		exit 0; \
	fi
	git push
	git push --tags
	$(call OK,push-release,Pushed commit + tags)

prepare-release: ## Local-friendly: bump versions + changelog + commit (NO TAG/PUSH by default)
	$(MAKE) check-tools-release
	$(MAKE) check-clean
	$(MAKE) update-versions
	$(MAKE) changelog-release SKIP_CHECKS=1
	$(MAKE) commit-release
	$(call OK,prepare-release,Prepared release $(TAG) (tag/push handled separately))

release: ## CI-friendly: prepare-release + optional tag/push (CREATE_TAG/PUSH default to CI)
	$(MAKE) prepare-release
	if [ "$(CREATE_TAG)" = "1" ]; then \
		$(MAKE) tag-release; \
	else \
		$(call WARN,release,Skipping tag creation (CREATE_TAG=0)); \
	fi
	if [ "$(PUSH)" = "1" ]; then \
		$(MAKE) push-release; \
	else \
		$(call WARN,release,Skipping push (PUSH=0)); \
	fi
	$(call OK,release,Release complete: $(TAG))
