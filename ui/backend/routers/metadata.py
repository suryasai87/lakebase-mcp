"""API routes serving MCP server metadata.

Imports governance data structures directly from server/ modules
to stay in sync. Tool descriptions maintained here alongside source.
"""
from fastapi import APIRouter

from server.governance.tool_guard import TOOL_CATEGORIES, TOOL_PROFILES
from server.governance.sql_guard import PROFILES as SQL_PROFILES, SQLStatementType

router = APIRouter()

# Static tool metadata — sourced from server/tools/*.py docstrings and annotations.
# Each entry mirrors the @mcp.tool() registration in the corresponding tool file.
TOOL_METADATA = {
    # --- sql_query (server/tools/query.py) ---
    "lakebase_execute_query": {
        "title": "Execute SQL Query",
        "description": "Execute a SQL query against the connected Lakebase PostgreSQL database. Supports SELECT, INSERT, UPDATE, DELETE and DDL statements governed by the SQL governance policy.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "sql": {"type": "string", "required": True, "description": "SQL query to execute"},
            "max_rows": {"type": "integer", "required": False, "default": 100, "description": "Maximum rows to return (1-1000)"},
            "response_format": {"type": "enum", "values": ["markdown", "json"], "default": "markdown"},
        },
    },
    "lakebase_read_query": {
        "title": "Execute Read-Only SQL Query",
        "description": "Execute a read-only SQL query against Lakebase. Only SELECT and EXPLAIN statements are allowed. Runs inside a READ ONLY transaction.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "sql": {"type": "string", "required": True, "description": "SQL query to execute"},
            "max_rows": {"type": "integer", "required": False, "default": 100, "description": "Maximum rows to return (1-1000)"},
            "response_format": {"type": "enum", "values": ["markdown", "json"], "default": "markdown"},
        },
    },
    "lakebase_explain_query": {
        "title": "Explain Query Execution Plan",
        "description": "Get the PostgreSQL execution plan for a SQL query using EXPLAIN. Helps understand query performance and identify missing indexes.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "sql": {"type": "string", "required": True, "description": "SQL query to analyze"},
            "analyze": {"type": "boolean", "required": False, "default": False, "description": "Run EXPLAIN ANALYZE (actually executes the query)"},
        },
    },
    # --- schema_read (server/tools/schema.py) ---
    "lakebase_list_schemas": {
        "title": "List Database Schemas",
        "description": "List all schemas in the connected Lakebase database. Returns schema names, owners, and descriptions.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "response_format": {"type": "enum", "values": ["markdown", "json"], "default": "markdown"},
        },
    },
    "lakebase_list_tables": {
        "title": "List Tables in Schema",
        "description": "List all tables and views in a given schema. Shows table name, type, row estimate, and size.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "schema_name": {"type": "string", "required": False, "default": "public", "description": "Schema to list tables from"},
            "response_format": {"type": "enum", "values": ["markdown", "json"], "default": "markdown"},
        },
    },
    "lakebase_describe_table": {
        "title": "Describe Table Schema",
        "description": "Get the full schema of a table: column names, data types, nullability, defaults, constraints, and indexes.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "table_name": {"type": "string", "required": True, "description": "Fully qualified table name (schema.table)"},
            "response_format": {"type": "enum", "values": ["markdown", "json"], "default": "markdown"},
        },
    },
    "lakebase_object_tree": {
        "title": "Get Database Object Tree",
        "description": "Get a hierarchical tree view of all database objects: schemas -> tables -> columns.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "schema_name": {"type": "string", "required": False, "description": "Filter to a specific schema"},
        },
    },
    # --- project_read (server/tools/instance.py) ---
    "lakebase_list_projects": {
        "title": "List Lakebase Projects",
        "description": "List all Lakebase projects accessible to the current user. Shows project name, state, catalog, region, branches, and compute status.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "catalog": {"type": "string", "required": False, "description": "Filter by UC catalog name"},
        },
    },
    "lakebase_describe_project": {
        "title": "Describe Lakebase Project",
        "description": "Get detailed information about a Lakebase project: configuration, branches, compute sizes, storage usage, and status.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
        },
    },
    "lakebase_get_connection_string": {
        "title": "Get Connection String",
        "description": "Get the PostgreSQL connection string for a Lakebase project/branch. Returns host, port, database, and temporary credentials.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
            "compute_type": {"type": "string", "required": False, "default": "primary", "description": "'primary' or 'replica'"},
        },
    },
    # --- branch_read (server/tools/branching.py) ---
    "lakebase_list_branches": {
        "title": "List Database Branches",
        "description": "List all branches of a Lakebase project. Shows branch name, creation time, parent branch, compute status, and CU allocation.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
        },
    },
    # --- branch_write (server/tools/branching.py) ---
    "lakebase_create_branch": {
        "title": "Create Database Branch",
        "description": "Create a copy-on-write branch of a Lakebase project. Branches are instant clones — perfect for feature development, safe migrations, and experiments.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Project to branch from"},
            "branch_name": {"type": "string", "required": True, "description": "Name for the new branch"},
            "parent_branch": {"type": "string", "required": False, "description": "Parent branch (defaults to production)"},
        },
    },
    "lakebase_delete_branch": {
        "title": "Delete Database Branch",
        "description": "Delete a Lakebase database branch. This is irreversible. The 'production' branch cannot be deleted.",
        "readOnlyHint": False,
        "destructiveHint": True,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": True, "description": "Branch to delete"},
        },
    },
    # --- compute_read (server/tools/compute.py) ---
    "lakebase_get_compute_status": {
        "title": "Get Compute Status",
        "description": "Get the current status of a Lakebase branch compute: state, CU allocation, autoscaling range, active connections, and uptime.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
        },
    },
    "lakebase_get_compute_metrics": {
        "title": "Get Compute Metrics",
        "description": "Get compute metrics: CPU utilization, memory usage, working set size, active connections, and state transitions.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
            "period_minutes": {"type": "integer", "required": False, "default": 60, "description": "Metrics lookback period (5-1440 minutes)"},
        },
    },
    # --- compute_write (server/tools/compute.py) ---
    "lakebase_configure_autoscaling": {
        "title": "Configure Compute Autoscaling",
        "description": "Configure autoscaling for a Lakebase branch compute. Each CU = 2 GB RAM. Max spread is 8 CU. Scaling happens without connection interruptions.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
            "min_cu": {"type": "number", "required": True, "description": "Minimum compute units (0.5-32)"},
            "max_cu": {"type": "number", "required": True, "description": "Maximum compute units"},
            "enable_autoscaling": {"type": "boolean", "required": False, "default": True, "description": "Enable/disable autoscaling"},
        },
    },
    "lakebase_configure_scale_to_zero": {
        "title": "Configure Scale-to-Zero",
        "description": "Configure scale-to-zero behavior. Compute suspends after inactivity timeout, reducing costs to zero. Resumes in hundreds of milliseconds.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
            "enabled": {"type": "boolean", "required": True, "description": "Enable or disable scale-to-zero"},
            "timeout_seconds": {"type": "integer", "required": False, "default": 300, "description": "Inactivity timeout (60-3600 seconds)"},
        },
    },
    "lakebase_restart_compute": {
        "title": "Restart Compute",
        "description": "Restart a Lakebase branch compute. WARNING: Interrupts all active connections.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
        },
    },
    "lakebase_create_read_replica": {
        "title": "Create Read Replica",
        "description": "Create a read replica for a Lakebase branch. Shares storage layer — no data duplication. Ideal for offloading analytics queries.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "branch_name": {"type": "string", "required": False, "default": "production", "description": "Branch name"},
            "min_cu": {"type": "number", "required": False, "default": 0.5, "description": "Min CU for replica"},
            "max_cu": {"type": "number", "required": False, "default": 4, "description": "Max CU for replica"},
        },
    },
    # --- migration (server/tools/migration.py) ---
    "lakebase_prepare_migration": {
        "title": "Prepare Database Migration",
        "description": "Prepare a migration safely using branching. Creates a temporary branch, applies DDL, returns branch for testing before committing.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "migration_sql": {"type": "string", "required": True, "description": "DDL migration SQL"},
            "description": {"type": "string", "required": False, "description": "Migration description"},
        },
    },
    "lakebase_complete_migration": {
        "title": "Complete Database Migration",
        "description": "Complete a prepared migration — apply to production (apply=true) or discard (apply=false).",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
            "migration_branch": {"type": "string", "required": True, "description": "Temporary migration branch name"},
            "apply": {"type": "boolean", "required": False, "default": True, "description": "True=apply, False=discard"},
        },
    },
    # --- sync_read (server/tools/sync.py) ---
    "lakebase_list_syncs": {
        "title": "List Sync Pipelines",
        "description": "List all data sync pipelines for a Lakebase project. Shows source, target, direction, frequency, and status.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
        },
    },
    # --- sync_write (server/tools/sync.py) ---
    "lakebase_create_sync": {
        "title": "Create Data Sync Pipeline",
        "description": "Create a data synchronization pipeline between Delta tables (Unity Catalog) and Lakebase. Supports snapshot, triggered, and continuous CDC sync.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "source_table": {"type": "string", "required": True, "description": "Source table"},
            "target_table": {"type": "string", "required": True, "description": "Target table"},
            "direction": {"type": "enum", "values": ["delta_to_lakebase", "lakebase_to_delta"], "required": True},
            "frequency": {"type": "enum", "values": ["snapshot", "triggered", "continuous"], "default": "triggered"},
            "project_name": {"type": "string", "required": True, "description": "Lakebase project name"},
        },
    },
    # --- quality (server/tools/quality.py) ---
    "lakebase_profile_table": {
        "title": "Profile Table Data Quality",
        "description": "Generate a comprehensive data profile: null counts, distinct values, min/max/mean/stddev for numeric columns, top frequent values.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "table_name": {"type": "string", "required": True, "description": "Table to profile (schema.table)"},
            "sample_size": {"type": "integer", "required": False, "default": 10000, "description": "Rows to sample (100-1000000)"},
            "response_format": {"type": "enum", "values": ["markdown", "json"], "default": "markdown"},
        },
    },
    # --- feature_read (server/tools/feature_store.py) ---
    "lakebase_lookup_features": {
        "title": "Lookup Online Features",
        "description": "Lookup real-time features from the Lakebase online feature store with low-latency (<10ms) point lookups for ML serving.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "feature_table": {"type": "string", "required": True, "description": "Feature table name (schema.table)"},
            "entity_keys": {"type": "object", "required": True, "description": "Entity key-value pairs for lookup"},
            "features": {"type": "array", "required": False, "description": "Specific feature columns to return"},
        },
    },
    "lakebase_list_feature_tables": {
        "title": "List Feature Tables",
        "description": "List all feature tables in the specified schema synced from the lakehouse for online serving.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "schema_name": {"type": "string", "required": False, "default": "features", "description": "Schema containing feature tables"},
        },
    },
    # --- insight (server/resources/insights.py) ---
    "lakebase_append_insight": {
        "title": "Record Data Insight",
        "description": "Record a data insight discovered during analysis. Insights are aggregated in the memo://insights resource.",
        "readOnlyHint": False,
        "destructiveHint": False,
        "parameters": {
            "insight": {"type": "string", "required": True, "description": "Data insight to record"},
        },
    },
    # --- uc_governance (server/tools/uc_governance.py) ---
    "lakebase_get_uc_permissions": {
        "title": "Get Unity Catalog Permissions",
        "description": "Get UC effective permissions on a Lakebase object. Shows direct and inherited grants with principal and privilege details.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "securable_type": {"type": "string", "required": False, "default": "SCHEMA", "description": "Object type: CATALOG, SCHEMA, TABLE, etc."},
            "full_name": {"type": "string", "required": True, "description": "Fully qualified object name"},
            "principal": {"type": "string", "required": False, "description": "Filter by principal"},
        },
    },
    "lakebase_check_my_access": {
        "title": "Check My Access",
        "description": "Check the current user's effective permissions on a Lakebase catalog/schema/table before executing queries.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "catalog": {"type": "string", "required": True, "description": "Catalog name"},
            "schema_name": {"type": "string", "required": False, "description": "Schema name"},
            "table_name": {"type": "string", "required": False, "description": "Table name"},
        },
    },
    "lakebase_governance_summary": {
        "title": "Governance Summary",
        "description": "Get a combined governance summary: MCP tool governance + UC permissions. Shows effective access and recommended profile.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "catalog": {"type": "string", "required": False, "description": "Catalog to summarize"},
        },
    },
    "lakebase_list_catalog_grants": {
        "title": "List Catalog Grants",
        "description": "List all grants on a Lakebase catalog and optionally its schemas for auditing access control.",
        "readOnlyHint": True,
        "destructiveHint": False,
        "parameters": {
            "catalog": {"type": "string", "required": True, "description": "Catalog name"},
            "include_schemas": {"type": "boolean", "required": False, "default": True, "description": "Also list schema grants"},
        },
    },
}

