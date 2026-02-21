# Lakebase MCP Server — Testing Scenarios

Comprehensive testing guide covering all **31 tools**, **4 prompt templates**, **1 resource**, governance, UC permissions, error handling, connection pool behavior, and end-to-end workflows.

---

## Prerequisites

### Environment Setup

```bash
# Clone and install
git clone https://github.com/suryasai87/lakebase-mcp.git
cd lakebase-mcp
uv sync

# Configure environment
export LAKEBASE_HOST="ep-your-endpoint.database.us-east-1.cloud.databricks.com"
export LAKEBASE_DATABASE="databricks_postgres"
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export LAKEBASE_ALLOW_WRITE="true"   # Required for write tool tests
```

### Start the Server

```bash
uv run lakebase-mcp
# Server starts at http://localhost:8000/mcp
```

### Test Client (Python)

All scenarios below can be executed with this client pattern:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://localhost:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("tool_name", arguments={...})
        print(result.content[0].text)
```

Or via **Claude Desktop / Claude Code** with the MCP server configured.

---

## Test Matrix Summary

| # | Category | Tool / Capability | Test Type | Priority |
|---|----------|-------------------|-----------|----------|
| 1 | Query | `lakebase_read_query` | Functional | P0 |
| 2 | Query | `lakebase_execute_query` | Functional | P0 |
| 3 | Query | `lakebase_explain_query` | Functional | P0 |
| 4 | Schema | `lakebase_list_schemas` | Functional | P0 |
| 5 | Schema | `lakebase_list_tables` | Functional | P0 |
| 6 | Schema | `lakebase_describe_table` | Functional | P0 |
| 7 | Schema | `lakebase_object_tree` | Functional | P1 |
| 8 | Project | `lakebase_list_projects` | Functional | P0 |
| 9 | Project | `lakebase_describe_project` | Functional | P1 |
| 10 | Project | `lakebase_get_connection_string` | Functional | P1 |
| 11 | Branching | `lakebase_create_branch` | Functional | P0 |
| 12 | Branching | `lakebase_list_branches` | Functional | P0 |
| 13 | Branching | `lakebase_delete_branch` | Functional | P0 |
| 14 | Compute | `lakebase_get_compute_status` | Functional | P0 |
| 15 | Compute | `lakebase_configure_autoscaling` | Functional | P1 |
| 16 | Compute | `lakebase_configure_scale_to_zero` | Functional | P1 |
| 17 | Compute | `lakebase_get_compute_metrics` | Functional | P1 |
| 18 | Compute | `lakebase_restart_compute` | Functional | P2 |
| 19 | Compute | `lakebase_create_read_replica` | Functional | P2 |
| 20 | Migration | `lakebase_prepare_migration` | Functional | P1 |
| 21 | Migration | `lakebase_complete_migration` | Functional | P1 |
| 22 | Sync | `lakebase_create_sync` | Functional | P1 |
| 23 | Sync | `lakebase_list_syncs` | Functional | P1 |
| 24 | Quality | `lakebase_profile_table` | Functional | P0 |
| 25 | Feature Store | `lakebase_lookup_features` | Functional | P1 |
| 26 | Feature Store | `lakebase_list_feature_tables` | Functional | P1 |
| 27 | Insights | `lakebase_append_insight` | Functional | P1 |
| 28 | Resource | `memo://insights` | Functional | P1 |
| 29 | Prompts | 4 prompt templates | Functional | P2 |
| 30 | Pool | Scale-to-zero retry | Resilience | P0 |
| 31 | Pool | Read replica routing | Resilience | P1 |
| 32 | Safety | Write guard | Security | P0 |
| 33 | Safety | Dangerous function blocking | Security | P0 |
| 34 | Safety | Production branch protection | Security | P0 |
| 35 | Errors | Autoscaling-aware messages | UX | P1 |
| 36 | E2E | Explore workflow | Integration | P0 |
| 37 | E2E | Migration workflow | Integration | P1 |
| 38 | E2E | Autoscaling tuning workflow | Integration | P1 |

---

## Scenario 1: Query Tools (3 tools)

### 1.1 — `lakebase_read_query` — Basic SELECT

**Purpose**: Verify read-only query execution with replica routing.

**Steps**:
1. Call `lakebase_read_query` with `sql: "SELECT current_database(), version()"`
2. Call `lakebase_read_query` with `sql: "SELECT 1 AS test_col, 'hello' AS greeting"`

**Expected**:
- Returns markdown table with results
- No errors
- If replica is configured, query routes to replica (check server logs for `prefer_replica=True`)

**Variations**:
- `max_rows: 5` — verify row limit is respected
- `response_format: "json"` — verify JSON output includes `row_count` and `rows` keys

### 1.2 — `lakebase_read_query` — Write Rejection

**Purpose**: Verify read_query blocks write statements.

**Steps**:
1. Call `lakebase_read_query` with `sql: "INSERT INTO test VALUES (1)"`
2. Call `lakebase_read_query` with `sql: "DROP TABLE test"`
3. Call `lakebase_read_query` with `sql: "UPDATE test SET col = 1"`

**Expected**:
- Each returns error: "Only SELECT queries are allowed with read_query. Use lakebase_execute_query for writes."

### 1.3 — `lakebase_execute_query` — Write Operations

**Purpose**: Verify read-write query execution with write guard.

**Precondition**: `LAKEBASE_ALLOW_WRITE=true`

**Steps**:
1. Call `lakebase_execute_query` with `sql: "CREATE TABLE IF NOT EXISTS mcp_test (id serial PRIMARY KEY, name text, created_at timestamp DEFAULT now())"`
2. Call `lakebase_execute_query` with `sql: "INSERT INTO mcp_test (name) VALUES ('test_row_1') RETURNING *"`
3. Call `lakebase_read_query` with `sql: "SELECT * FROM mcp_test"`
4. Call `lakebase_execute_query` with `sql: "DROP TABLE mcp_test"`

