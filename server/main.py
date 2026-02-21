"""Lakebase MCP Server — main entry point.

Merged: base server + autoscaling compute tools + replica pool initialization.
27 tools, 4 prompts, 1 resource.
"""
import logging
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from server.config import config
from server.db import pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan():
    """Initialize and tear down resources."""
    primary_conninfo = (
        f"host={config.lakebase_host} port={config.lakebase_port} "
        f"dbname={config.lakebase_database} "
        f"connect_timeout={config.query_timeout_seconds}"
    )

    replica_conninfo = None
    if config.replica_host:
        replica_conninfo = (
            f"host={config.replica_host} port={config.replica_port} "
            f"dbname={config.lakebase_database} "
            f"connect_timeout={config.query_timeout_seconds}"
        )

    await pool.initialize(primary_conninfo, replica_conninfo=replica_conninfo)
    logger.info("Lakebase MCP Server started (autoscaling-aware)")
    yield {"pool": pool}
    await pool.close()
    logger.info("Lakebase MCP Server stopped")


mcp = FastMCP(
    "lakebase_mcp",
    lifespan=app_lifespan,
    stateless_http=True,
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
    import os
    port = int(os.environ.get("APP_PORT", "8000"))
    mcp.run(transport="streamable_http", port=port)


if __name__ == "__main__":
    main()
