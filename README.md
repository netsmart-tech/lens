# Lens

Netsmart's multi-client consulting workspace. Select a client, see everything Netsmart touches for them — Jira, FortiGate (later), network metrics (later) — and auto-generate client-facing work-summary reports.

## Stack

- **Backend:** FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16
- **Frontend:** Next.js 15 + React 19 + TypeScript + Tailwind 4 + shadcn/ui + recharts + cmdk
- **Sync workers:** same Python package as backend, different entrypoints (one container per source × tenant)
- **Auth:** Authentik OIDC (hand-rolled; session cookie)
- **Deployment:** Docker Compose on Proxmox, VM 121 (172.16.20.11)

## Quick start (development)

```bash
make dev
```

Starts db + backend + frontend + jira-sync worker in Docker with hot reload. Frontend on http://localhost:3101.

Stop: `Ctrl+C` or `make dev-down`.

## Tenant management

```bash
make add-tenant slug=topbuild name="TopBuild, Inc."
make migrate                              # run core migrations + all tenants
make migrate-tenant slug=topbuild         # run migrations for one tenant
```

## Project structure

```
├── backend/          # FastAPI app + sync workers + Alembic + CLI
├── frontend/         # Next.js app
├── deploy/           # Deploy scripts (Phase 2)
├── .github/          # CI/CD workflows (Phase 2)
├── assets/           # Logos, report templates
├── docker-compose.yml          # Base (shared dev + prod)
├── docker-compose.dev.yml      # Dev overrides (hot reload)
├── docker-compose.prod.yml     # Prod overrides (Phase 2)
└── Makefile          # Developer commands
```

## Design

See `teams/netsmart/apps/lens/DESIGN.md` (v2) in the Loyd tree for full architecture + specialist reviews.

## License

Apache 2.0 — see [LICENSE](./LICENSE).