**Expected**:
- Step 1: Table created successfully
- Step 2: Returns inserted row with generated id
- Step 3: Returns the inserted data
- Step 4: Table dropped

### 1.4 — `lakebase_execute_query` — Write Guard (Disabled)

**Purpose**: Verify writes are blocked when `LAKEBASE_ALLOW_WRITE=false`.

**Precondition**: Restart server with `LAKEBASE_ALLOW_WRITE=false`

**Steps**:
1. Call `lakebase_execute_query` with `sql: "CREATE TABLE guard_test (id int)"`

**Expected**:
- Returns: "Error: Write operations are disabled. Set LAKEBASE_ALLOW_WRITE=true to enable INSERT, UPDATE, DELETE, DDL."

### 1.5 — `lakebase_execute_query` — Dangerous Function Blocking

**Purpose**: Verify blocked PostgreSQL admin functions.

**Steps**:
1. Call `lakebase_execute_query` with `sql: "SELECT pg_terminate_backend(123)"`
2. Call `lakebase_execute_query` with `sql: "SELECT pg_cancel_backend(456)"`
3. Call `lakebase_execute_query` with `sql: "SELECT pg_reload_conf()"`

**Expected**:
- Each raises validation error: "Query contains blocked function: pg_terminate_backend" (etc.)

### 1.6 — `lakebase_explain_query` — Execution Plan

**Purpose**: Verify EXPLAIN output for query optimization.

**Steps**:
1. Call `lakebase_explain_query` with `sql: "SELECT 1"`, `analyze: false`
2. Call `lakebase_explain_query` with `sql: "SELECT 1"`, `analyze: true`

**Expected**:
- Step 1: Returns JSON execution plan (EXPLAIN FORMAT JSON, VERBOSE)
- Step 2: Returns plan with actual timing data (EXPLAIN ANALYZE, BUFFERS)

---

## Scenario 2: Schema Discovery Tools (4 tools)

### 2.1 — `lakebase_list_schemas`

**Purpose**: Verify schema enumeration with system schema filtering.

**Steps**:
1. Call `lakebase_list_schemas` with default params
2. Call `lakebase_list_schemas` with `response_format: "json"`

**Expected**:
- Returns list of user schemas (e.g., `public`)
- Does NOT include `pg_catalog`, `information_schema`, `pg_toast`
- Each schema shows `schema_name` and `schema_owner`

### 2.2 — `lakebase_list_tables`

**Purpose**: Verify table listing with metadata.

**Steps**:
1. Call `lakebase_list_tables` with `schema_name: "public"`
2. Call `lakebase_list_tables` with a non-existent schema: `schema_name: "nonexistent"`

**Expected**:
- Step 1: Returns tables with `table_name`, `table_type`, `estimated_rows`, `total_size`
- Step 2: Returns empty list or "No tables found."

### 2.3 — `lakebase_describe_table`

**Purpose**: Verify full table schema inspection.

**Precondition**: At least one table exists in the database.

**Steps**:
1. Call `lakebase_describe_table` with `table_name: "public.your_table"`
2. Call `lakebase_describe_table` with `table_name: "your_table"` (no schema prefix — should default to `public`)
3. Call `lakebase_describe_table` with `response_format: "json"`

**Expected**:
- Returns columns: `column_name`, `data_type`, `is_nullable`, `column_default`, length/precision info
- Returns indexes: `indexname`, `indexdef`
- Schema prefix defaults to `public` when omitted

### 2.4 — `lakebase_object_tree`

**Purpose**: Verify hierarchical object tree generation.

**Steps**:
1. Call `lakebase_object_tree` with no params (all schemas)
2. Call `lakebase_object_tree` with `schema_name: "public"` (single schema)

**Expected**:
- Returns JSON object: `{ "schema_name": [{ "name": "table", "type": "TABLE", "columns": [...] }] }`
- Includes TABLE, VIEW, and MATERIALIZED VIEW types
- Excludes system schemas when no filter provided

---

## Scenario 3: Project Management Tools (3 tools)

### 3.1 — `lakebase_list_projects`

**Purpose**: Verify Lakebase project enumeration via Databricks API.

**Precondition**: `DATABRICKS_HOST` configured, authenticated workspace.

**Steps**:
1. Call `lakebase_list_projects` with no params
2. Call `lakebase_list_projects` with `catalog: "your_catalog"`

**Expected**:
- Returns JSON array of projects with name, state, catalog, region, branches

### 3.2 — `lakebase_describe_project`

**Purpose**: Verify detailed project metadata retrieval.

**Steps**:
1. Call `lakebase_describe_project` with `project_name: "your-project"`

**Expected**:
- Returns JSON with project config, branches, compute sizes, storage usage, sync pipelines

### 3.3 — `lakebase_get_connection_string`

**Purpose**: Verify connection string generation with credential vending.

**Steps**:
1. Call `lakebase_get_connection_string` with `project_name: "your-project"`, `branch_name: "production"`, `compute_type: "primary"`
2. Call with `compute_type: "replica"`

**Expected**:
- Returns JSON with `connection_string`, `host`, `port`, `database`, `user`, `branch`, `compute_type`
- Credentials are temporary (short-lived tokens)
- Note about Unity Catalog scoping included

---

## Scenario 4: Branching Tools (3 tools)

### 4.1 — `lakebase_create_branch` — Create Branch

**Purpose**: Verify copy-on-write branch creation.

**Steps**:
1. Call `lakebase_create_branch` with `project_name: "your-project"`, `branch_name: "test-branch-001"`
2. Call `lakebase_list_branches` to verify the branch exists

