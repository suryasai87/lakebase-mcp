"""Lakebase MCP Server — main entry point.

Merged: base server + autoscaling compute tools + replica pool initialization.
31 tools, 4 prompts, 1 resource, dual-layer governance, UC permissions.
"""
import os
import logging
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from server.config import config
from server.db import pool
from server.governance.policy import build_governance_policy

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

# Build governance policy (env vars + optional YAML)
governance = build_governance_policy()

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
from server.tools.uc_governance import register_uc_governance_tools
from server.resources.insights import register_insight_resources
from server.prompts.templates import register_prompts

register_query_tools(mcp, governance)   # SQL governance via GovernancePolicy
register_schema_tools(mcp)
register_instance_tools(mcp)
register_branching_tools(mcp)
register_compute_tools(mcp)
register_migration_tools(mcp)
register_sync_tools(mcp)
register_quality_tools(mcp)
register_feature_store_tools(mcp)
register_uc_governance_tools(mcp)       # UC permissions & governance tools
register_insight_resources(mcp)
register_prompts(mcp)


def _apply_tool_governance(mcp_instance: FastMCP):
    """Apply tool-level governance middleware by wrapping ToolManager.call_tool.

    Intercepts every tool invocation to check tool access permissions
    before the handler executes. Only active when tool governance is configured
    (tool_profile, tool_allowed, or tool_denied env vars are set).
    """
    if not governance.tool_policy.allowed_tools and not governance.tool_policy.denied_tools:
        logger.info("Tool-level governance: inactive (no tool restrictions configured)")
        return

    original_call_tool = mcp_instance._tool_manager.call_tool

    async def governed_call_tool(name, arguments, context=None, convert_result=False):
        allowed, error_msg = governance.check_tool_access(name)
        if not allowed:
            return [{"type": "text", "text": f"Error: {error_msg}"}]
        return await original_call_tool(name, arguments, context, convert_result)

    mcp_instance._tool_manager.call_tool = governed_call_tool
    logger.info(
        f"Tool-level governance: active "
        f"(allow={len(governance.tool_policy.allowed_tools)}, "
        f"deny={len(governance.tool_policy.denied_tools)})"
    )


_apply_tool_governance(mcp)


def main():
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