PROMPT_METADATA = [
    {
        "name": "lakebase_explore_database",
        "title": "Explore Database",
        "description": "Step-by-step guide for exploring a Lakebase database: list schemas, tables, describe, sample, profile, record insights.",
    },
    {
        "name": "lakebase_safe_migration",
        "title": "Safe Migration",
        "description": "Guide for safely performing schema migrations using Lakebase branching: prepare, test, validate, complete.",
    },
    {
        "name": "lakebase_setup_sync",
        "title": "Setup Data Sync",
        "description": "Guide for setting up Delta <-> Lakebase data synchronization for feature serving, analytics, and real-time apps.",
    },
    {
        "name": "lakebase_autoscaling_tuning",
        "title": "Autoscaling Tuning",
        "description": "Guide for tuning Lakebase compute autoscaling and scale-to-zero settings based on workload metrics.",
    },
]

RESOURCE_METADATA = [
    {
        "uri": "memo://insights",
        "name": "Session Insights",
        "description": "Aggregated data insights discovered during the current session. Populated via lakebase_append_insight.",
    },
]

ENV_VARS = [
    {"name": "LAKEBASE_PROJECT", "description": "Default Lakebase project name", "required": False},
    {"name": "LAKEBASE_BRANCH", "description": "Default branch name", "default": "production", "required": False},
    {"name": "LAKEBASE_COMPUTE_ENDPOINT", "description": "PostgreSQL connection endpoint", "required": True},
    {"name": "LAKEBASE_TOKEN_PATH", "description": "Path to Databricks OAuth token", "required": False},
    {"name": "LAKEBASE_ALLOW_WRITE", "description": "Legacy write toggle (true/false)", "default": "false", "required": False},
    {"name": "LAKEBASE_SQL_PROFILE", "description": "SQL governance profile: read_only, analyst, developer, admin", "required": False},
    {"name": "LAKEBASE_TOOL_PROFILE", "description": "Tool access profile: read_only, analyst, developer, admin", "required": False},
    {"name": "LAKEBASE_SQL_ALLOWED_TYPES", "description": "Comma-separated additional allowed SQL types", "required": False},
    {"name": "LAKEBASE_SQL_DENIED_TYPES", "description": "Comma-separated denied SQL types (overrides profile)", "required": False},
    {"name": "LAKEBASE_TOOL_ALLOWED_CATEGORIES", "description": "Comma-separated additional allowed tool categories", "required": False},
    {"name": "LAKEBASE_TOOL_DENIED_CATEGORIES", "description": "Comma-separated denied tool categories", "required": False},
    {"name": "LAKEBASE_TOOL_ALLOWED", "description": "Comma-separated individual tool allow list", "required": False},
    {"name": "LAKEBASE_TOOL_DENIED", "description": "Comma-separated individual tool deny list", "required": False},
    {"name": "LAKEBASE_GOVERNANCE_CONFIG", "description": "Path to governance YAML config file", "required": False},
]