**Expected**:
- Returns JSON: `{ "status": "created", "branch": "test-branch-001", "parent": "production" }`
- Branch appears in list_branches output

### 4.2 — `lakebase_list_branches`

**Purpose**: Verify branch enumeration.

**Steps**:
1. Call `lakebase_list_branches` with `project_name: "your-project"`

**Expected**:
- Returns JSON array with branch details (name, creation time, parent, compute status, CU allocation)
- Always includes `production` branch

### 4.3 — `lakebase_delete_branch` — Normal and Protected

**Purpose**: Verify branch deletion with production protection.

**Steps**:
1. Call `lakebase_delete_branch` with `project_name: "your-project"`, `branch_name: "test-branch-001"`
2. Call `lakebase_delete_branch` with `branch_name: "production"`
3. Call `lakebase_delete_branch` with `branch_name: "main"`

**Expected**:
- Step 1: Returns "Branch 'test-branch-001' deleted from project '...'"
- Step 2: Returns "Error: Cannot delete the production/main branch."
- Step 3: Returns same protection error

---

## Scenario 5: Compute Management Tools (6 tools)

### 5.1 — `lakebase_get_compute_status`

**Purpose**: Verify compute state inspection.

**Steps**:
1. Call `lakebase_get_compute_status` with `project_name: "your-project"`, `branch_name: "production"`

**Expected**:
- Returns JSON with state (`active`/`suspended`/`scaling_up`/`scaling_down`), CU allocation, autoscaling range, connections count

### 5.2 — `lakebase_configure_autoscaling` — Valid Range

**Purpose**: Verify autoscaling configuration within limits.

**Steps**:
1. Call with `min_cu: 1`, `max_cu: 4` (spread = 3, valid)
2. Call with `min_cu: 0.5`, `max_cu: 8.5` (spread = 8, valid)

**Expected**:
- Returns JSON: `{ "status": "configured", "autoscaling_enabled": true, "min_cu": ..., "max_cu": ..., "ram_range": "..." }`
- `ram_range` shows `min_cu*2 — max_cu*2` GB

### 5.3 — `lakebase_configure_autoscaling` — Invalid Range

**Purpose**: Verify autoscaling range validation (max spread = 8 CU).

**Steps**:
1. Call with `min_cu: 1`, `max_cu: 10` (spread = 9, exceeds 8)
2. Call with `min_cu: 0.5`, `max_cu: 32` (spread = 31.5, exceeds 8)

**Expected**:
- Returns error: "Autoscaling range too wide. max_cu (...) - min_cu (...) = ..., but maximum allowed spread is 8 CU."
- Suggests corrected `max_cu` value

### 5.4 — `lakebase_configure_scale_to_zero`

**Purpose**: Verify scale-to-zero enable/disable with timeout bounds.

**Steps**:
1. Call with `enabled: true`, `timeout_seconds: 60` (minimum)
2. Call with `enabled: true`, `timeout_seconds: 3600` (maximum)
3. Call with `enabled: false`

**Expected**:
- Step 1-2: Returns `{ "scale_to_zero_enabled": true, "timeout_seconds": ... }` with message about suspension
- Step 3: Returns `{ "scale_to_zero_enabled": false }` with message about compute staying active

### 5.5 — `lakebase_get_compute_metrics`

**Purpose**: Verify time-series metrics retrieval.

**Steps**:
1. Call with `period_minutes: 60` (last hour)
2. Call with `period_minutes: 1440` (last 24 hours)

**Expected**:
- Returns JSON with CPU%, memory%, working set, connections, state transitions, CU allocation over time

### 5.6 — `lakebase_restart_compute`

**Purpose**: Verify compute restart (destructive — test carefully).

**Steps**:
1. Call `lakebase_restart_compute` with `project_name`, `branch_name` (preferably a non-production branch)

**Expected**:
- Returns `{ "status": "restarting", "message": "Compute is restarting..." }`
- Subsequent queries may fail temporarily until restart completes

### 5.7 — `lakebase_create_read_replica` — Valid and Invalid

**Purpose**: Verify read replica creation with autoscaling validation.

**Steps**:
1. Call with `min_cu: 0.5`, `max_cu: 4` (valid)
2. Call with `min_cu: 1`, `max_cu: 10` (spread > 8, invalid)

**Expected**:
- Step 1: Returns `{ "status": "creating", "compute_type": "read_replica", ... }`
- Step 2: Returns error about max spread being 8 CU

---

## Scenario 6: Migration Tools (2 tools)

### 6.1 — `lakebase_prepare_migration`

**Purpose**: Verify branch-based migration preparation.

**Steps**:
1. Call `lakebase_prepare_migration` with:
   - `project_name: "your-project"`
   - `migration_sql: "CREATE TABLE migration_test (id serial PRIMARY KEY, data text)"`
   - `description: "Add migration_test table"`

**Expected**:
- Returns JSON with `status: "prepared"`, auto-generated `migration_branch` name (e.g., `migration-a1b2c3d4`)
- `next_steps` array with testing and completion instructions

### 6.2 — `lakebase_complete_migration` — Apply

**Purpose**: Verify migration application to production.

**Steps**:
1. Call `lakebase_complete_migration` with `migration_branch` from 6.1, `apply: true`

**Expected**:
- Returns `{ "status": "applied", "message": "Migration from '...' applied to production branch." }`

### 6.3 — `lakebase_complete_migration` — Discard

**Purpose**: Verify migration rollback (branch deletion).

**Steps**:
1. First call `lakebase_prepare_migration` to create a new migration branch
2. Call `lakebase_complete_migration` with that branch, `apply: false`

**Expected**:
- Returns `{ "status": "discarded", "message": "Migration branch '...' discarded. No changes applied." }`
- Branch is deleted (verify with `lakebase_list_branches`)

---

## Scenario 7: Sync Tools (2 tools)

