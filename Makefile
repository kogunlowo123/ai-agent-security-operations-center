# =============================================================================
# AI Agent Security Operations Center — Makefile
# =============================================================================
SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Project configuration ────────────────────────────────────────────────────
PROJECT_NAME    := ai-agent-soc
VERSION         := $(shell cat VERSION)
REGISTRY        ?= ghcr.io/kogunlowo123
IMAGE_TAG       ?= $(VERSION)

# ── Paths ────────────────────────────────────────────────────────────────────
SRC_DIR         := src
SERVICES_DIR    := services
TESTS_DIR       := tests
INFRA_DIR       := infra/terraform

# ── Python tooling ───────────────────────────────────────────────────────────
PYTHON          := python3
PIP             := pip3
PYTEST          := pytest
BLACK           := black
RUFF            := ruff
MYPY            := mypy

# ── Docker ───────────────────────────────────────────────────────────────────
DOCKER          := docker
COMPOSE         := docker compose
API_IMAGE       := $(REGISTRY)/$(PROJECT_NAME)-api:$(IMAGE_TAG)
AGENT_IMAGE     := $(REGISTRY)/$(PROJECT_NAME)-agents:$(IMAGE_TAG)
INGEST_IMAGE    := $(REGISTRY)/$(PROJECT_NAME)-ingest:$(IMAGE_TAG)

# ── Terraform ────────────────────────────────────────────────────────────────
TF              := terraform
TF_DIR          := $(INFRA_DIR)
TF_WORKSPACE    ?= dev

