# Lakebase MCP Server

A production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for **Databricks Lakebase** — the managed PostgreSQL service on Databricks with autoscaling, branching, and Unity Catalog governance.

This server gives AI agents (Claude, GPT, Copilot, etc.) full control over Lakebase databases: querying, schema exploration, compute management, branching, migrations, Delta sync, data quality profiling, and feature serving — all through a standard MCP interface.

---

## Key Capabilities

- **49 tools** across 14 categories — query, schema, projects, branching, compute, migration, sync, synced tables, endpoints, monitoring, quality, query optimization, feature store, UC governance
- **4 prompt templates** — guided workflows for exploration, migration, sync, and autoscaling tuning
- **1 session resource** — `memo://insights` for accumulating observations during analysis
- **Interactive UI dashboard** — 5-page React + FastAPI app with tool explorer, governance matrix, connection wizard, and pricing calculator
- **Autoscaling-aware** — exponential backoff retry for scale-to-zero, read replica routing, compute lifecycle management
- **Safety-first** — write guard, dangerous function blocking, production branch protection, read-only transaction enforcement
- **Dual output** — markdown tables (human-friendly) or JSON (programmatic) for every tool
- **Fully async** — built on FastMCP with `psycopg` 3.x async connection pooling
- **Query cost attribution** — SQL comment tagging (`/* lakebase_mcp:tool_name */`) + `application_name` for pg_stat_activity
- **Transport flexibility** — streamable-http (default, production) or stdio (`--transport stdio` for Claude Desktop)

---

## Tool Reference (49 Tools)

### Query Tools (3)

| Tool | Description | Read-Only |
|------|-------------|-----------|
| `lakebase_read_query` | Execute read-only SQL (routes to replica if available). Wrapped in `READ ONLY` transaction | Yes |
| `lakebase_execute_query` | Execute read/write SQL. Governed by SQL profile (`LAKEBASE_SQL_PROFILE` or `LAKEBASE_ALLOW_WRITE`). Blocks `pg_terminate_backend`, `pg_cancel_backend`, `pg_reload_conf` | No |
| `lakebase_explain_query` | Show PostgreSQL execution plan (`EXPLAIN FORMAT JSON, VERBOSE`). Optional `ANALYZE` + `BUFFERS` for actual timing | Yes |

### Schema Discovery Tools (4)

| Tool | Description |
|------|-------------|
| `lakebase_list_schemas` | List user schemas (excludes `pg_catalog`, `information_schema`, `pg_toast`) with owners |
| `lakebase_list_tables` | List tables/views in a schema with row estimates (`pg_stat_get_live_tuples`) and sizes (`pg_total_relation_size`) |
| `lakebase_describe_table` | Full table schema: columns, types, nullability, defaults, length/precision, indexes with definitions |
| `lakebase_object_tree` | Hierarchical JSON tree: schemas -> tables -> columns. Includes TABLE, VIEW, MATERIALIZED VIEW |

### Project Management Tools (7)

| Tool | Description |
|------|-------------|
| `lakebase_list_projects` | List all Lakebase projects in the workspace via Databricks API. Optional catalog filter |
| `lakebase_describe_project` | Detailed project info: configuration, branches, compute sizes, storage usage, sync pipelines |
| `lakebase_get_connection_string` | Get PostgreSQL connection string with temporary credentials via Databricks credential vending. Supports primary and replica endpoints. **Passwords redacted by default** |
| `lakebase_create_project` | Create a new Lakebase project via Databricks REST API. Specify catalog, tier, and initial compute configuration |
| `lakebase_delete_project` | Delete a Lakebase project (irreversible). Requires confirmation parameter to prevent accidental deletion |
| `lakebase_rotate_credentials` | Rotate PostgreSQL credentials for a Lakebase project. Generates new short-lived tokens via credential vending |
| `lakebase_list_credentials` | List active credentials/sessions for a Lakebase project. Shows credential age and expiration |

### Branching Tools (3)

| Tool | Description |
|------|-------------|
| `lakebase_create_branch` | Create a copy-on-write branch (instant, shared storage). Optional parent branch selection |
| `lakebase_list_branches` | List all branches with creation time, parent, compute status, CU allocation |
| `lakebase_delete_branch` | Delete a branch (irreversible). **Cannot delete production/main** — enforced server-side |

### Compute Management Tools (6)

| Tool | Description |
|------|-------------|
| `lakebase_get_compute_status` | Current state (`active`/`suspended`/`scaling_up`/`scaling_down`), CU allocation, connections, uptime |
| `lakebase_configure_autoscaling` | Set min/max CU range. Rules: each CU = 2 GB RAM, max spread = 16 CU, 0.5–32 CU range. No restart needed |
| `lakebase_configure_scale_to_zero` | Enable/disable auto-suspend with inactivity timeout (60–3600s). Dev: 60s, Staging: 300s, Prod: disabled |
| `lakebase_get_compute_metrics` | Time-series: CPU%, memory%, working set, connections, state transitions. Lookback: 5–1440 minutes |
| `lakebase_restart_compute` | Restart compute (interrupts active connections). For config changes, performance issues, or extension updates |
| `lakebase_create_read_replica` | Create read replica with independent autoscaling. Shares storage (no data duplication) |