### 7.1 — `lakebase_create_sync` — All Directions and Frequencies

**Purpose**: Verify Delta-Lakebase sync pipeline creation.

**Steps**:
1. Call with `direction: "delta_to_lakebase"`, `frequency: "snapshot"`, `source_table: "catalog.schema.table"`, `target_table: "public.table"`
2. Call with `direction: "lakebase_to_delta"`, `frequency: "continuous"`
3. Call with `frequency: "triggered"`

**Expected**:
- Returns JSON with `status: "created"`, `sync_id`, `direction`, `frequency`, and `message`

### 7.2 — `lakebase_list_syncs`

**Purpose**: Verify sync pipeline enumeration.

**Steps**:
1. Call with `project_name: "your-project"`

**Expected**:
- Returns JSON array of syncs with source, target, direction, frequency, status, last sync time

---

## Scenario 8: Data Quality Tools (1 tool)

### 8.1 — `lakebase_profile_table` — Numeric and Text Columns

**Purpose**: Verify per-column data profiling.

**Precondition**: Table with mixed column types exists.

**Steps**:
1. Call `lakebase_profile_table` with `table_name: "public.your_table"`, `sample_size: 1000`
2. Call with `response_format: "json"`

**Expected** (Markdown):
- Header: `## Data Profile: public.your_table` + `Total Rows: N`
- Table columns: Column | Type | Nulls% | Distinct | Min | Max | Avg
- Numeric columns have min/max/avg/stddev values
- String/text columns have null% and distinct counts

**Expected** (JSON):
- `{ "table": "...", "total_rows": N, "columns": [{ "column": "...", "data_type": "...", "null_count": ..., "null_pct": ..., "distinct_count": ..., "min_val": ..., "max_val": ..., "avg_val": ..., "stddev_val": ... }] }`

### 8.2 — `lakebase_profile_table` — Sample Size Bounds

**Purpose**: Verify sample_size validation.

**Steps**:
1. Call with `sample_size: 99` (below min 100)
2. Call with `sample_size: 1000001` (above max 1M)

**Expected**:
- Both rejected by Pydantic validation (ge=100, le=1000000)

---

## Scenario 9: Feature Store Tools (2 tools)

### 9.1 — `lakebase_lookup_features`

**Purpose**: Verify low-latency feature point lookup.

**Precondition**: Feature table exists (e.g., `features.customer_features` with `customer_id` key).

**Steps**:
1. Call with `feature_table: "features.customer_features"`, `entity_keys: {"customer_id": "12345"}`
2. Call with specific features: `features: ["avg_spend", "churn_score"]`
3. Call with non-existent entity key

**Expected**:
- Step 1: Returns all columns for entity
- Step 2: Returns only requested feature columns
- Step 3: Returns empty `features` array

### 9.2 — `lakebase_list_feature_tables`

**Purpose**: Verify feature table enumeration.

**Steps**:
1. Call with `schema_name: "features"` (default)
2. Call with `schema_name: "public"`

**Expected**:
- Returns JSON array with `table_name`, `row_count`, `size` for each base table in the schema

---

## Scenario 10: Insights Tool and Resource (1 tool + 1 resource)

### 10.1 — `lakebase_append_insight`

**Purpose**: Verify insight recording to session memo.

**Steps**:
1. Call with `insight: "Revenue table has 5% null values in the region column"`
2. Call again with `insight: "Transactions grow 12% MoM in Q4 2024"`
3. Read the `memo://insights` resource

**Expected**:
- Step 1: Returns "Insight recorded (1 total). View all at memo://insights"
- Step 2: Returns "Insight recorded (2 total)..."
- Step 3 (resource): Returns:
  ```
  - Revenue table has 5% null values in the region column
  - Transactions grow 12% MoM in Q4 2024
  ```

### 10.2 — `memo://insights` — Empty State

**Purpose**: Verify empty insights behavior.

**Steps**:
1. Start a fresh server/session
2. Read the `memo://insights` resource

**Expected**:
- Returns "No insights recorded yet. Use lakebase_append_insight to add discoveries."

---

## Scenario 11: Prompt Templates (4 prompts)

### 11.1 — List and Retrieve Prompts

**Steps** (via MCP client):
1. `await session.list_prompts()` — should list 4 prompts
2. `await session.get_prompt("lakebase_explore_database")`
3. `await session.get_prompt("lakebase_safe_migration")`
4. `await session.get_prompt("lakebase_setup_sync")`
5. `await session.get_prompt("lakebase_autoscaling_tuning")`

**Expected**:
- 4 prompts returned in list
- Each prompt contains step-by-step instructions referencing the correct tool names
- `lakebase_explore_database`: References `lakebase_list_schemas`, `lakebase_list_tables`, `lakebase_describe_table`, `lakebase_read_query`, `lakebase_profile_table`, `lakebase_append_insight`
- `lakebase_safe_migration`: References `lakebase_prepare_migration`, `lakebase_read_query`, `lakebase_explain_query`, `lakebase_complete_migration`
- `lakebase_setup_sync`: References `lakebase_create_sync`, `lakebase_list_syncs`
- `lakebase_autoscaling_tuning`: References `lakebase_get_compute_status`, `lakebase_get_compute_metrics`, `lakebase_configure_autoscaling`, `lakebase_configure_scale_to_zero`, `lakebase_create_read_replica`

---

## Scenario 12: Connection Pool and Resilience

### 12.1 — Scale-to-Zero Retry

**Purpose**: Verify exponential backoff when compute is waking.

**Setup**: Configure a Lakebase branch with scale-to-zero enabled and a short timeout. Wait for it to suspend.

**Steps**:
1. Send a read query while compute is suspended
2. Observe server logs for retry attempts

