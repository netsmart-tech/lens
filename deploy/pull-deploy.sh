#!/usr/bin/env bash
# =============================================================================
# Lens — pull-based deploy script for /srv/lens/
#
# Reads GHCR_READ_TOKEN from .env.runtime (written by Infisical agent),
# logs into GHCR, performs a pre-deploy per-tenant pg_dump against external
# loyd-pg, pulls latest images, restarts services, and runs tenant-aware
# migrations.
#
# Usage: sudo /srv/lens/deploy/pull-deploy.sh
# =============================================================================

set -euo pipefail

APP_DIR="/srv/lens"
BACKUP_DIR="${APP_DIR}/backups"
COMPOSE_FILES="-f ${APP_DIR}/docker-compose.yml -f ${APP_DIR}/docker-compose.prod.yml"
HEALTH_URL="http://localhost:${BACKEND_PORT:-8100}/api/health"
BACKUP_RETAIN_COUNT="${BACKUP_RETAIN_COUNT:-14}"

cd "$APP_DIR"

# --- Source env files so docker compose can interpolate variables ---
# .env.prod:    non-secret config (ports, hostnames, OIDC endpoints)
# .env.runtime: secrets from Infisical (DB password, session secret, GHCR token, OIDC secret)
# Infisical agent writes shell-quoted values (KEY='value') — strip the quotes.
set -a
[[ -f "${APP_DIR}/.env.prod" ]]    && source <(grep -v '^#' "${APP_DIR}/.env.prod"    | sed "s/='\\(.*\\)'$/=\\1/" | sed 's/="\\(.*\\)"$/=\\1/')
[[ -f "${APP_DIR}/.env.runtime" ]] && source <(grep -v '^#' "${APP_DIR}/.env.runtime" | sed "s/='\\(.*\\)'$/=\\1/" | sed 's/="\\(.*\\)"$/=\\1/')
set +a

# --- Sanity: GHCR token must be present ---
if [[ -z "${GHCR_READ_TOKEN:-}" ]]; then
    echo "ERROR: GHCR_READ_TOKEN not found. Ensure Infisical agent has rendered .env.runtime"
    echo "       and /apps/lens/GHCR_READ_TOKEN is set in Infisical."
    exit 1
fi

# --- Sanity: DATABASE_URL must be set (external loyd-pg) ---
if [[ -z "${DATABASE_URL:-}" || "$DATABASE_URL" == CHANGEME-* ]]; then
    echo "ERROR: DATABASE_URL is unset or placeholder. Ensure lens_app role exists on loyd-pg"
    echo "       and /apps/lens/DATABASE_URL + DB_PASSWORD are set in Infisical."
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# --- Pre-deploy backup: per-tenant schema dump against external loyd-pg ---
# Backup every lens_* schema individually so restore can be scoped to one
# client if needed. Uses DATABASE_URL from .env.runtime — read-only operation.
echo "==> Pre-deploy backup: per-tenant schemas on loyd-pg..."
TS="$(date +%Y%m%d-%H%M%S)"
SCHEMAS="$(psql "$DATABASE_URL" -At -c \
    "SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'lens%' ORDER BY schema_name;")"

if [[ -z "$SCHEMAS" ]]; then
    echo "    WARNING: no lens schemas found on loyd-pg — first deploy? skipping backup."
else
    for schema in $SCHEMAS; do
        OUT="${BACKUP_DIR}/${schema}-${TS}.sql.gz"
        echo "    dumping ${schema} -> ${OUT}"
        pg_dump "$DATABASE_URL" --schema="$schema" --no-owner --no-acl | gzip > "$OUT"
    done
fi

# --- Prune old backups (keep last N of each schema) ---
if [[ -n "$SCHEMAS" ]]; then
    for schema in $SCHEMAS; do
        ls -1t "${BACKUP_DIR}/${schema}-"*.sql.gz 2>/dev/null | tail -n "+$((BACKUP_RETAIN_COUNT + 1))" | xargs -r rm -f
    done
fi

# --- GHCR login ---
echo "==> Logging into GHCR..."
echo "$GHCR_READ_TOKEN" | docker login ghcr.io -u netsmart-tech --password-stdin

# --- Pull latest images ---
echo "==> Pulling latest images..."
docker compose ${COMPOSE_FILES} pull backend frontend worker-jira

# --- Restart services (alembic migrations run as part of backend start command) ---
echo "==> Restarting services..."
docker compose ${COMPOSE_FILES} up -d

# --- Health check ---
echo "==> Waiting for backend health..."
for i in {1..12}; do
    sleep 5
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "==> Deploy successful — health check passed ($(curl -s "$HEALTH_URL"))."
        exit 0
    fi
done

echo "==> ERROR: health check failed after 60s. Recent backend logs:"
docker compose ${COMPOSE_FILES} logs --tail=50 backend
exit 1
