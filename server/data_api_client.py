"""HTTP client for the Lakebase Data API (PostgREST-based REST interface).

The Data API exposes Lakebase tables as REST resources with filtering,
sorting, pagination, and resource embedding — all authenticated via
Databricks OAuth bearer tokens.

Base URL pattern:
  https://<endpoint-id>.database.<region>.cloud.databricks.com/api/2.0/workspace/<workspace-id>/rest/<database>

Read replicas use the replica endpoint host; writes to replicas fail with HTTP 405.
"""

import logging
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from server.config import config

logger = logging.getLogger(__name__)

DATA_API_TIMEOUT = 30.0


class DataAPIError(Exception):
    """Raised when the Data API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str, error_code: str = ""):
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        super().__init__(f"HTTP {status_code}: {detail}")


class LakebaseDataAPIClient:
    """Async HTTP client for Lakebase Data API operations."""

    def __init__(self, base_url: str, token: str, replica_url: str = ""):
        self._base_url = base_url.rstrip("/")
        self._replica_url = replica_url.rstrip("/") if replica_url else ""
        self._token = token
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=DATA_API_TIMEOUT,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.close()

    def _build_url(
        self, schema: str, table: str, use_replica: bool = False
    ) -> str:
        base = self._replica_url if (use_replica and self._replica_url) else self._base_url
        return f"{base}/{schema}/{table}"

    def _build_filter_params(self, filters: dict[str, str]) -> str:
        """Build PostgREST filter query string from a dict.

        Values use PostgREST operator syntax: eq.value, gte.5, like.*foo*, in.(a,b,c)
        """
        return "&".join(f"{k}={v}" for k, v in filters.items())

    async def _handle_response(self, resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            try:
                body = resp.json()
                detail = body.get("message", body.get("details", resp.text))
                error_code = str(body.get("code", ""))
            except Exception:
                detail = resp.text
                error_code = ""
            raise DataAPIError(resp.status_code, detail, error_code)
        if resp.status_code == 204:
            return []
        try:
            return resp.json()
        except Exception:
            return resp.text

    async def get(
        self,
        schema: str,
        table: str,
        *,
        filters: Optional[dict[str, str]] = None,
        select: Optional[str] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        use_replica: bool = False,
    ) -> Any:
        """GET rows from a table with optional filtering, sorting, and pagination."""
        url = self._build_url(schema, table, use_replica=use_replica)
        params: dict[str, str] = {}
        if filters:
            params.update(filters)
        if select:
            params["select"] = select
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)

        client = await self._get_client()
        resp = await client.get(url, params=params)
        return await self._handle_response(resp)

    async def insert(
        self, schema: str, table: str, rows: list[dict[str, Any]]
    ) -> Any:
        """POST one or more rows into a table."""
        url = self._build_url(schema, table)
        client = await self._get_client()
        body = rows[0] if len(rows) == 1 else rows
        resp = await client.post(
            url,
            json=body,
            headers={"Prefer": "return=representation"},
        )
        return await self._handle_response(resp)

    async def update(
        self,
        schema: str,
        table: str,
        filters: dict[str, str],
        data: dict[str, Any],
    ) -> Any:
        """PATCH rows matching filters."""
        url = self._build_url(schema, table)
        client = await self._get_client()
        resp = await client.patch(
            url,
            params=filters,
            json=data,
            headers={"Prefer": "return=representation"},
        )
        return await self._handle_response(resp)

    async def delete(
        self, schema: str, table: str, filters: dict[str, str]
    ) -> Any:
        """DELETE rows matching filters."""
        url = self._build_url(schema, table)
        client = await self._get_client()
        resp = await client.delete(url, params=filters)
        return await self._handle_response(resp)

    async def get_openapi_schema(self) -> Any:
        """GET /openapi.json — requires OpenAPI to be enabled in Data API settings."""
        url = f"{self._base_url}/openapi.json"
        client = await self._get_client()
        resp = await client.get(url)
        return await self._handle_response(resp)