**Expected**:
- Server logs show: "Connection attempt 1/5 failed (compute may be waking from scale-to-zero). Retrying in 0.5s..."
- Retry delays double: 0.5s, 1.0s, 2.0s, 4.0s (capped at `LAKEBASE_S2Z_MAX_DELAY`)
- Query succeeds after compute wakes (within 5 attempts)
- If all retries exhaust: Returns "Lakebase compute is waking up from scale-to-zero. Retries exhausted."

### 12.2 — Read Replica Routing

**Purpose**: Verify queries route to replica pool.

**Setup**: Configure `LAKEBASE_REPLICA_HOST` and restart server.

**Steps**:
1. Call `lakebase_read_query` (should route to replica)
2. Call `lakebase_execute_query` with a SELECT (should route to primary)
3. Check server logs for pool selection

**Expected**:
- `lakebase_read_query` uses `execute_readonly()` which calls `connection(prefer_replica=True)`
- `lakebase_execute_query` with write SQL uses `execute_query()` which uses primary pool
- Read-only via `execute_query` (non-write SELECT) also routes to primary (only `execute_readonly` prefers replica)

### 12.3 — Pool Lifecycle

**Purpose**: Verify connection recycling and health checks.

**Steps**:
1. Start server, wait > `LAKEBASE_POOL_MAX_LIFETIME` (300s default)
2. Execute a query

**Expected**:
- Server recycles stale connections transparently
- Query succeeds on fresh connection
- `max_idle` (60s) evicts idle connections in pool

---

## Scenario 13: Error Handling

### 13.1 — Table Not Found

**Steps**:
1. Call `lakebase_read_query` with `sql: "SELECT * FROM nonexistent_table_xyz"`

**Expected**:
- Returns: "Error: Table 'nonexistent_table_xyz' does not exist. Use lakebase_list_tables to discover available tables, or lakebase_list_schemas to check schema names."

### 13.2 — SQL Syntax Error

**Steps**:
1. Call `lakebase_read_query` with `sql: "SELEC * FORM bad_query"`

**Expected**:
- Returns: "Error: SQL syntax error — ..."

### 13.3 — Query Timeout

**Steps**:
1. Call `lakebase_read_query` with a very slow query (e.g., `"SELECT pg_sleep(60)"`)

**Expected**:
- Returns: "Error: Query timed out. Try limiting rows with LIMIT or simplifying the query."

### 13.4 — Permission Denied

**Steps**:
1. Try accessing a table outside the user's UC permissions

**Expected**:
- Returns: "Error: Permission denied. Your Unity Catalog permissions do not allow this operation."

### 13.5 — Input Validation

**Steps**:
1. `lakebase_read_query` with `sql: ""` (empty)
2. `lakebase_read_query` with `max_rows: 0` (below min 1)
3. `lakebase_read_query` with `max_rows: 1001` (above max 1000)
4. `lakebase_configure_scale_to_zero` with `timeout_seconds: 59` (below min 60)
5. `lakebase_configure_scale_to_zero` with `timeout_seconds: 3601` (above max 3600)
6. `lakebase_configure_autoscaling` with `min_cu: 0.4` (below min 0.5)
7. `lakebase_get_compute_metrics` with `period_minutes: 4` (below min 5)

**Expected**:
- All rejected by Pydantic validators with descriptive error messages

---

## Scenario 14: MCP Protocol Compliance

### 14.1 — Tool Discovery

**Steps**:
1. `await session.list_tools()`

**Expected**:
- Returns exactly 27 tools
- Each tool has: `name`, `description`, `inputSchema`, `annotations`
- Annotations include: `title`, `readOnlyHint`, `destructiveHint`, `idempotentHint`

### 14.2 — Resource Discovery

**Steps**:
1. `await session.list_resources()`

**Expected**:
- Returns 1 resource: `memo://insights`

### 14.3 — Prompt Discovery

**Steps**:
1. `await session.list_prompts()`

**Expected**:
- Returns 4 prompts: `lakebase_explore_database`, `lakebase_safe_migration`, `lakebase_setup_sync`, `lakebase_autoscaling_tuning`

### 14.4 — Tool Annotations Correctness

**Steps**:
1. Verify read-only tools have `readOnlyHint: true`:
   - `lakebase_read_query`, `lakebase_explain_query`, all schema tools, `lakebase_list_projects`, `lakebase_describe_project`, `lakebase_get_connection_string`, `lakebase_list_branches`, `lakebase_get_compute_status`, `lakebase_get_compute_metrics`, `lakebase_list_syncs`, `lakebase_profile_table`, `lakebase_lookup_features`, `lakebase_list_feature_tables`
2. Verify destructive tools have `destructiveHint: true`:
   - `lakebase_delete_branch`
3. Verify `lakebase_execute_query` has `readOnlyHint: false`

---

## Scenario 15: End-to-End Workflows

### 15.1 — Database Exploration Workflow

**Purpose**: Simulate the `lakebase_explore_database` prompt template end-to-end.

**Steps**:
1. `lakebase_list_schemas` — discover schemas
2. `lakebase_list_tables` with the `public` schema — find tables
3. `lakebase_describe_table` with the first table — understand schema
4. `lakebase_read_query` with `SELECT * FROM first_table LIMIT 10` — sample data
5. `lakebase_profile_table` with the same table — data quality check
6. `lakebase_append_insight` — record a finding
7. Read `memo://insights` — verify insight was saved

**Expected**: Each step succeeds; insights accumulate; all metadata is consistent.

### 15.2 — Safe Migration Workflow

**Purpose**: Simulate the `lakebase_safe_migration` prompt template end-to-end.

**Steps**:
1. `lakebase_prepare_migration` with DDL: `"ALTER TABLE your_table ADD COLUMN test_col text"`
2. Record the `migration_branch` name from the response
3. `lakebase_describe_table` on the migrated table (on branch) — verify `test_col` exists
4. `lakebase_explain_query` on a SELECT against the table — verify plan is sane
5. `lakebase_complete_migration` with `apply: false` (discard to keep prod clean)
6. Verify branch is deleted via `lakebase_list_branches`