CATEGORY_DESCRIPTIONS = {
    "sql_query": "SQL query execution with governance controls",
    "schema_read": "Schema and metadata discovery",
    "project_read": "Lakebase project lifecycle management",
    "branch_read": "Database branch listing",
    "branch_write": "Database branch creation and deletion",
    "compute_read": "Compute status and metrics monitoring",
    "compute_write": "Compute autoscaling, scale-to-zero, and replicas",
    "migration": "Safe database migrations using branching",
    "sync_read": "Data sync pipeline monitoring",
    "sync_write": "Data sync pipeline creation",
    "quality": "Data quality and profiling",
    "feature_read": "Online feature store lookups",
    "insight": "Session insight recording",
    "uc_governance": "Unity Catalog permissions and governance",
}


@router.get("/tools")
async def get_tools():
    tools = []
    for category, tool_names in TOOL_CATEGORIES.items():
        for tool_name in tool_names:
            meta = TOOL_METADATA.get(tool_name, {})
            tools.append({
                "name": tool_name,
                "category": category,
                **meta,
            })
    return {"tools": tools, "count": len(tools)}


@router.get("/categories")
async def get_categories():
    categories = []
    for cat, tool_names in TOOL_CATEGORIES.items():
        categories.append({
            "name": cat,
            "description": CATEGORY_DESCRIPTIONS.get(cat, ""),
            "tools": tool_names,
            "tool_count": len(tool_names),
        })
    return {"categories": categories, "count": len(categories)}


