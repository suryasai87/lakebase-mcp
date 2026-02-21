# Lakebase MCP Server

A production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for **Databricks Lakebase** — the managed PostgreSQL service on Databricks with autoscaling, branching, and Unity Catalog governance.

This server gives AI agents (Claude, GPT, Copilot, etc.) full control over Lakebase databases: querying, schema exploration, compute management, branching, migrations, Delta sync, data quality profiling, and feature serving — all through a standard MCP interface.

---

## Features

| Category | Tools | What They Do |
|----------|-------|--------------|
| **Query** | 3 | Execute read/write SQL, explain query plans |
| **Schema** | 4 | List schemas/tables, describe columns/indexes, browse object tree |
| **Project** | 3 | List projects, describe project details, get connection strings |
| **Branching** | 3 | Create/list/delete branches for dev/test isolation |
| **Compute** | 6 | Autoscaling, scale-to-zero, metrics, restart, read replicas |
| **Migration** | 2 | Branch-based safe schema migrations (prepare + apply/discard) |
| **Sync** | 2 | Delta Lake <-> Lakebase data synchronization |
| **Quality** | 1 | Per-column data profiling (nulls, cardinality, min/max) |
| **Feature Store** | 2 | Low-latency feature lookup, list feature tables |
| **Insights** | 1 | Append observations to a session memo |
| **Total** | **27 tools** | + 4 prompt templates + 1 resource |

### Autoscaling-Aware Design

This server is built specifically for Lakebase Autoscaling:

- **Scale-to-zero retry**: Exponential backoff when compute is waking from suspension (~hundreds of ms)
- **Read replica routing**: Read-only queries automatically route to the replica pool
- **Compute management**: 6 tools to monitor, configure, and optimize autoscaling
- **Connection health**: Pool pre-checks, max lifetime rotation, idle connection cleanup
- **Autoscaling-aware errors**: Distinguishes compute wake-up from actual failures

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

# Optional — Databricks workspace (for compute management tools)
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"

# Optional — Read replica
export LAKEBASE_REPLICA_HOST=""

# Optional — Safety (defaults shown)
export LAKEBASE_ALLOW_WRITE="false"      # Set to "true" to enable write queries
export LAKEBASE_MAX_ROWS="1000"          # Max rows returned per query
export LAKEBASE_QUERY_TIMEOUT="30"       # Query timeout in seconds

# Optional — Scale-to-zero retry (defaults shown)
export LAKEBASE_S2Z_RETRY_ATTEMPTS="5"   # Retries when compute is waking
export LAKEBASE_S2Z_RETRY_DELAY="0.5"    # Base delay in seconds (doubles each retry)

# Optional — Pool lifecycle (defaults shown)
export LAKEBASE_POOL_MAX_LIFETIME="300"  # Max connection age in seconds
export LAKEBASE_POOL_MAX_IDLE="60"       # Max idle time before eviction
```

### 3. Run Locally

```bash
uv run lakebase-mcp
```

The server starts on `http://localhost:8000/mcp` using Streamable HTTP transport.

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

        # List all 27 tools
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
# Set required secrets
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

## Tool Reference

### Query Tools

| Tool | Description | Read-Only |
|------|-------------|-----------|
| `lakebase_read_query` | Execute a read-only SQL query (routed to replica if available) | Yes |
| `lakebase_execute_query` | Execute a read/write SQL query (requires `LAKEBASE_ALLOW_WRITE=true`) | No |
| `lakebase_explain_query` | Show the execution plan for a SQL query with optional `ANALYZE` | Yes |

### Schema Tools

| Tool | Description |
|------|-------------|
| `lakebase_list_schemas` | List all user-created schemas (excludes pg_catalog, information_schema) |
| `lakebase_list_tables` | List tables in a schema with row estimates and sizes |
| `lakebase_describe_table` | Full table schema: columns, types, nullability, indexes, constraints |
| `lakebase_object_tree` | Hierarchical view: schemas -> tables -> columns |

### Project Tools

| Tool | Description |
|------|-------------|
| `lakebase_list_projects` | List all Lakebase projects in the workspace |
| `lakebase_describe_project` | Project details: branches, compute, quotas |
| `lakebase_get_connection_string` | Get the PostgreSQL connection string for a branch |

### Branching Tools

| Tool | Description |
|------|-------------|
| `lakebase_create_branch` | Create a branch from production (copy-on-write, instant) |
| `lakebase_list_branches` | List all branches for a project |
| `lakebase_delete_branch` | Delete a branch (cannot delete production) |

### Compute Tools (Autoscaling)

| Tool | Description |
|------|-------------|
| `lakebase_get_compute_status` | Current state (active/suspended/scaling), CU allocation, connections |
| `lakebase_configure_autoscaling` | Set min/max CU range (max spread: 8 CU). Each CU = 2 GB RAM |
| `lakebase_configure_scale_to_zero` | Enable/disable auto-suspend with inactivity timeout (60-3600s) |
| `lakebase_get_compute_metrics` | CPU, memory, working set, connections over time |
| `lakebase_restart_compute` | Restart compute (interrupts connections) |
| `lakebase_create_read_replica` | Create a read replica with independent autoscaling |