**Expected**: Migration branch is created, DDL is applied, testing works, discard cleans up.

### 15.3 — Autoscaling Tuning Workflow

**Purpose**: Simulate the `lakebase_autoscaling_tuning` prompt template end-to-end.

**Steps**:
1. `lakebase_get_compute_status` — current state and CU
2. `lakebase_get_compute_metrics` with `period_minutes: 60` — usage trends
3. `lakebase_configure_autoscaling` — adjust min/max CU based on metrics
4. `lakebase_configure_scale_to_zero` — set timeout based on workload type
5. Optionally `lakebase_create_read_replica` for read-heavy workloads

**Expected**: Each tool returns valid status/metrics; configurations apply without errors.

### 15.4 — Delta Sync Workflow

**Purpose**: Simulate the `lakebase_setup_sync` prompt template end-to-end.

**Steps**:
1. `lakebase_list_projects` — identify target project
2. `lakebase_create_sync` with `direction: "delta_to_lakebase"`, `frequency: "continuous"`
3. `lakebase_list_syncs` — verify pipeline appears

**Expected**: Sync is created and listed with correct configuration.

---

## Running Automated Tests

### Unit Tests (No Connection Required)

```bash
uv run pytest tests/test_unit/ -v
```

Tests: SQL validation, write detection, formatting, error handling, autoscaling range validation, connection pool mocking, branching protection logic.

### Integration Tests (Live Lakebase Connection)

```bash
LAKEBASE_LIVE_TEST=true uv run pytest tests/test_integration/ -v
```

Tests: Real authentication, live database queries, actual tool execution.

### End-to-End Tests (Running MCP Server)

```bash
# Terminal 1: Start server
uv run lakebase-mcp

# Terminal 2: Run E2E tests
LAKEBASE_E2E_TEST=true MCP_SERVER_URL=http://localhost:8000/mcp \
  uv run pytest tests/test_e2e/ -v
```

Tests: Full MCP protocol compliance, tool invocation through the HTTP transport.

---

## Test Sign-Off Checklist

| Category | Tests | Pass/Fail | Tester | Date |
|----------|-------|-----------|--------|------|
| Query (3 tools) | 1.1–1.6 | | | |
| Schema (4 tools) | 2.1–2.4 | | | |
| Project (3 tools) | 3.1–3.3 | | | |
| Branching (3 tools) | 4.1–4.3 | | | |
| Compute (6 tools) | 5.1–5.7 | | | |
| Migration (2 tools) | 6.1–6.3 | | | |
| Sync (2 tools) | 7.1–7.2 | | | |
| Quality (1 tool) | 8.1–8.2 | | | |
| Feature Store (2 tools) | 9.1–9.2 | | | |
| Insights (1 tool + 1 resource) | 10.1–10.2 | | | |
| Prompts (4 templates) | 11.1 | | | |
| Resilience (pool) | 12.1–12.3 | | | |
| Error Handling | 13.1–13.5 | | | |
| MCP Protocol | 14.1–14.4 | | | |
| E2E Workflows | 15.1–15.4 | | | |
| Unit Tests | `pytest tests/test_unit/` | | | |
| Integration Tests | `pytest tests/test_integration/` | | | |
| E2E Tests | `pytest tests/test_e2e/` | | | |
| Governance — SQL | 16.1–16.5 | | | |
| Governance — Tools | 17.1–17.4 | | | |
| Governance — Profiles | 18.1–18.4 | | | |
| Governance — Backward Compat | 19.1–19.2 | | | |
| UC Governance Tools | 20.1–20.4 | | | |
| UC + MCP Integration | 21.1–21.2 | | | |

---

## Scenario 16: SQL Statement Governance (sqlglot-based)

### 16.1 — Read-Only SQL Profile

**Setup**: `export LAKEBASE_SQL_PROFILE=read_only`

**Steps**:
1. Call `lakebase_execute_query` with `sql: "SELECT 1"`
2. Call `lakebase_execute_query` with `sql: "INSERT INTO t VALUES (1)"`
3. Call `lakebase_execute_query` with `sql: "DROP TABLE t"`
4. Call `lakebase_execute_query` with `sql: "SHOW TABLES"`
5. Call `lakebase_execute_query` with `sql: "EXPLAIN SELECT 1"`

**Expected**:
- Step 1: Succeeds (SELECT allowed)
- Step 2: Error: "Statement type 'insert' is not allowed. Permitted types: describe, explain, select, show"
- Step 3: Error: "Statement type 'drop' is not allowed..."
- Step 4: Succeeds (SHOW allowed)
- Step 5: Succeeds (EXPLAIN allowed)

### 16.2 — CTE Detection (Critical Edge Case)

**Purpose**: Verify sqlglot correctly classifies CTEs — the case where regex fails.

**Setup**: `export LAKEBASE_SQL_PROFILE=read_only`

**Steps**:
1. Call `lakebase_execute_query` with `sql: "WITH data AS (SELECT 1 AS id) SELECT * FROM data"`
2. Call `lakebase_execute_query` with `sql: "WITH data AS (SELECT 1 AS id) INSERT INTO t SELECT * FROM data"`

**Expected**:
- Step 1: Succeeds (CTE wrapping SELECT → classified as SELECT)
- Step 2: Error: "Statement type 'insert' is not allowed" (CTE wrapping INSERT → classified as INSERT)

### 16.3 — Multi-Statement SQL

**Setup**: `export LAKEBASE_SQL_PROFILE=analyst` (allows SELECT + INSERT)

