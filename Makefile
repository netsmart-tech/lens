# =============================================================================
# Lens — developer commands
# =============================================================================

.PHONY: dev dev-up dev-down dev-logs dev-rebuild dev-reset \
        prod-up prod-down prod-rebuild \
        migrate migrate-tenant add-tenant seed-dev \
        test test-ci lint build \
        shell-backend shell-frontend shell-db \
        openapi api-client \
        help

ENV_FILE ?= .env.development
DEV_COMPOSE = docker compose --env-file $(ENV_FILE) -f docker-compose.yml -f docker-compose.dev.yml
PROD_COMPOSE = docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml
TEST_COMPOSE = docker compose -f docker-compose.test.yml

# ---- Dev ----

dev: dev-up ## Start full dev stack (db + backend + jira worker + frontend, hot reload)

dev-up: ## Build + start dev stack
	$(DEV_COMPOSE) up --build

dev-down: ## Stop dev stack
	$(DEV_COMPOSE) down

dev-logs: ## Tail dev logs
	$(DEV_COMPOSE) logs -f

dev-rebuild: ## Force-rebuild containers (after dependency changes)
	$(DEV_COMPOSE) up --build --force-recreate

dev-reset: ## Nuke dev DB and start fresh (DESTROYS DATA)
	$(DEV_COMPOSE) down -v
	@echo "Dev volumes removed. Run 'make dev' to start fresh."

# ---- Migrations / tenants ----

migrate: ## Run core migrations + all tenant migrations
	$(DEV_COMPOSE) exec backend alembic -x mode=all upgrade head

migrate-tenant: ## Run migrations for one tenant (e.g. make migrate-tenant slug=topbuild)
	@test -n "$(slug)" || (echo "Usage: make migrate-tenant slug=<slug>" && exit 1)
	$(DEV_COMPOSE) exec backend alembic -x mode=tenant:$(slug) upgrade head

add-tenant: ## Create + migrate a new tenant (make add-tenant slug=topbuild name="TopBuild, Inc.")
	@test -n "$(slug)" || (echo "Usage: make add-tenant slug=<slug> name=\"Display Name\"" && exit 1)
	$(DEV_COMPOSE) exec backend python -m lens.cli.tenants add "$(slug)" --name "$(name)"

seed-dev: ## Reseed dev data (tenants, user, sample jira)
	$(DEV_COMPOSE) exec backend python -m lens.cli.seed_dev

# ---- Prod (Phase 2) ----

prod-up: ## Build + start production stack
	$(PROD_COMPOSE) up -d --build

prod-down: ## Stop production stack
	$(PROD_COMPOSE) down

prod-rebuild: ## Force rebuild prod images
	$(PROD_COMPOSE) up -d --build --force-recreate

# ---- Test ----

test: ## Run backend pytest (requires local Python env)
	cd backend && pytest -v --tb=short

test-ci: ## Run backend pytest in Docker (CI-equivalent; uses testcontainers)
	$(DEV_COMPOSE) run --rm backend pytest -v --tb=short

# ---- Lint ----

lint: ## Frontend ESLint + backend ruff
	cd frontend && npm run lint
	cd backend && ruff check .

build: ## Build all images without starting
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# ---- Shells ----

shell-backend: ## Shell into backend container
	$(DEV_COMPOSE) exec backend bash

shell-frontend: ## Shell into frontend container
	$(DEV_COMPOSE) exec frontend sh

shell-db: ## psql into dev Postgres
	$(DEV_COMPOSE) exec db psql -U $${DB_USER:-lens} -d $${DB_NAME:-lens}

# ---- API client generation ----

openapi: ## Dump OpenAPI schema from running backend to backend/openapi.json
	$(DEV_COMPOSE) exec backend python -m lens.cli.dump_openapi

api-client: openapi ## Regenerate TS client from OpenAPI schema
	cd frontend && npm run gen:api

# ---- Help ----

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
