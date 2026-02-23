"""Async PostgreSQL connection pool for Lakebase with autoscaling-aware retry.

Merged: base pool + Gap 1 (scale-to-zero retry) + Gap 4 (read replica routing).
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from server.config import config

logger = logging.getLogger(__name__)


class LakebasePool:
    """Manages async connection pool to Lakebase PostgreSQL.

    Designed for Lakebase Autoscaling with:
    - Exponential backoff retry for scale-to-zero wake-up
    - Connection health checks before checkout
    - Automatic reconnection on transient failures
    - Read replica routing for read-only queries
    """

    def __init__(self):
        self._primary_pool: Optional[AsyncConnectionPool] = None
        self._replica_pool: Optional[AsyncConnectionPool] = None

    async def initialize(
        self, conninfo: str, replica_conninfo: str = None
    ):
        """Initialize primary (and optional replica) connection pools."""
        self._primary_pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=config.pool_min_size,
            max_size=config.pool_max_size,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": True},
            # Autoscaling-critical settings:
            check=AsyncConnectionPool.check_connection,
            max_lifetime=config.pool_max_lifetime,
            max_idle=config.pool_max_idle,
            reconnect_timeout=30,
        )
        await self._primary_pool.open()
        logger.info("Lakebase primary connection pool initialized (autoscaling-aware)")

        if replica_conninfo:
            self._replica_pool = AsyncConnectionPool(
                conninfo=replica_conninfo,
                min_size=1,
                max_size=config.pool_max_size,
                open=False,
                kwargs={"row_factory": dict_row, "autocommit": True},
                check=AsyncConnectionPool.check_connection,
                max_lifetime=config.pool_max_lifetime,
                max_idle=config.pool_max_idle,
                reconnect_timeout=30,
            )
            await self._replica_pool.open()
            logger.info("Lakebase replica connection pool initialized")

    async def close(self):
        if self._primary_pool:
            await self._primary_pool.close()
            logger.info("Lakebase primary pool closed")
        if self._replica_pool:
            await self._replica_pool.close()
            logger.info("Lakebase replica pool closed")

    @asynccontextmanager
    async def connection(
        self, prefer_replica: bool = False
    ) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Get a connection with scale-to-zero retry logic.

        If the Lakebase compute is suspended (scale-to-zero), the first
        connection attempt will fail. This method retries with exponential
        backoff to allow the compute to wake up (~hundreds of milliseconds).

        Args:
            prefer_replica: If True and replica pool is available, use replica.
        """
        target_pool = self._primary_pool
        if prefer_replica and self._replica_pool:
            target_pool = self._replica_pool

        if not target_pool:
            raise RuntimeError("Pool not initialized. Call initialize() first.")

        last_error = None
        for attempt in range(config.scale_to_zero_retry_attempts):
            try:
                async with target_pool.connection() as conn:
                    yield conn
                    return
            except (
                psycopg.OperationalError,
                psycopg.errors.ConnectionException,
                ConnectionRefusedError,
                OSError,
            ) as e:
                last_error = e
                delay = min(
                    config.scale_to_zero_retry_base_delay * (2**attempt),
                    config.scale_to_zero_max_delay,
                )
                logger.warning(
                    f"Connection attempt {attempt + 1}/{config.scale_to_zero_retry_attempts} failed "
                    f"(compute may be waking from scale-to-zero). Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

        raise ConnectionError(
            f"Failed to connect after {config.scale_to_zero_retry_attempts} attempts. "
            f"Lakebase compute may still be starting. Last error: {last_error}"
        )

    async def execute_query(
        self, sql: str, params: tuple = None, max_rows: int = None,
        tool_name: str = None,
    ) -> list[dict[str, Any]]:
        """Execute a SQL query (read-write) and return results as list of dicts."""
        effective_max = max_rows or config.max_rows
        tagged_sql = f"/* lakebase_mcp:{tool_name} */ {sql}" if tool_name else sql
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(tagged_sql, params, prepare=True)
                if cur.description:
                    rows = await cur.fetchmany(effective_max)
                    return [dict(row) for row in rows]
                return [{"affected_rows": cur.rowcount}]

    async def execute_readonly(
        self, sql: str, params: tuple = None, max_rows: int = None,
        tool_name: str = None,
    ) -> list[dict]:
        """Execute query in a read-only transaction, routed to replica if available."""
        effective_max = max_rows or config.max_rows
        tagged_sql = f"/* lakebase_mcp:{tool_name} */ {sql}" if tool_name else sql
        async with self.connection(prefer_replica=True) as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                async with conn.cursor() as cur:
                    await cur.execute(tagged_sql, params)
                    if cur.description:
                        rows = await cur.fetchmany(effective_max)
                        return [dict(row) for row in rows]
                    return []


pool = LakebasePool()