@router.get("/governance/matrix")
async def get_governance_matrix():
    matrix = {}
    for profile_name, allowed_cats in TOOL_PROFILES.items():
        allowed_tools = set()
        for cat in allowed_cats:
            if cat in TOOL_CATEGORIES:
                allowed_tools.update(TOOL_CATEGORIES[cat])
        matrix[profile_name] = {
            tool: tool in allowed_tools
            for cat_tools in TOOL_CATEGORIES.values()
            for tool in cat_tools
        }
    return matrix


@router.get("/governance/sql-matrix")
async def get_sql_matrix():
    all_types = sorted(t.value for t in SQLStatementType)
    matrix = {}
    for profile_name, allowed_set in SQL_PROFILES.items():
        allowed_values = {t.value for t in allowed_set}
        matrix[profile_name] = {
            sql_type: sql_type in allowed_values
            for sql_type in all_types
        }
    return {"types": all_types, "profiles": matrix}


@router.get("/governance/profiles")
async def get_profiles():
    profiles = {}
    for profile_name, allowed_cats in TOOL_PROFILES.items():
        allowed_tools = set()
        for cat in allowed_cats:
            if cat in TOOL_CATEGORIES:
                allowed_tools.update(TOOL_CATEGORIES[cat])
        all_tools = {t for tools in TOOL_CATEGORIES.values() for t in tools}
        sql_allowed = sorted(t.value for t in SQL_PROFILES.get(profile_name, set()))
        profiles[profile_name] = {
            "tool_categories": allowed_cats,
            "tools_allowed": len(allowed_tools),
            "tools_denied": len(all_tools - allowed_tools),
            "sql_types_allowed": sql_allowed,
        }
    return profiles