### Migration Tools (2)

| Tool | Description |
|------|-------------|
| `lakebase_prepare_migration` | Create temporary branch from production, execute DDL migration SQL on the branch, and validate results before promoting |
| `lakebase_complete_migration` | `apply=true`: replay DDL on production branch and clean up migration branch. `apply=false`: delete branch, discard changes |

### Sync Tools (2)

| Tool | Description |
|------|-------------|
| `lakebase_create_sync` | Create Delta <-> Lakebase sync pipeline. Directions: `delta_to_lakebase`, `lakebase_to_delta`. Frequencies: `snapshot`, `triggered`, `continuous` |
| `lakebase_list_syncs` | List all sync pipelines with source, target, direction, frequency, status, last sync time |

### Synced Tables Tools (4)

| Tool | Description |
|------|-------------|
| `lakebase_list_synced_tables` | List all synced tables for a Lakebase project via the Synced Tables API. Shows source Delta table, sync status, and last sync time |
| `lakebase_create_synced_table` | Create a new synced table (Delta to Lakebase reverse sync) via `/api/2.0/lakebase/projects/{name}/synced_tables`. Specify source catalog, schema, and table |
| `lakebase_delete_synced_table` | Remove a synced table configuration. Stops ongoing sync and cleans up the Lakebase-side replica |
| `lakebase_get_synced_table_status` | Get detailed sync status for a specific synced table: lag, throughput, last sync time, error state |

### Endpoint Management Tools (4)

| Tool | Description |
|------|-------------|
| `lakebase_list_endpoints` | List all endpoints (primary and replica) for a Lakebase project with connection details and status |
| `lakebase_create_endpoint` | Create a new endpoint (e.g., read replica endpoint) for a Lakebase project via REST API |
| `lakebase_update_endpoint` | Update endpoint configuration: autoscaling CU range, allowed IP list, SSL mode |
| `lakebase_delete_endpoint` | Delete a non-primary endpoint. Primary endpoints cannot be deleted |

### Monitoring Tools (3)

| Tool | Description |
|------|-------------|
| `lakebase_replication_status` | Query `pg_stat_replication` for active replication slots, WAL lag, replay lag, and replica state |
| `lakebase_wal_statistics` | Query `pg_stat_wal` for WAL generation rate, buffers, sync metrics. Useful for sizing and CDC throughput estimation |
| `lakebase_cdc_monitor` | Monitor WAL-based CDC (`wal2delta`) pipeline: slot status, confirmed flush LSN, replication lag, consumer health |

### Data Quality Tools (1)

| Tool | Description |
|------|-------------|
| `lakebase_profile_table` | Per-column statistics: null%, cardinality, min/max, mean, stddev (numeric), distinct counts. Configurable sample size (100–1M rows) |

### Query Optimization Tools (3)

| Tool | Description |
|------|-------------|
| `lakebase_list_slow_queries` | List slowest queries from `pg_stat_statements` ranked by total/mean time, calls, or rows. Shows call count, timing stats, rows per call, and shared buffer cache hit ratio. Requires `pg_stat_statements` extension |
| `lakebase_index_usage` | Analyze index usage from `pg_stat_user_indexes` to find unused or underused indexes. Shows scan count, tuple reads, size, and flags non-primary/unique indexes with zero scans |
| `lakebase_table_scan_stats` | Compare sequential vs index scan statistics from `pg_stat_user_tables`. Identifies tables with high seq scans and low index usage that are candidates for new indexes |

### Feature Store Tools (2)

| Tool | Description |
|------|-------------|
| `lakebase_lookup_features` | Low-latency (<10ms) feature point lookup by entity keys. Supports column selection |
| `lakebase_list_feature_tables` | List all feature-serving tables in a schema with row counts and sizes |

### Unity Catalog Governance Tools (4)

| Tool | Description |
|------|-------------|
| `lakebase_get_uc_permissions` | Get effective UC permissions on any securable (catalog, schema, table). Shows direct and inherited grants with source |
| `lakebase_check_my_access` | Check current user's effective privileges on a Lakebase catalog/schema/table. Shows SELECT, MODIFY, CREATE status |
| `lakebase_governance_summary` | Combined view: MCP SQL governance + MCP tool governance + UC permissions. Recommends optimal profile |
| `lakebase_list_catalog_grants` | List all grants on a catalog and its schemas. Shows which principals have what privileges |