### Migration Tools

| Tool | Description |
|------|-------------|
| `lakebase_prepare_migration` | Create a migration branch and apply DDL for testing |
| `lakebase_complete_migration` | Apply migration to production (`apply=true`) or discard (`apply=false`) |

### Sync Tools

| Tool | Description |
|------|-------------|
| `lakebase_create_sync` | Set up Delta <-> Lakebase sync (snapshot, triggered, or continuous) |
| `lakebase_list_syncs` | List all active sync pipelines for a project |

### Quality & Feature Store Tools

| Tool | Description |
|------|-------------|
| `lakebase_profile_table` | Per-column statistics: null%, cardinality, min/max, type distribution |
| `lakebase_lookup_features` | Low-latency feature lookup by entity keys |
| `lakebase_list_feature_tables` | List all feature-serving tables |

### Insights Resource

| Resource | Description |
|----------|-------------|
| `memo://insights` | Session-scoped notepad. Use `lakebase_append_insight` to record observations |

---

## Prompt Templates

The server includes 4 reusable prompt templates that guide agents through common workflows:

| Prompt | Use Case |
|--------|----------|
| `lakebase_explore_database` | Step-by-step database exploration (schemas -> tables -> profiling) |
| `lakebase_safe_migration` | Branch-based migration workflow (prepare -> test -> apply/discard) |
| `lakebase_setup_sync` | Set up Delta <-> Lakebase synchronization |
| `lakebase_autoscaling_tuning` | Monitor metrics and tune autoscaling/scale-to-zero settings |

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

## Architecture

```
lakebase-mcp/
├── server/
│   ├── main.py              # FastMCP server, lifespan, tool registration
│   ├── config.py             # Environment-based configuration
│   ├── db.py                 # Async connection pool (S2Z retry + replica routing)
│   ├── auth.py               # Databricks SDK authentication
│   ├── tools/
│   │   ├── query.py          # 3 tools: read, execute, explain
│   │   ├── schema.py         # 4 tools: schemas, tables, describe, tree
│   │   ├── instance.py       # 3 tools: projects, describe, connection string
│   │   ├── branching.py      # 3 tools: create, list, delete branches
│   │   ├── compute.py        # 6 tools: autoscaling, S2Z, metrics, replicas
│   │   ├── migration.py      # 2 tools: prepare, complete
│   │   ├── sync.py           # 2 tools: create sync, list syncs
│   │   ├── quality.py        # 1 tool: profile table
│   │   └── feature_store.py  # 2 tools: lookup, list feature tables
│   ├── resources/
│   │   └── insights.py       # memo://insights resource + append tool
│   ├── prompts/
│   │   └── templates.py      # 4 prompt templates
│   └── utils/
│       ├── errors.py         # Autoscaling-aware error handling
│       ├── formatting.py     # Markdown/JSON response formatting
│       └── pagination.py     # Cursor-based pagination
├── tests/
│   ├── test_unit/            # 39 unit tests (all passing)
│   ├── test_integration/     # Live connection tests
│   └── test_e2e/             # Full MCP protocol tests
├── deploy/
│   ├── deploy.sh             # Databricks Apps deployment script
│   └── register_mcp_catalog.py  # Unity Catalog registration
├── eval/
│   └── evaluation.xml        # 10 evaluation Q&A pairs
├── app.yaml                  # Databricks App configuration
├── pyproject.toml            # Project metadata and dependencies
└── requirements.txt          # Pip-compatible requirements
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

---

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LAKEBASE_HOST` | *(required)* | Lakebase endpoint hostname |
| `LAKEBASE_DATABASE` | *(required)* | Database name |
| `LAKEBASE_PORT` | `5432` | PostgreSQL port |
| `DATABRICKS_HOST` | *(optional)* | Workspace URL (for compute tools) |
| `LAKEBASE_REPLICA_HOST` | *(empty)* | Read replica hostname |
| `LAKEBASE_REPLICA_PORT` | `5432` | Read replica port |
| `LAKEBASE_ALLOW_WRITE` | `false` | Allow write/DDL queries |
| `LAKEBASE_MAX_ROWS` | `1000` | Max rows per query result |
| `LAKEBASE_QUERY_TIMEOUT` | `30` | Query timeout (seconds) |
| `LAKEBASE_S2Z_RETRY_ATTEMPTS` | `5` | Scale-to-zero connection retries |
| `LAKEBASE_S2Z_RETRY_DELAY` | `0.5` | Base retry delay (seconds, doubles each attempt) |
| `LAKEBASE_S2Z_MAX_DELAY` | `10.0` | Max retry delay cap (seconds) |
| `LAKEBASE_POOL_MIN` | `2` | Minimum pool connections |
| `LAKEBASE_POOL_MAX` | `10` | Maximum pool connections |
| `LAKEBASE_POOL_MAX_LIFETIME` | `300` | Max connection age (seconds) |
| `LAKEBASE_POOL_MAX_IDLE` | `60` | Max idle time before eviction (seconds) |

---

## License

Apache 2.0
