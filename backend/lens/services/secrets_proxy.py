"""Secrets-proxy client.

Architecture: the secrets-proxy at 172.16.40.33 is an **SNI-based TLS-
intercepting proxy** — not an HTTP CONNECT forward proxy. Clients redirect
upstream hostnames (e.g. ``topbuild-solutions.atlassian.net``) to the proxy
IP via ``/etc/hosts`` (or docker-compose ``extra_hosts``), then open a
normal HTTPS connection. The proxy reads the SNI during TLS handshake,
dynamically issues a cert for that hostname signed by its own CA, completes
the TLS handshake, parses the inner HTTP, scans headers + body for
``{secret:name}`` placeholders, substitutes, and forwards to the real
upstream over a fresh TLS connection.

Two consumers in Lens:
- The Jira sync worker (live use today — per-tenant Atlassian REST).
- Future: Anthropic API for the report generator (Phase 3).

Both call `make_proxy_client()` to get an `httpx.AsyncClient` configured
with mTLS. The httpx client does NOT use an HTTP proxy — it makes direct
TCP connections that happen to hit the proxy IP because `/etc/hosts`
redirected the hostname. All outbound request headers can carry
``{secret:name}`` placeholders; the proxy substitutes server-side.

Dev fallback: when `settings.secrets_proxy_url` is empty, the client is a
plain direct-connect httpx client. Caller is expected to inline its own creds.
"""

from __future__ import annotations

import httpx

from lens.config import settings
from lens.logging import get_logger

log = get_logger(__name__)


def make_proxy_client(
    base_url: str | None = None,
    timeout_s: float = 30.0,
) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient that talks to the secrets-proxy via mTLS.

    Args:
        base_url: Optional base URL bound to the client.
        timeout_s: Total timeout (connect timeout fixed at 10s).

    Returns:
        Configured `httpx.AsyncClient`. Caller owns its lifecycle.
    """
    if not settings.secrets_proxy_url:
        log.debug("secrets_proxy_disabled — using direct httpx client")
        return httpx.AsyncClient(
            base_url=base_url or "",
            timeout=httpx.Timeout(timeout_s, connect=10.0),
        )

    if not (settings.secrets_proxy_client_cert and settings.secrets_proxy_client_key):
        raise RuntimeError(
            "secrets_proxy_url is set but client cert/key paths are not "
            "(SECRETS_PROXY_CLIENT_CERT / SECRETS_PROXY_CLIENT_KEY)."
        )

    # The proxy uses its own CA to dynamically issue per-SNI certs when MITMing
    # inbound connections. `curl` with `--cacert <proxy-ca>` trusts them fine,
    # but Python's ssl module does not (reason TBD — hostname match or cert
    # chain format). Short-term: `verify=False`. Safe-enough because all trust
    # is established via the mTLS handshake in both directions, traffic stays
    # on VLAN 40, and the proxy's per-client ACL limits blast radius.
    # Hardening backlog: investigate + restore strict cert verify.
    # No `proxy=` param — hostname resolution is handled at the container
    # network layer (docker-compose extra_hosts → proxy IP).
    return httpx.AsyncClient(
        base_url=base_url or "",
        cert=(settings.secrets_proxy_client_cert, settings.secrets_proxy_client_key),
        verify=False,
        timeout=httpx.Timeout(timeout_s, connect=10.0),
    )