### Insights (1 tool + 1 resource)

| Name | Type | Description |
|------|------|-------------|
| `lakebase_append_insight` | Tool | Record observations during analysis. Accumulates in session memo |
| `memo://insights` | Resource | Read all recorded insights as a bullet list |

---

## Prompt Templates (4)

Reusable prompt templates that guide agents through common multi-step workflows:

| Prompt | Use Case | Tools Used |
|--------|----------|------------|
| `lakebase_explore_database` | Step-by-step database exploration | `list_schemas` -> `list_tables` -> `describe_table` -> `read_query` -> `profile_table` -> `append_insight` |
| `lakebase_safe_migration` | Branch-based schema migration | `prepare_migration` -> `read_query` (test) -> `explain_query` (validate) -> `complete_migration` |
| `lakebase_setup_sync` | Delta <-> Lakebase synchronization | `create_sync` -> `list_syncs` |
| `lakebase_autoscaling_tuning` | Monitor and tune compute autoscaling | `get_compute_status` -> `get_compute_metrics` -> `configure_autoscaling` -> `configure_scale_to_zero` -> `create_read_replica` |

**Usage in Claude Code:**
```
Use the lakebase_explore_database prompt to guide your exploration of my database.
```

**Usage in Python MCP client:**
```python
prompt = await session.get_prompt("lakebase_autoscaling_tuning")
print(prompt.messages[0].content.text)
```

---

## Autoscaling-Aware Design

This server is purpose-built for Lakebase Autoscaling compute:

### Scale-to-Zero Retry
When compute is suspended, the first connection attempt fails. The server retries with exponential backoff:
- Attempts: 5 (configurable via `LAKEBASE_S2Z_RETRY_ATTEMPTS`)
- Delays: 0.5s -> 1.0s -> 2.0s -> 4.0s -> 8.0s (capped at `LAKEBASE_S2Z_MAX_DELAY`)
- Catches: `OperationalError`, `ConnectionException`, `ConnectionRefusedError`, `OSError`

### Read Replica Routing
- `lakebase_read_query` calls `execute_readonly()` which prefers the replica pool
- `lakebase_execute_query` always uses the primary pool
- Automatic fallback to primary if replica is unavailable

### Connection Health
- Pre-checkout health checks (`AsyncConnectionPool.check_connection`)
- Max lifetime: 300s — stale connections recycled
- Max idle: 60s — idle connections evicted
- Reconnect timeout: 30s

### Autoscaling-Aware Error Messages
| Condition | Message |
|-----------|---------|
| Scale-to-zero wake-up | "Compute is waking up... Retries exhausted. Try again shortly." |
| Connection refused | "Cannot connect. Possible: suspended, restarting, autoscaling in progress." |
| Connection terminated | "Connection terminated during restart/scaling. Pool will reconnect." |
| Permission denied | "UC permissions don't allow this operation." |
| Table not found | "Use `lakebase_list_tables` to discover available tables." |
| Syntax error | "SQL syntax error — {details}." |
| Query timeout | "Try limiting rows with LIMIT or simplifying query." |

---

## Query Cost Attribution

Inspired by Snowflake's `QUERY_TAG` pattern, Lakebase MCP provides two layers of query attribution for cost tracking and observability:

### 1. Application-Level Tagging
All connections include `application_name=lakebase_mcp` in the connection string. This appears in:
- `pg_stat_activity.application_name` — identify MCP sessions in active queries
- PostgreSQL logs — filter MCP traffic in log analysis

### 2. Tool-Level SQL Comments
Each query is prefixed with a SQL comment identifying the originating tool:
```sql
/* lakebase_mcp:lakebase_read_query */ SELECT * FROM users LIMIT 10;
```
This appears in:
- `pg_stat_statements` — aggregate cost by tool
- Query logs — trace individual tool invocations

---

## Safety Controls

| Control | Details |
|---------|---------|
| **Write guard** | All write/DDL queries blocked unless `LAKEBASE_ALLOW_WRITE=true` (legacy) or governed by `LAKEBASE_SQL_PROFILE` |
| **SQL governance** | sqlglot-based AST parsing classifies all 17 SQL statement types with per-type allow/deny |
| **Tool access control** | Per-tool allow/deny lists with pre-built profiles (read_only, analyst, developer, admin) |
| **Read-only transactions** | `lakebase_read_query` wraps in `SET TRANSACTION READ ONLY` |
| **Dangerous function blocking** | `pg_terminate_backend`, `pg_cancel_backend`, `pg_reload_conf` are rejected at validation |
| **Production branch protection** | `lakebase_delete_branch` refuses to delete `production` or `main` |
| **Row limits** | Queries capped at `LAKEBASE_MAX_ROWS` (default: 1000) |
| **Query timeout** | `connect_timeout` enforced via `LAKEBASE_QUERY_TIMEOUT` (default: 30s) |
| **Credential redaction** | `get_connection_string` redacts passwords by default — returns `****` unless `show_password=true` is explicitly passed |
| **Input validation** | Pydantic models enforce bounds on all parameters (CU ranges, timeouts, sample sizes) |