**Steps**:
1. Call `lakebase_execute_query` with `sql: "SELECT 1; INSERT INTO t VALUES (1)"`
2. Call `lakebase_execute_query` with `sql: "SELECT 1; DROP TABLE t"`

**Expected**:
- Step 1: Both statements allowed (SELECT + INSERT in analyst profile)
- Step 2: Error: "Statement type 'drop' is not allowed" (DROP not in analyst profile)

### 16.4 — Developer SQL Profile

**Setup**: `export LAKEBASE_SQL_PROFILE=developer`

**Steps**:
1. Call `lakebase_execute_query` with `sql: "CREATE TABLE test_gov (id int)"`
2. Call `lakebase_execute_query` with `sql: "ALTER TABLE test_gov ADD COLUMN name text"`
3. Call `lakebase_execute_query` with `sql: "INSERT INTO test_gov VALUES (1, 'test')"`
4. Call `lakebase_execute_query` with `sql: "DROP TABLE test_gov"` — should FAIL
5. Call `lakebase_execute_query` with `sql: "GRANT ALL ON test_gov TO someone"` — should FAIL

**Expected**:
- Steps 1–3: Succeed (CREATE, ALTER, INSERT in developer profile)
- Step 4: Error (DROP not in developer profile)
- Step 5: Error (GRANT not in developer profile)

### 16.5 — SQL Denied Types Override

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=developer
export LAKEBASE_SQL_DENIED_TYPES=create,alter
```

**Steps**:
1. Call `lakebase_execute_query` with `sql: "SELECT 1"` — should work
2. Call `lakebase_execute_query` with `sql: "CREATE TABLE t (id int)"` — should FAIL
3. Call `lakebase_execute_query` with `sql: "INSERT INTO t VALUES (1)"` — should work

**Expected**:
- Step 1: Succeeds (SELECT still in developer profile)
- Step 2: Error (CREATE explicitly denied)
- Step 3: Succeeds (INSERT still in developer profile, not denied)

---

## Scenario 17: Tool Access Control

### 17.1 — Read-Only Tool Profile

**Setup**: `export LAKEBASE_TOOL_PROFILE=read_only`

**Steps**:
1. Call `lakebase_read_query` — should work (sql_query category allowed)
2. Call `lakebase_list_schemas` — should work (schema_read allowed)
3. Call `lakebase_create_branch` — should FAIL (branch_write not in read_only)
4. Call `lakebase_restart_compute` — should FAIL (compute_write not in read_only)
5. Call `lakebase_prepare_migration` — should FAIL (migration not in read_only)

**Expected**:
- Steps 1–2: Succeed
- Steps 3–5: Error: "Tool 'tool_name' is not permitted by the current governance policy."

### 17.2 — Individual Tool Deny List

**Setup**:
```bash
export LAKEBASE_TOOL_PROFILE=admin
export LAKEBASE_TOOL_DENIED=lakebase_execute_query,lakebase_delete_branch
```

**Steps**:
1. Call `lakebase_read_query` — should work
2. Call `lakebase_execute_query` — should FAIL (individually denied)
3. Call `lakebase_create_branch` — should work
4. Call `lakebase_delete_branch` — should FAIL (individually denied)

**Expected**:
- Admin profile allows all, but individual deny overrides

### 17.3 — Category Deny Override

**Setup**:
```bash
export LAKEBASE_TOOL_PROFILE=developer
export LAKEBASE_TOOL_DENIED_CATEGORIES=compute_write,migration
```

**Steps**:
1. Call `lakebase_get_compute_status` — should work (compute_read, not compute_write)
2. Call `lakebase_configure_autoscaling` — should FAIL (compute_write denied)
3. Call `lakebase_prepare_migration` — should FAIL (migration denied)
4. Call `lakebase_create_branch` — should work (branch_write still in developer)

### 17.4 — Dual-Layer Enforcement

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=read_only
export LAKEBASE_TOOL_PROFILE=admin
```

**Steps**:
1. Call `lakebase_execute_query` with `sql: "SELECT 1"` — should work (tool allowed + SQL allowed)
2. Call `lakebase_execute_query` with `sql: "INSERT INTO t VALUES (1)"` — should FAIL (tool allowed but SQL denied)
3. Call `lakebase_create_branch` — should work (tool allowed, no SQL governance)

**Expected**: Both governance layers enforce independently.

---

## Scenario 18: Governance Profiles End-to-End

### 18.1 — Analyst Profile (Full Stack)

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=analyst
export LAKEBASE_TOOL_PROFILE=analyst
```

**Steps**:
1. `lakebase_list_schemas` — works
2. `lakebase_list_tables` — works
3. `lakebase_read_query` with SELECT — works
4. `lakebase_execute_query` with INSERT — works (analyst allows INSERT)
5. `lakebase_execute_query` with DROP — fails
6. `lakebase_profile_table` — works (quality in analyst tools)
7. `lakebase_create_branch` — fails (branch_write not in analyst)

### 18.2 — Developer Profile (Full Stack)

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=developer
export LAKEBASE_TOOL_PROFILE=developer
```

**Steps**:
1. `lakebase_execute_query` with CREATE TABLE — works
2. `lakebase_execute_query` with INSERT — works
3. `lakebase_execute_query` with UPDATE — works
4. `lakebase_execute_query` with DELETE — works
5. `lakebase_execute_query` with DROP — fails (not in developer SQL)
6. `lakebase_create_branch` — works (branch_write in developer)
7. `lakebase_prepare_migration` — works (migration in developer)

### 18.3 — Admin Profile (Full Stack)

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=admin
export LAKEBASE_TOOL_PROFILE=admin
```

**Steps**:
1. `lakebase_execute_query` with any statement type — all work
2. All 27 tools accessible — no restrictions

### 18.4 — Customer Demo: Read-Only Agent (DB-I-15833)

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=read_only
export LAKEBASE_TOOL_PROFILE=read_only
export LAKEBASE_TOOL_DENIED=lakebase_execute_query
```

