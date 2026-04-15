"""Async Jira REST client — rate-limited, retrying, pagination-aware.

Per Teo §5 / DESIGN §3.6:
- `aiolimiter.AsyncLimiter(9, 1.0)` per base URL (leaky bucket for asyncio).
- `tenacity` retry with exponential backoff on 429/5xx/TransportError.
- Per-site limiter singletons (shared Jira Cloud rate limit across tenants
  sharing a site).

Auth: caller supplies the literal `Authorization` header value. In prod that
includes a `{secret:<name>}` placeholder which the secrets-proxy substitutes
in flight (e.g. `Basic {secret:topbuild-jira-api-token}` — the secret stored
in the proxy is the pre-base64-encoded `email:token` blob). The HTTPS path
to Jira routes through the secrets-proxy via `make_proxy_client`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from lens.config import settings
from lens.logging import get_logger
from lens.services.secrets_proxy import make_proxy_client

log = get_logger(__name__)

# Per-base-url limiter cache so multiple clients share a bucket.
_limiter_cache: dict[str, AsyncLimiter] = {}


def _limiter_for(base_url: str) -> AsyncLimiter:
    limiter = _limiter_cache.get(base_url)
    if limiter is None:
        limiter = AsyncLimiter(
            max_rate=settings.jira_rate_limit_rps,
            time_period=settings.jira_rate_limit_period_s,
        )
        _limiter_cache[base_url] = limiter
    return limiter


class JiraClient:
    """Async Jira Cloud REST client.

    Args:
        base_url: Site URL, e.g. `https://topbuild.atlassian.net`. Path
            prefixes are added per-method.
        authorization: Full `Authorization` header value to send with every
            request. In prod: `Basic {secret:<slug>-jira-api-token}` — the
            secrets-proxy substitutes the literal placeholder for the stored
            base64(email:token) blob before forwarding to Atlassian.
    """

    def __init__(self, base_url: str, authorization: str):
        self.base_url = base_url.rstrip("/")
        self._client = make_proxy_client(base_url=self.base_url)
        self._client.headers.update({
            "Authorization": authorization,
            "Accept": "application/json",
        })
        self._limiter = _limiter_for(self.base_url)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> JiraClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=1, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with self._limiter:
            resp = await self._client.get(path, params=params)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "0") or 0)
            if retry_after:
                await asyncio.sleep(retry_after)
        resp.raise_for_status()
        return resp.json()

    # ---- high-level ops -----------------------------------------------------

    async def search_issues(
        self,
        jql: str,
        fields: list[str] | None = None,
        start_at: int = 0,
        max_results: int = 100,
    ) -> dict:
        """POST /rest/api/3/search. Cursor-of-sorts via start_at."""
        params: dict[str, Any] = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
        }
        if fields:
            params["fields"] = ",".join(fields)
        return await self._get("/rest/api/3/search", params=params)

    async def get_issue(self, key: str) -> dict:
        return await self._get(f"/rest/api/3/issue/{key}")

    async def list_comments(self, key: str, start_at: int = 0, max_results: int = 100) -> dict:
        return await self._get(
            f"/rest/api/3/issue/{key}/comment",
            params={"startAt": start_at, "maxResults": max_results},
        )

    async def list_changelog(self, key: str, start_at: int = 0, max_results: int = 100) -> dict:
        return await self._get(
            f"/rest/api/3/issue/{key}/changelog",
            params={"startAt": start_at, "maxResults": max_results},
        )

    async def list_worklogs(self, key: str, start_at: int = 0, max_results: int = 100) -> dict:
        return await self._get(
            f"/rest/api/3/issue/{key}/worklog",
            params={"startAt": start_at, "maxResults": max_results},
        )