---

## Fine-Grained Governance

The server provides **dual-layer governance** for controlling what AI agents can do — matching and exceeding Snowflake MCP's access control capabilities.

### Architecture

```
Request: lakebase_execute_query("DROP TABLE users")

Layer 1 — Tool Access Control
  Is "lakebase_execute_query" permitted? → check tool profile/allow/deny

Layer 2 — SQL Statement Governance
  Parse "DROP TABLE users" via sqlglot → SQLStatementType.DROP
  Is DROP in allowed types? → check SQL profile/allow/deny

Both layers must PASS for execution to proceed.
```

### SQL Statement Profiles

The server classifies SQL using **sqlglot AST parsing** (not regex) to accurately handle CTEs, subqueries, multi-statement SQL, and Postgres-specific syntax.

| Profile | Allowed Statement Types |
|---------|------------------------|
| `read_only` | SELECT, SHOW, DESCRIBE, EXPLAIN |
| `analyst` | read_only + INSERT, SET |
| `developer` | analyst + UPDATE, DELETE, CREATE, ALTER, CALL |
| `admin` | All 17 types (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, MERGE, TRUNCATE, GRANT, REVOKE, USE, SHOW, DESCRIBE, EXPLAIN, SET, CALL) |

### Tool Access Profiles

| Profile | Allowed Tool Categories |
|---------|------------------------|
| `read_only` | sql_query, schema_read, project_read, branch_read, compute_read, sync_read, synced_tables_read, endpoint_read, monitoring, quality, query_optimization, feature_read, insight |
| `analyst` | Same as read_only |
| `developer` | read_only + branch_write, compute_write, migration, sync_write, synced_tables_write, endpoint_write |
| `admin` | All 17 categories |

### Quick Start Examples

**Read-only agent** (most restrictive — ideal for coding assistants):
```bash
export LAKEBASE_SQL_PROFILE=read_only
export LAKEBASE_TOOL_PROFILE=read_only
export LAKEBASE_TOOL_DENIED=lakebase_execute_query  # force read_query only
```

**Analyst agent** (SELECT + INSERT for staging):
```bash
export LAKEBASE_SQL_PROFILE=analyst
export LAKEBASE_TOOL_PROFILE=analyst
```

**Developer agent** (full CRUD, no admin):
```bash
export LAKEBASE_SQL_PROFILE=developer
export LAKEBASE_TOOL_PROFILE=developer
```

**Legacy mode** (backward compatible — no governance env vars):
```bash
export LAKEBASE_ALLOW_WRITE=false  # same behavior as before
```

### YAML Configuration (Optional)

For complex policies, use a YAML file instead of env vars:

```bash
export LAKEBASE_GOVERNANCE_CONFIG=/path/to/governance.yaml
```

See [`governance.yaml.example`](governance.yaml.example) for the full reference.

### Governance Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `LAKEBASE_SQL_PROFILE` | `read_only`, `analyst`, `developer`, `admin` | *(empty = legacy)* | SQL permission profile |
| `LAKEBASE_TOOL_PROFILE` | `read_only`, `analyst`, `developer`, `admin` | *(empty = legacy)* | Tool access profile |
| `LAKEBASE_SQL_ALLOWED_TYPES` | comma-separated types | *(empty)* | Additional allowed SQL types |
| `LAKEBASE_SQL_DENIED_TYPES` | comma-separated types | *(empty)* | Denied SQL types (overrides profile) |
| `LAKEBASE_TOOL_ALLOWED_CATEGORIES` | comma-separated categories | *(empty)* | Additional allowed tool categories |
| `LAKEBASE_TOOL_DENIED_CATEGORIES` | comma-separated categories | *(empty)* | Denied tool categories |
| `LAKEBASE_TOOL_ALLOWED` | comma-separated tool names | *(empty)* | Individual tool allow list |
| `LAKEBASE_TOOL_DENIED` | comma-separated tool names | *(empty)* | Individual tool deny list |
| `LAKEBASE_GOVERNANCE_CONFIG` | file path | *(empty)* | Path to governance.yaml |

---

## Unity Catalog Integration

Lakebase MCP integrates with Unity Catalog governance at three levels:

### Level 1: Permission Introspection

Agents can query their own UC permissions before attempting operations:

```
> What can I access in the hls_amer_catalog?

Agent calls: lakebase_governance_summary(catalog="hls_amer_catalog")

Result:
  SQL Governance: read_only (SELECT, SHOW, DESCRIBE, EXPLAIN)
  Tool Access: all read-only tools
  UC Privileges: SELECT, USE_CATALOG, USE_SCHEMA
  Recommended profile: read_only or analyst
```

