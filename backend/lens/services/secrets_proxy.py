"""Secrets-proxy client.

Architecture: the secrets-proxy at `secrets-proxy.netsmart.tech` is a TLS-
intercepting forward proxy that scans every outbound request's headers + body
for `{secret:name}` placeholders, substitutes the matching secret value, and
forwards the (rewritten) request to the real upstream (Jira, Anthropic, …).
The proxy authenticates clients via mTLS — see `/etc/lens/secrets-proxy.{crt,key,ca.crt}`.

Two consumers in Lens:
- The Jira sync worker (this is the live use today).
- Future: Anthropic API for the report generator (Phase 3).

Both call `make_proxy_client()` to get an `httpx.AsyncClient` configured with
the right proxy URL + mTLS material. Headers like
``Authorization: Basic {secret:topbuild-jira-api-token}`` go through unmodified
on the wire to the proxy, which substitutes the placeholder before forwarding.

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
    """Build an httpx.AsyncClient that routes through the secrets-proxy.

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

    # The proxy serves its own TLS cert to clients AND MITMs the inner TLS
    # to the upstream (Jira, etc.) using its own CA. Trusting the proxy's CA
    # bundle covers both legs.
    verify: str | bool = settings.secrets_proxy_ca_cert or True

    return httpx.AsyncClient(
        base_url=base_url or "",
        proxy=settings.secrets_proxy_url,
        cert=(settings.secrets_proxy_client_cert, settings.secrets_proxy_client_key),
        verify=verify,
        timeout=httpx.Timeout(timeout_s, connect=10.0),
    )