# ── Colors ───────────────────────────────────────────────────────────────────
BOLD   := \033[1m
RESET  := \033[0m
GREEN  := \033[32m
YELLOW := \033[33m

# =============================================================================
# Help
# =============================================================================
.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "$(BOLD)$(PROJECT_NAME) v$(VERSION)$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-26s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Development Setup
# =============================================================================
.PHONY: install
install: ## Install Python dependencies and pre-commit hooks
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	pre-commit install --install-hooks
	@echo "$(GREEN)Development environment ready.$(RESET)"

.PHONY: install-ci
install-ci: ## Install dependencies for CI (no pre-commit)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt

# =============================================================================
# Code Quality
# =============================================================================
.PHONY: lint
lint: ## Run all linters (ruff, mypy)
	$(RUFF) check $(SRC_DIR) $(SERVICES_DIR) $(TESTS_DIR)
	$(MYPY) $(SRC_DIR) --ignore-missing-imports
	@echo "$(GREEN)Lint passed.$(RESET)"

.PHONY: format
format: ## Auto-format code with Black and Ruff
	$(BLACK) $(SRC_DIR) $(SERVICES_DIR) $(TESTS_DIR) --line-length 120
	$(RUFF) check --fix $(SRC_DIR) $(SERVICES_DIR) $(TESTS_DIR)
	@echo "$(GREEN)Format complete.$(RESET)"

.PHONY: format-check
format-check: ## Check formatting without modifying files
	$(BLACK) $(SRC_DIR) $(SERVICES_DIR) $(TESTS_DIR) --line-length 120 --check
	$(RUFF) check $(SRC_DIR) $(SERVICES_DIR) $(TESTS_DIR)

# =============================================================================
# Testing
# =============================================================================
.PHONY: test
test: ## Run unit and integration tests with coverage
	$(PYTEST) $(TESTS_DIR) \
		--cov=$(SRC_DIR) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=80 \
		-v

.PHONY: test-unit
test-unit: ## Run unit tests only
	$(PYTEST) $(TESTS_DIR)/unit -v

.PHONY: test-integration
test-integration: ## Run integration tests (requires running services)
	$(PYTEST) $(TESTS_DIR)/integration -v

.PHONY: test-e2e
test-e2e: ## Run end-to-end API tests
	$(PYTEST) $(TESTS_DIR)/e2e -v

# =============================================================================
# Docker
# =============================================================================
.PHONY: docker-build
docker-build: ## Build all Docker images
	$(DOCKER) build -t $(API_IMAGE) -f $(SERVICES_DIR)/api/Dockerfile .
	$(DOCKER) build -t $(AGENT_IMAGE) -f $(SERVICES_DIR)/agents/Dockerfile .
	$(DOCKER) build -t $(INGEST_IMAGE) -f $(SERVICES_DIR)/ingest/Dockerfile .
	@echo "$(GREEN)Images built: $(API_IMAGE), $(AGENT_IMAGE), $(INGEST_IMAGE)$(RESET)"

.PHONY: docker-push
docker-push: ## Push Docker images to registry
	$(DOCKER) push $(API_IMAGE)
	$(DOCKER) push $(AGENT_IMAGE)
	$(DOCKER) push $(INGEST_IMAGE)
	@echo "$(GREEN)Images pushed to $(REGISTRY).$(RESET)"

.PHONY: docker-build-push
docker-build-push: docker-build docker-push ## Build and push Docker images

# =============================================================================
# Local Development Stack
# =============================================================================
.PHONY: dev
dev: ## Start the full local development stack
	$(COMPOSE) up --build

.PHONY: dev-services
dev-services: ## Start backing services only (postgres, opensearch, redis)
	$(COMPOSE) up -d postgres opensearch redis otel-collector

.PHONY: dev-down
dev-down: ## Stop and remove all local development containers
	$(COMPOSE) down -v

.PHONY: dev-logs
dev-logs: ## Tail logs from all services
	$(COMPOSE) logs -f

# =============================================================================
# Terraform
# =============================================================================
.PHONY: terraform-init
terraform-init: ## Initialize Terraform working directory
	cd $(TF_DIR) && $(TF) init -upgrade
	cd $(TF_DIR) && $(TF) workspace select $(TF_WORKSPACE) || $(TF) workspace new $(TF_WORKSPACE)

.PHONY: terraform-validate
terraform-validate: ## Validate Terraform configuration
	cd $(TF_DIR) && $(TF) validate

.PHONY: terraform-plan
terraform-plan: ## Generate and show Terraform execution plan
	cd $(TF_DIR) && $(TF) plan \
		-var-file="environments/$(TF_WORKSPACE).tfvars" \
		-out=tfplan.$(TF_WORKSPACE)

.PHONY: terraform-apply
terraform-apply: ## Apply the Terraform execution plan
	cd $(TF_DIR) && $(TF) apply tfplan.$(TF_WORKSPACE)

.PHONY: terraform-destroy
terraform-destroy: ## Destroy Terraform-managed infrastructure (use with caution)
	@echo "$(YELLOW)WARNING: This will destroy all infrastructure in workspace $(TF_WORKSPACE).$(RESET)"
	@read -p "Type 'yes' to confirm: " confirm && [ "$$confirm" = "yes" ]
	cd $(TF_DIR) && $(TF) destroy -var-file="environments/$(TF_WORKSPACE).tfvars"

.PHONY: terraform-fmt
terraform-fmt: ## Format all Terraform files
	cd $(TF_DIR) && $(TF) fmt -recursive

# =============================================================================
# Security Scanning
# =============================================================================
.PHONY: scan-deps
scan-deps: ## Scan Python dependencies for known vulnerabilities
	pip-audit -r requirements.txt -r requirements-dev.txt

.PHONY: scan-images
scan-images: ## Scan Docker images with Trivy
	trivy image $(API_IMAGE)
	trivy image $(AGENT_IMAGE)
	trivy image $(INGEST_IMAGE)

.PHONY: scan-iac
scan-iac: ## Scan IaC with Checkov
	checkov -d $(TF_DIR) --framework terraform --compact

# =============================================================================
# Database
# =============================================================================
.PHONY: db-migrate
db-migrate: ## Run Alembic database migrations
	alembic upgrade head

.PHONY: db-rollback
db-rollback: ## Rollback the last database migration
	alembic downgrade -1

.PHONY: db-reset
db-reset: ## Drop and recreate the local development database
	$(COMPOSE) exec postgres psql -U soc_user -c "DROP DATABASE IF EXISTS soc_db;"
	$(COMPOSE) exec postgres psql -U soc_user -c "CREATE DATABASE soc_db;"
	$(MAKE) db-migrate

# =============================================================================
# Clean
# =============================================================================
.PHONY: clean
clean: ## Remove build artifacts, caches, and test outputs
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type f -name '*.pyo' -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage .coverage.* dist build *.egg-info
	rm -rf .mypy_cache .ruff_cache
	rm -f $(TF_DIR)/tfplan.*
	@echo "$(GREEN)Clean complete.$(RESET)"

.PHONY: clean-all
clean-all: clean dev-down ## Remove everything including Docker volumes
	$(DOCKER) system prune -f
	@echo "$(GREEN)Full clean complete.$(RESET)"

# =============================================================================
# Version management
# =============================================================================
.PHONY: version
version: ## Print the current project version
	@cat VERSION

.PHONY: bump-patch
bump-patch: ## Bump patch version (e.g. 0.1.0 -> 0.1.1)
	@current=$$(cat VERSION); \
	IFS='.' read -r major minor patch <<< "$$current"; \
	new="$$major.$$minor.$$((patch + 1))"; \
	echo "$$new" > VERSION; \
	echo "$(GREEN)Version bumped: $$current -> $$new$(RESET)"