@router.get("/prompts")
async def get_prompts():
    return {"prompts": PROMPT_METADATA, "count": len(PROMPT_METADATA)}


@router.get("/resources")
async def get_resources():
    return {"resources": RESOURCE_METADATA, "count": len(RESOURCE_METADATA)}


@router.get("/config/env-vars")
async def get_env_vars():
    return {"variables": ENV_VARS, "count": len(ENV_VARS)}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "lakebase-mcp-ui"}


# ---------------------------------------------------------------------------
# Pricing data (static — reliable, no external API dependency)
# ---------------------------------------------------------------------------

MODEL_PRICING = {
    "models": [
        {
            "id": "claude-opus-4-6",
            "name": "Claude Opus 4.6",
            "input_per_mtok": 5.0,
            "output_per_mtok": 25.0,
            "cache_write": 6.25,
            "cache_hit": 0.50,
        },
        {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "input_per_mtok": 3.0,
            "output_per_mtok": 15.0,
            "cache_write": 3.75,
            "cache_hit": 0.30,
        },
        {
            "id": "claude-haiku-4-5",
            "name": "Claude Haiku 4.5",
            "input_per_mtok": 1.0,
            "output_per_mtok": 5.0,
            "cache_write": 1.25,
            "cache_hit": 0.10,
        },
    ],
    "tool_overhead_tokens": 6000,
    "system_prompt_overhead": 346,
    "avg_input_per_call": 5000,
    "avg_output_per_call": 1000,
}