### Level 2: Federated Catalogs

Lakebase databases are registered as **foreign catalogs** in Unity Catalog:
- Schemas and tables appear in Catalog Explorer
- UC grants (SELECT, MODIFY, etc.) control metadata access
- Credential vending respects UC permissions
- Row filters and column masks can be applied

### Level 3: Three-Layer Access Control

```
Agent Request → MCP Tool Governance → SQL Statement Governance → UC Permission Check
                (tool_guard.py)        (sql_guard.py)             (PostgreSQL + UC grants)

Layer 1: Is the tool allowed?        (LAKEBASE_TOOL_PROFILE)
Layer 2: Is the SQL type allowed?    (LAKEBASE_SQL_PROFILE)
Layer 3: Does UC permit this object? (Unity Catalog grants)
```

All three layers must permit an operation for it to succeed.

---

## UI Dashboard

A full-featured React + FastAPI web app for exploring, configuring, and estimating costs for the Lakebase MCP Server. Deployed as a Databricks App.

### Pages (5)

| Page | Path | Description |
|------|------|-------------|
| **Home** | `/` | Stats overview (49 tools, 17 categories, 4 profiles, 4 prompts), quick links |
| **Tool Explorer** | `/tools` | Browse all 49 tools by category, search, filter, view parameters and annotations |
| **Connect** | `/connect` | Connection wizard with config snippets for Claude Desktop, Claude Code, Python, curl |
| **Governance** | `/governance` | Interactive access control matrices for SQL profiles and tool profiles |
| **Pricing Calculator** | `/pricing` | Token cost estimator, compute/storage calculators, competitive comparison |

### Pricing Calculator

The pricing page provides interactive cost estimation across three dimensions:

- **Token Cost Calculator** — Select Claude model (Opus/Sonnet/Haiku), adjust tool calls per session, see per-call and per-session costs. Includes model recommendation banners (e.g., "Switch to Sonnet for 40% savings")
- **Compute Cost Estimator** — Choose CU size (0.5-32), region, and usage pattern (always-on vs scale-to-zero). Calculates monthly DBU cost
- **Storage Cost Estimator** — Input database size and branches. Highlights that branches are free (copy-on-write)
- **Total Monthly Estimate** — Combined token + compute + storage with adjustable sessions/month
- **Competitive Comparison** — Side-by-side Lakebase vs Snowflake MCP vs Teradata MCP: compute costs, session costs, tool counts, governance layers, and key differentiators
- **Cost Optimization Tips** — Actionable recommendations (prompt caching, model selection, scale-to-zero, batch API)

### Build and Deploy

```bash
# Build frontend
python ui/build.py

# Deploy to Databricks Apps
python ui/deploy_to_databricks.py --app-name lakebase-mcp-ui

# Hard redeploy (delete and recreate)
python ui/deploy_to_databricks.py --app-name lakebase-mcp-ui --hard-redeploy
```

### UI Tests (44 tests)

```bash
cd ui/frontend
npx vitest run
```

| Test Suite | Tests | Coverage |
|-----------|-------|----------|
| App.test.jsx | 7 | Routing, navigation, all 5 pages |
| PricingCalculator.test.jsx | 10 | All 6 sections, model selector, optimization tips |
| ConnectionWizard.test.jsx | 7 | Config generation, copy buttons, tabs |
| ToolCard.test.jsx | 6 | Tool rendering, parameters, annotations |
| GovernanceMatrix.test.jsx | 5 | Profile matrices, SQL/tool governance |
| CategoryAccordion.test.jsx | 4 | Category grouping, expansion, tool counts |
| ProfileSelector.test.jsx | 5 | Profile switching, badge counts |

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Databricks workspace with Lakebase enabled
- Databricks CLI authenticated (`databricks auth login`)

### 1. Clone and Install

```bash
git clone https://github.com/suryasai87/lakebase-mcp.git
cd lakebase-mcp
uv sync
```

### 2. Configure Environment

Create a `.env` file or export these environment variables:

```bash
# Required — Lakebase connection
export LAKEBASE_HOST="ep-your-endpoint.database.us-east-1.cloud.databricks.com"
export LAKEBASE_DATABASE="databricks_postgres"

# Optional — Databricks workspace (for compute/project/branching tools)
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"

# Optional — Read replica
export LAKEBASE_REPLICA_HOST=""

# Optional — Safety (defaults shown)
export LAKEBASE_ALLOW_WRITE="false"
export LAKEBASE_MAX_ROWS="1000"
export LAKEBASE_QUERY_TIMEOUT="30"

# Optional — Scale-to-zero retry (defaults shown)
export LAKEBASE_S2Z_RETRY_ATTEMPTS="5"
export LAKEBASE_S2Z_RETRY_DELAY="0.5"

# Optional — Pool lifecycle (defaults shown)
export LAKEBASE_POOL_MAX_LIFETIME="300"
export LAKEBASE_POOL_MAX_IDLE="60"
```

