"""Secrets-proxy client.

Dev path: when `settings.secrets_proxy_url` is empty, resolve `{secret:name}`
placeholders against `LENS_STATIC_*` environment variables. This is the Phase 1
path — no mTLS, no network call.

Prod path (Phase 2): mTLS GET to `secrets-proxy.netsmart.tech` with the
lens-prod client cert. STUBBED below — real implementation comes when the
cert is issued and the VLAN 20 → VLAN 40 policy is applied (Turtle).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from lens.config import settings
from lens.logging import get_logger

log = get_logger(__name__)


@dataclass
class _CachedSecret:
    value: str
    fetched_at: float


_cache: dict[str, _CachedSecret] = {}


def _cache_key(name: str) -> str:
    return name.lower().replace("-", "_")


def _lookup_static(name: str) -> str | None:
    """Map secret names like 'topbuild-jira-api-token' to LENS_STATIC_TOPBUILD_JIRA_TOKEN."""
    env_name = f"LENS_STATIC_{name.upper().replace('-', '_')}"
    # Accept common shorter aliases too
    val = os.environ.get(env_name)
    if val:
        return val
    # Try alternate mapping: 'topbuild-jira-api-token' → LENS_STATIC_TOPBUILD_JIRA_TOKEN
    if name.endswith("-api-token"):
        alt = f"LENS_STATIC_{name[:-10].upper().replace('-', '_')}_TOKEN"
        return os.environ.get(alt)
    return None


async def get_secret(name: str) -> str:
    """Resolve a secret by name. Cached with TTL.

    Raises KeyError if the secret is not found in either the cache, env, or
    (eventually) the secrets-proxy.
    """
    key = _cache_key(name)
    cached = _cache.get(key)
    now = time.monotonic()
    if cached and (now - cached.fetched_at) < settings.secrets_proxy_cache_ttl_s:
        return cached.value

    # Dev path — no proxy URL configured.
    if not settings.secrets_proxy_url:
        val = _lookup_static(name)
        if val is None:
            raise KeyError(f"Secret '{name}' not found in LENS_STATIC_* env (dev mode)")
        _cache[key] = _CachedSecret(value=val, fetched_at=now)
        return val

    # TODO(Phase 2): mTLS GET to secrets-proxy.netsmart.tech.
    # Blocked on: lens-prod cert issuance + VLAN 20→40 FortiGate policy.
    raise NotImplementedError(
        "Real mTLS secrets-proxy client is Phase 2. "
        "Clear SECRETS_PROXY_URL to fall back to LENS_STATIC_* env vars."
    )
