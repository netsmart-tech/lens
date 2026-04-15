# Deploy (Phase 2)

This directory will hold the production deploy pipeline for Lens:

- `pull-deploy.sh` — mirrors billing's pattern (`sudo /srv/lens/deploy/pull-deploy.sh`)
- `systemd/lens.service` — if we move to systemd orchestration
- `nginx/lens.netsmart.tech.conf` — reference NGINX HA config

Populated in Phase 2 when we deploy to VM 118 (172.16.20.11).

See `teams/netsmart/apps/portal/DESIGN.md` §7 for the full deployment architecture and `outputs/configs/vince-portal-architecture-recommendation.md` for rationale.
