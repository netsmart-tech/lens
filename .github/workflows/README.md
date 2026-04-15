# CI/CD (Phase 2)

GitHub Actions workflows land here in Phase 2. Planned jobs (mirroring billing's `netsmart-tech/MyBag`):

- `ci.yml` — backend pytest + frontend lint + typecheck on every PR
- `deploy.yml` — on push to `main`: build + push `lens-{backend,frontend}` to GHCR, trigger Drama deploy to 172.16.20.11

Reference: `teams/netsmart/knowledge/project_billing_cicd.md`.