### 3. Run Locally

```bash
# Default: Streamable HTTP (production, stateless, horizontal scaling)
uv run lakebase-mcp

# Alternative: stdio transport (for Claude Desktop direct integration)
uv run lakebase-mcp --transport stdio
```

The server starts on `http://localhost:8000/mcp` using Streamable HTTP transport by default.

### 4. Connect an AI Agent

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "lakebase": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

#### Claude Code (`.claude/mcp.json`)

```json
{
  "mcpServers": {
    "lakebase": {
      "type": "streamable_http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

#### Any MCP Client (Python)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # List all 49 tools
        tools = await session.list_tools()

        # Run a query
        result = await session.call_tool(
            "lakebase_read_query",
            arguments={"sql": "SELECT current_database(), version()"}
        )
        print(result.content[0].text)
```

---

## Deploy to Databricks

### Option A: Databricks Apps (Recommended)

1. **Create the app**

```bash
databricks apps create lakebase-mcp-server --profile DEFAULT
```

2. **Set secrets** for the Lakebase connection

```bash
databricks apps set-secret lakebase-mcp-server LAKEBASE_HOST \
  "ep-your-endpoint.database.us-east-1.cloud.databricks.com" --profile DEFAULT

databricks apps set-secret lakebase-mcp-server LAKEBASE_DATABASE \
  "databricks_postgres" --profile DEFAULT
```

3. **Sync and deploy**

```bash
DATABRICKS_USERNAME=$(databricks current-user me --profile DEFAULT | jq -r .userName)

databricks sync . "/Users/$DATABRICKS_USERNAME/lakebase-mcp-server" --profile DEFAULT

databricks apps deploy lakebase-mcp-server \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/lakebase-mcp-server" \
  --profile DEFAULT
```

4. **Access the MCP endpoint**

```
https://lakebase-mcp-server-<workspace-id>.aws.databricksapps.com/mcp
```

### Option B: Unity Catalog MCP Catalog Registration

After deploying, register the server in the UC MCP Catalog so all workspace users can discover it:

```bash
uv run python deploy/register_mcp_catalog.py
```

Edit `deploy/register_mcp_catalog.py` to set your actual app URL before running.

---

## Architecture

```
lakebase-mcp/
├── server/
│   ├── main.py              # FastMCP server, lifespan, tool registration, governance wiring
│   ├── config.py            # Environment-based configuration (19 vars)
│   ├── db.py                # Async connection pool (S2Z retry + replica routing + query tagging)
│   ├── auth.py              # Databricks SDK auth (OBO + standard) + UC permissions
│   ├── governance/
│   │   ├── sql_guard.py     # sqlglot-based SQL statement classification (17 types)
│   │   ├── tool_guard.py    # Per-tool access control (17 categories, 4 profiles)
│   │   └── policy.py        # Unified policy engine (env vars + YAML)
│   ├── tools/
│   │   ├── query.py         # 3 tools: read, execute, explain
│   │   ├── schema.py        # 4 tools: schemas, tables, describe, tree
│   │   ├── instance.py      # 7 tools: projects, describe, connection string, create/delete project, credentials
│   │   ├── branching.py     # 3 tools: create, list, delete branches
│   │   ├── compute.py       # 6 tools: autoscaling, S2Z, metrics, replicas
│   │   ├── migration.py     # 2 tools: prepare, complete
│   │   ├── sync.py          # 2 tools: create sync, list syncs
│   │   ├── synced_tables.py # 4 tools: list, create, delete, status for synced tables
│   │   ├── endpoints.py    # 4 tools: list, create, update, delete endpoints
│   │   ├── monitoring.py   # 3 tools: replication status, WAL stats, CDC monitor
│   │   ├── quality.py       # 1 tool: profile table
│   │   ├── query_optimization.py # 3 tools: slow queries, index usage, table scan stats
│   │   ├── feature_store.py # 2 tools: lookup, list feature tables
│   │   └── uc_governance.py # 4 tools: UC permissions, access check, governance summary, catalog grants
│   ├── resources/
│   │   └── insights.py      # memo://insights resource + append tool
│   ├── prompts/
│   │   └── templates.py     # 4 prompt templates
│   └── utils/
│       ├── errors.py        # Autoscaling-aware error handling
│       ├── formatting.py    # Markdown/JSON response formatting
│       └── pagination.py    # Cursor-based pagination
├── ui/
│   ├── backend/
│   │   ├── app.py           # FastAPI app serving React SPA + API
│   │   └── routers/
│   │       └── metadata.py  # 12 API endpoints (tools, governance, pricing)
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── App.jsx      # Router with 5 animated pages
│   │   │   ├── components/
│   │   │   │   └── Layout.jsx  # Sidebar navigation, app bar
│   │   │   ├── pages/
│   │   │   │   ├── Home.jsx              # Dashboard with stats and quick links
│   │   │   │   ├── ToolExplorer.jsx      # Tool browser with search and filters
│   │   │   │   ├── ConnectionWizard.jsx  # MCP client connection setup
│   │   │   │   ├── GovernanceDashboard.jsx # Access control matrices
│   │   │   │   └── PricingCalculator.jsx # Cost estimators and comparison
│   │   │   └── hooks/
│   │   │       └── useApi.js  # Shared fetch hook
│   │   └── __tests__/       # 44 Vitest tests (7 suites)
│   ├── build.py             # Frontend build script
│   ├── deploy_to_databricks.py  # Staging-based deployment
│   └── app.yaml             # Databricks App config for UI
├── tests/
│   ├── test_unit/           # 39+ unit tests (no connection needed)
│   ├── test_integration/    # Live connection tests
│   └── test_e2e/            # Full MCP protocol tests
├── deploy/
│   └── register_mcp_catalog.py  # Unity Catalog registration
├── eval/
│   └── evaluation.xml       # 10 evaluation Q&A pairs
├── app.yaml                 # Databricks App configuration (MCP server)
├── pyproject.toml           # Project metadata (v0.2.0)
├── requirements.txt         # Pip-compatible requirements (includes sqlglot for SQL governance)
└── TESTING_SCENARIOS.md     # Comprehensive test scenarios for all 49 tools
```

