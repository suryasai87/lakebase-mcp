"""Lakebase MCP Server — main entry point.

Merged: base server + autoscaling compute tools + replica pool initialization.
27 tools, 4 prompts, 1 resource.
"""
import os
import logging
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from server.config import config
from server.db import pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_conninfo(host: str, port: int) -> str:
    """Build psycopg conninfo string.

    Authentication is handled externally via:
    - .pgpass file (local dev with oauth_auto_token_rotation)
    - Databricks SP token (on Databricks Apps, set PGPASSWORD or .pgpass)
    - LAKEBASE_PG_USER / LAKEBASE_PG_PASSWORD env vars (explicit)
    """
    parts = [
        f"host={host}",
        f"port={port}",
        f"dbname={config.lakebase_database}",
        f"sslmode=require",
        f"connect_timeout={config.query_timeout_seconds}",
    ]

    pg_user = os.environ.get("LAKEBASE_PG_USER", "")
    pg_password = os.environ.get("LAKEBASE_PG_PASSWORD", "")

    if pg_user:
        parts.append(f"user={pg_user}")
    if pg_password:
        parts.append(f"password={pg_password}")

    return " ".join(parts)


@asynccontextmanager
async def app_lifespan():
    """Initialize and tear down resources."""
    if config.lakebase_host:
        primary_conninfo = _build_conninfo(config.lakebase_host, config.lakebase_port)
        replica_conninfo = None
        if config.replica_host:
            replica_conninfo = _build_conninfo(config.replica_host, config.replica_port)

        try:
            await pool.initialize(primary_conninfo, replica_conninfo=replica_conninfo)
            logger.info("Lakebase MCP Server started (autoscaling-aware, pool connected)")
        except Exception as e:
            logger.warning(
                f"Pool initialization failed (tools will retry on first call): {e}"
            )
    else:
        logger.info(
            "Lakebase MCP Server started (no LAKEBASE_HOST set — "
            "compute/schema tools available, query tools will fail until configured)"
        )

    yield {"pool": pool}

    try:
        await pool.close()
    except Exception:
        pass
    logger.info("Lakebase MCP Server stopped")


_port = int(os.environ.get("APP_PORT", "8000"))

mcp = FastMCP(
    "lakebase_mcp",
    lifespan=app_lifespan,
    stateless_http=True,
    host="0.0.0.0",
    port=_port,
)

# Register all tool modules
from server.tools.query import register_query_tools
from server.tools.schema import register_schema_tools
from server.tools.instance import register_instance_tools
from server.tools.branching import register_branching_tools
from server.tools.compute import register_compute_tools
from server.tools.migration import register_migration_tools
from server.tools.sync import register_sync_tools
from server.tools.quality import register_quality_tools
from server.tools.feature_store import register_feature_store_tools
from server.resources.insights import register_insight_resources
from server.prompts.templates import register_prompts

register_query_tools(mcp)
register_schema_tools(mcp)
register_instance_tools(mcp)
register_branching_tools(mcp)
register_compute_tools(mcp)       # NEW: 6 autoscaling tools
register_migration_tools(mcp)
register_sync_tools(mcp)
register_quality_tools(mcp)
register_feature_store_tools(mcp)
register_insight_resources(mcp)
register_prompts(mcp)


def main():
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