**Steps**:
1. `lakebase_read_query` with SELECT — works
2. `lakebase_execute_query` — fails (individually denied)
3. `lakebase_list_schemas` — works
4. `lakebase_describe_table` — works
5. `lakebase_profile_table` — works
6. `lakebase_create_branch` — fails
7. `lakebase_configure_autoscaling` — fails

**Expected**: Agent is fully restricted to read-only exploration. Cannot modify anything.

---

## Scenario 19: Backward Compatibility

### 19.1 — Legacy Mode (ALLOW_WRITE=false)

**Setup**: Only `LAKEBASE_ALLOW_WRITE=false` — NO governance env vars.

**Steps**:
1. `lakebase_execute_query` with `sql: "SELECT 1"` — works
2. `lakebase_execute_query` with `sql: "INSERT INTO t VALUES (1)"` — fails (write blocked)
3. `lakebase_read_query` with SELECT — works
4. All non-SQL tools — work (no tool restrictions in legacy mode)

**Expected**: Identical behavior to pre-governance version.

### 19.2 — Legacy Mode (ALLOW_WRITE=true)

**Setup**: Only `LAKEBASE_ALLOW_WRITE=true` — NO governance env vars.

**Steps**:
1. `lakebase_execute_query` with `sql: "INSERT INTO t VALUES (1)"` — works
2. `lakebase_execute_query` with `sql: "DROP TABLE t"` — works
3. All tools — work

**Expected**: Identical behavior to pre-governance version with writes enabled.

---

## Scenario 20: Unity Catalog Governance Tools (4 tools)

### 20.1 — `lakebase_get_uc_permissions` — Effective Permissions

**Purpose**: Verify UC permission introspection for Lakebase objects.

**Precondition**: Databricks SDK configured (DATABRICKS_HOST set).

**Steps**:
1. Call with `securable_type: "CATALOG"`, `full_name: "hls_amer_catalog"`
2. Call with `securable_type: "SCHEMA"`, `full_name: "hls_amer_catalog.public"`
3. Call with `securable_type: "TABLE"`, `full_name: "hls_amer_catalog.public.your_table"`
4. Call with `principal: "your-email@company.com"` to filter by user

**Expected**:
- Step 1: Shows all principals with catalog-level grants (USE_CATALOG, ALL_PRIVILEGES, etc.)
- Step 2: Shows schema-level grants plus inherited catalog grants
- Step 3: Shows table-level grants (SELECT, MODIFY, etc.) with inheritance chain
- Step 4: Filters to only the specified principal's grants

### 20.2 — `lakebase_check_my_access`

**Purpose**: Verify current user's own permission check.

**Steps**:
1. Call with `catalog: "hls_amer_catalog"` only (catalog-level)
2. Call with `catalog: "hls_amer_catalog"`, `schema_name: "public"` (schema-level)
3. Call with all three: `catalog`, `schema_name`, `table_name` (table-level)
4. Call with a catalog you don't have access to

**Expected**:
- Steps 1-3: Returns "Your Access" summary with privileges, Can read/Can write/Can create summary
- Step 4: Returns "no permissions" with GRANT recommendation SQL

### 20.3 — `lakebase_governance_summary`

**Purpose**: Verify combined governance view.

**Setup**: `export LAKEBASE_SQL_PROFILE=analyst`, `export LAKEBASE_TOOL_PROFILE=read_only`

**Steps**:
1. Call with `catalog: "hls_amer_catalog"`
2. Call without catalog (uses LAKEBASE_CATALOG env var)

**Expected**:
- Shows SQL Statement Governance section (allowed types: describe, explain, insert, select, set, show)
- Shows Tool Access Governance section (tool restrictions active)
- Shows UC Permissions section (user email, catalog privileges, recommended profile)

### 20.4 — `lakebase_list_catalog_grants`

**Purpose**: Verify catalog-wide grant listing for audit.

**Steps**:
1. Call with `catalog: "hls_amer_catalog"`, `include_schemas: true`
2. Call with `include_schemas: false`

**Expected**:
- Step 1: Shows catalog-level grants table + per-schema grants tables (Principal | Privileges)
- Step 2: Shows only catalog-level grants

---

## Scenario 21: UC Governance + MCP Governance Integration

### 21.1 — Governance-Aware Exploration Workflow

**Purpose**: End-to-end workflow using governance tools to guide exploration.

**Setup**: `export LAKEBASE_SQL_PROFILE=read_only`, `export LAKEBASE_TOOL_PROFILE=read_only`

**Steps**:
1. `lakebase_governance_summary` — understand current permissions
2. `lakebase_check_my_access` on target catalog — verify UC grants
3. `lakebase_list_schemas` — discover available schemas
4. `lakebase_list_tables` — find tables
5. `lakebase_read_query` with SELECT — query data (allowed by read_only)
6. `lakebase_execute_query` with INSERT — should FAIL (blocked by SQL governance)

**Expected**: Agent can introspect permissions, explore data, but cannot modify.

### 21.2 — Three-Layer Enforcement

**Purpose**: Verify all three governance layers work together.

**Setup**:
```bash
export LAKEBASE_SQL_PROFILE=developer
export LAKEBASE_TOOL_PROFILE=developer
# UC: user has SELECT but NOT MODIFY on the catalog
```

**Steps**:
1. `lakebase_governance_summary` — shows developer SQL profile, developer tool profile, UC SELECT-only
2. `lakebase_execute_query` with `INSERT INTO table VALUES (1)` — MCP allows (developer), but UC/PostgreSQL may deny
3. `lakebase_check_my_access` — confirms SELECT-only UC grants

**Expected**: MCP governance permits the operation but UC/PostgreSQL layer enforces actual data access control.