---

## Running Tests

```bash
# Unit tests (no Lakebase connection needed)
uv run pytest tests/test_unit/ -v

# Integration tests (requires LAKEBASE_LIVE_TEST=true + connection)
LAKEBASE_LIVE_TEST=true uv run pytest tests/test_integration/ -v

# E2E tests (requires running MCP server)
LAKEBASE_E2E_TEST=true MCP_SERVER_URL=http://localhost:8000/mcp \
  uv run pytest tests/test_e2e/ -v
```

---

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LAKEBASE_HOST` | *(required)* | Lakebase endpoint hostname |
| `LAKEBASE_DATABASE` | *(required)* | Database name |
| `LAKEBASE_PORT` | `5432` | PostgreSQL port |
| `DATABRICKS_HOST` | *(optional)* | Workspace URL (for compute/project/branching tools) |
| `LAKEBASE_REPLICA_HOST` | *(empty)* | Read replica hostname |
| `LAKEBASE_REPLICA_PORT` | `5432` | Read replica port |
| `LAKEBASE_PG_USER` | *(from .pgpass)* | Explicit PostgreSQL username |
| `LAKEBASE_PG_PASSWORD` | *(from .pgpass)* | Explicit PostgreSQL password |
| `LAKEBASE_ALLOW_WRITE` | `false` | Allow write/DDL queries |
| `LAKEBASE_MAX_ROWS` | `1000` | Max rows per query result |
| `LAKEBASE_QUERY_TIMEOUT` | `30` | Query timeout / connect timeout (seconds) |
| `LAKEBASE_S2Z_RETRY_ATTEMPTS` | `5` | Scale-to-zero connection retries |
| `LAKEBASE_S2Z_RETRY_DELAY` | `0.5` | Base retry delay (seconds, doubles each attempt) |
| `LAKEBASE_S2Z_MAX_DELAY` | `10.0` | Max retry delay cap (seconds) |
| `LAKEBASE_POOL_MIN` | `2` | Minimum pool connections |
| `LAKEBASE_POOL_MAX` | `10` | Maximum pool connections |
| `LAKEBASE_POOL_MAX_LIFETIME` | `300` | Max connection age (seconds) |
| `LAKEBASE_POOL_MAX_IDLE` | `60` | Max idle time before eviction (seconds) |

---

## Example Conversations

### Explore a Database

> **You**: What tables are in my Lakebase database? Show me the biggest one.
>
> **Agent**: *Calls `lakebase_list_schemas` -> `lakebase_list_tables` -> `lakebase_describe_table`*
>
> Your database has 3 schemas (public, analytics, staging) with 24 tables total. The largest is `public.transactions` with ~2.4M rows...

### Tune Autoscaling

> **You**: My dev database is costing too much. Can you enable scale-to-zero?
>
> **Agent**: *Calls `lakebase_get_compute_status` -> `lakebase_get_compute_metrics` -> `lakebase_configure_scale_to_zero`*
>
> Done. Your dev branch now suspends after 60s of inactivity and wakes in ~200ms on the next query. Based on your metrics, the compute was idle 78% of the time — this should significantly reduce costs.

### Safe Schema Migration

> **You**: Add a `last_login` column to the users table, but test it first.
>
> **Agent**: *Calls `lakebase_prepare_migration` -> `lakebase_describe_table` (on branch) -> `lakebase_complete_migration(apply=true)`*
>
> Migration applied. The `last_login` timestamp column is now on the production `users` table. I tested it on a branch first to verify no existing queries were broken.

### Set Up Feature Serving

> **You**: Sync the customer_features table from Delta Lake to Lakebase for real-time serving.
>
> **Agent**: *Calls `lakebase_create_sync` with direction=delta_to_lakebase, frequency=continuous*
>
> Continuous sync pipeline created. The `analytics.ml.customer_features` Delta table will stream changes to Lakebase. Use `lakebase_lookup_features` for sub-millisecond lookups.

### Profile Data Quality

> **You**: Check the data quality of the orders table.
>
> **Agent**: *Calls `lakebase_profile_table` with table_name="public.orders"*
>
> | Column | Type | Nulls% | Distinct | Min | Max | Avg |
> |--------|------|--------|----------|-----|-----|-----|
> | order_id | integer | 0% | 50000 | 1 | 50000 | 25000.5 |
> | amount | numeric | 2.3% | 4521 | 0.99 | 9999.99 | 142.87 |
> | status | text | 0% | 5 | | | |

---

## Authentication

The server supports multiple authentication modes:

| Mode | When | How |
|------|------|-----|
| **On-Behalf-Of (OBO)** | Deployed as Databricks App | `ModelServingUserCredentials()` — inherits user identity |
| **Standard SDK** | Local development, CLI | `WorkspaceClient()` — uses `~/.databrickscfg` or env vars |
| **`.pgpass` file** | Local dev with OAuth rotation | Standard PostgreSQL `.pgpass` for connection credentials |
| **Explicit credentials** | CI/CD, service accounts | `LAKEBASE_PG_USER` + `LAKEBASE_PG_PASSWORD` env vars |

Unity Catalog permissions are enforced at the database layer — the server does not bypass access controls.

---

## Known Limitations & Roadmap

The following gaps were identified comparing the MCP implementation against the latest Databricks Lakebase APIs (April 2026):

| # | Severity | Gap | Status |
|---|----------|-----|--------|
| GAP-1 | MEDIUM | CU spread validation uses 8 CU max — Databricks docs indicate 16 CU max spread | **Fixed in v0.3.0** — max spread updated to 16 CU |
| GAP-2 | LOW | Autoscaling min/max CU not validated against tier-specific constraints | **Fixed in v0.3.0** — tier-aware validation added |
| GAP-3 | HIGH | Migration tools are partial stubs — `prepare_migration` creates branch but doesn't execute DDL; `complete_migration(apply=true)` returns success without replaying DDL on production | **Fixed in v0.3.0** — migrations now execute DDL on branch and replay on production |
| GAP-4 | HIGH | No Synced Tables API support (Delta to Lakebase reverse sync via `/api/2.0/lakebase/projects/{name}/synced_tables`) | **Fixed in v0.3.0** — 4 synced tables tools added |
| GAP-5 | MEDIUM | No endpoint management tools (create/update/delete endpoints via REST API) | **Fixed in v0.3.0** — 4 endpoint management tools added |
| GAP-6 | MEDIUM | No credential/connection-string management via Lakebase REST API | **Fixed in v0.3.0** — `rotate_credentials` and `list_credentials` tools added |
| GAP-7 | LOW | Missing `pg_stat_replication` and `pg_stat_wal` monitoring queries | **Fixed in v0.3.0** — `replication_status` and `wal_statistics` tools added |
| GAP-8 | MEDIUM | SQL/tool governance only wired to query tools — branch, compute, and sync tools bypass governance checks | **Fixed in v0.3.0** — governance enforced on all tool categories |
| GAP-9 | HIGH | `get_connection_string` returns credentials in plaintext response — should redact or use short-lived tokens | **Fixed in v0.3.0** — passwords redacted by default, `show_password=true` opt-in |
| GAP-10 | LOW | No WAL-based CDC (`wal2delta`) monitoring integration | **Fixed in v0.3.0** — `cdc_monitor` tool added |
| GAP-11 | LOW | No project-level CRUD (create/delete projects via API) | **Fixed in v0.3.0** — `create_project` and `delete_project` tools added |
| GAP-12 | LOW | No Lakehouse Sync status polling via REST API | **Fixed in v0.3.0** — `get_synced_table_status` tool provides sync status polling |

Full gap analysis with recommendations: [Confluence — Lakebase MCP Server](https://databricks.atlassian.net/wiki/spaces/FE/pages/6179390187)

---

## License

Apache 2.0
