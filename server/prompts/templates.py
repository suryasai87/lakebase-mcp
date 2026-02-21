"""Reusable prompt templates for common Lakebase workflows."""
from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP):

    @mcp.prompt("lakebase_explore_database")
    async def explore_database() -> str:
        """Step-by-step guide for exploring a Lakebase database."""
        return """You are exploring a Databricks Lakebase PostgreSQL database. Follow these steps:

1. **List schemas**: Call lakebase_list_schemas to see available schemas
2. **List tables**: For each relevant schema, call lakebase_list_tables
3. **Describe key tables**: Call lakebase_describe_table for important tables
4. **Sample data**: Use lakebase_read_query with SELECT * FROM table LIMIT 10
5. **Profile data**: Call lakebase_profile_table for data quality overview
6. **Record insights**: Use lakebase_append_insight for notable findings

Always use lakebase_read_query (not lakebase_execute_query) for exploration to ensure read-only safety.
Read-only queries are automatically routed to the read replica if one is available."""

    @mcp.prompt("lakebase_safe_migration")
    async def safe_migration() -> str:
        """Guide for safely performing schema migrations using branching."""
        return """You are performing a safe database migration on Lakebase. Follow this workflow:

1. **Prepare**: Call lakebase_prepare_migration with your DDL SQL
   - This creates a temporary branch and applies the migration there
2. **Test**: Use lakebase_read_query on the migration branch to verify:
   - Schema changes applied correctly
   - Existing queries still work
   - No data loss or corruption
3. **Validate**: Call lakebase_explain_query on critical queries against the branch
4. **Complete**: Call lakebase_complete_migration with apply=true to merge, or apply=false to discard

NEVER apply DDL directly to the production branch. Always use the branch workflow."""

    @mcp.prompt("lakebase_setup_sync")
    async def setup_sync() -> str:
        """Guide for setting up Delta <-> Lakebase data synchronization."""
        return """You are setting up data synchronization between the Databricks Lakehouse and Lakebase.

Common patterns:
- **Feature serving**: Sync ML feature tables from Delta -> Lakebase for low-latency serving
- **Operational analytics**: Sync transactional Lakebase data -> Delta for BI/ML
- **Real-time apps**: Continuous sync for live dashboards

Steps:
1. Identify source and target tables
2. Choose direction (delta_to_lakebase or lakebase_to_delta)
3. Choose frequency (snapshot, triggered, or continuous)
4. Call lakebase_create_sync
5. Monitor with lakebase_list_syncs"""

    @mcp.prompt("lakebase_autoscaling_tuning")
    async def autoscaling_tuning() -> str:
        """Guide for tuning Lakebase autoscaling and scale-to-zero settings."""
        return """You are tuning Lakebase compute autoscaling. Follow this workflow:

1. **Check current state**: Call lakebase_get_compute_status to see current CU, state, and config
2. **Review metrics**: Call lakebase_get_compute_metrics to see CPU, memory, and working set trends
3. **Configure autoscaling**: Based on metrics:
   - If CPU is consistently high -> increase min_cu
   - If memory pressure -> increase max_cu
   - If mostly idle -> reduce min_cu or enable scale-to-zero
4. **Set scale-to-zero**: Use lakebase_configure_scale_to_zero
   - Dev/test: enabled, 60s timeout
   - Staging: enabled, 300s timeout
   - Production: disabled (for lowest latency)
5. **Create read replica**: If read-heavy workload, use lakebase_create_read_replica
   to offload analytics queries from the primary compute

Rules:
- Each CU = 2 GB RAM + proportional CPU
- Max autoscaling spread: 8 CU (e.g., min=2, max=10)
- Scale-to-zero wake-up: ~hundreds of milliseconds"""