COMPUTE_PRICING = {
    "regions": [
        {"id": "us-east-1", "name": "US East (N. Virginia)", "dbu_rate": 0.70},
        {"id": "us-west-2", "name": "US West (Oregon)", "dbu_rate": 0.70},
        {"id": "eu-west-1", "name": "EU West (Ireland)", "dbu_rate": 0.80},
        {"id": "ap-southeast-1", "name": "Asia Pacific (Singapore)", "dbu_rate": 0.85},
        {"id": "ap-northeast-1", "name": "Asia Pacific (Tokyo)", "dbu_rate": 0.90},
    ],
    "compute_units": [
        {"cu": 0.5, "ram_gb": 1, "dbu_per_hour": 0.5},
        {"cu": 1, "ram_gb": 2, "dbu_per_hour": 1.0},
        {"cu": 2, "ram_gb": 4, "dbu_per_hour": 2.0},
        {"cu": 4, "ram_gb": 8, "dbu_per_hour": 4.0},
        {"cu": 8, "ram_gb": 16, "dbu_per_hour": 8.0},
        {"cu": 16, "ram_gb": 32, "dbu_per_hour": 16.0},
        {"cu": 32, "ram_gb": 64, "dbu_per_hour": 32.0},
    ],
    "storage_per_gb_month": 0.023,
}

COMPARISON_PRICING = {
    "platforms": [
        {
            "name": "Lakebase",
            "provider": "Databricks",
            "min_compute_hr": 0.35,
            "session_cost_8_calls": 0.42,
            "monthly_prod": 365,
            "branching": "Free (copy-on-write)",
            "scale_to_zero": True,
            "mcp_tools": 31,
            "governance_layers": 2,
            "highlights": [
                "10-15x cheaper compute",
                "Free instant branching",
                "Scale-to-zero (sub-second resume)",
                "Dual-layer governance",
                "Async connection pooling",
                "Full MCP annotations",
            ],
        },
        {
            "name": "Snowflake",
            "provider": "Snowflake",
            "min_compute_hr": 3.00,
            "session_cost_8_calls": 1.05,
            "monthly_prod": 8640,
            "branching": "N/A (clone = full cost)",
            "scale_to_zero": True,
            "mcp_tools": 15,
            "governance_layers": 1,
            "highlights": [
                "Managed MCP server (CREATE MCP SERVER)",
                "Cortex Analyst ($0.20/message)",
                "Cortex Search (RAG built-in)",
            ],
        },
        {
            "name": "Teradata",
            "provider": "Teradata",
            "min_compute_hr": 4.80,
            "session_cost_8_calls": 1.05,
            "monthly_prod": 5184,
            "branching": "N/A",
            "scale_to_zero": False,
            "mcp_tools": 100,
            "governance_layers": 1,
            "highlights": [
                "100+ tools (most comprehensive)",
                "Enterprise workload management",
                "ClearScape Analytics built-in",
            ],
        },
    ],
}


@router.get("/pricing/models")
async def get_model_pricing():
    return MODEL_PRICING


@router.get("/pricing/compute")
async def get_compute_pricing():
    return COMPUTE_PRICING


@router.get("/pricing/comparison")
async def get_comparison_pricing():
    return COMPARISON_PRICING
