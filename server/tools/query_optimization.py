"""Query optimization tools — slow query analysis and index recommendations.

Inspired by Neon MCP's list_slow_queries / prepare_query_tuning / complete_query_tuning.
Uses pg_stat_statements and pg_stat_user_indexes for analysis via psycopg.
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.utils.errors import handle_error
from server.utils.formatting import ResponseFormat, format_query_results


class SlowQueriesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    limit: int = Field(
        default=20,
        description="Number of slow queries to return",
        ge=1,
        le=100,
    )
    sort_by: str = Field(
        default="total_time",
        description="Sort metric: total_time, mean_time, calls, rows",
    )
    min_calls: int = Field(
        default=1,
        description="Minimum number of calls to include a query",
        ge=1,
    )
    min_mean_time_ms: float = Field(
        default=0,
        description="Minimum mean execution time in ms to include",
        ge=0,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class IndexUsageInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    schema_name: str = Field(
        default="public", description="Schema to analyze"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class TableStatsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    schema_name: str = Field(
        default="public", description="Schema to analyze"
    )
    min_seq_scan: int = Field(
        default=0,
        description="Minimum sequential scan count to include a table",
        ge=0,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


SORT_COLUMNS = {
    "total_time": "total_exec_time",
    "mean_time": "mean_exec_time",
    "calls": "calls",
    "rows": "rows",
}


def register_query_optimization_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_list_slow_queries",
        annotations={
            "title": "List Slow Queries",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_slow_queries(params: SlowQueriesInput) -> str:
        """List the slowest queries from pg_stat_statements.

        Identifies performance bottlenecks by showing queries ranked by
        total execution time, mean time, call count, or rows returned.
        Requires the pg_stat_statements extension to be enabled.

        Returns query text, call count, total/mean/min/max time,
        rows per call, and shared buffer hit ratio.
        """
        try:
            # Validate sort column to prevent injection
            sort_col = SORT_COLUMNS.get(params.sort_by)
            if not sort_col:
                return (
                    f"Error: Invalid sort_by '{params.sort_by}'. "
                    f"Valid options: {', '.join(SORT_COLUMNS.keys())}"
                )

            # Check if pg_stat_statements is available
            ext_check = await pool.execute_readonly(
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'",
                tool_name="lakebase_list_slow_queries",
            )
            if not ext_check:
                return (
                    "Error: pg_stat_statements extension is not installed. "
                    "Run `CREATE EXTENSION IF NOT EXISTS pg_stat_statements` "
                    "to enable slow query tracking."
                )

            rows = await pool.execute_readonly(
                f"""SELECT
                    LEFT(query, 200) AS query,
                    calls,
                    ROUND(total_exec_time::numeric, 2) AS total_time_ms,
                    ROUND(mean_exec_time::numeric, 2) AS mean_time_ms,
                    ROUND(min_exec_time::numeric, 2) AS min_time_ms,
                    ROUND(max_exec_time::numeric, 2) AS max_time_ms,
                    rows,
                    CASE WHEN calls > 0
                        THEN ROUND((rows::numeric / calls), 1)
                        ELSE 0
                    END AS rows_per_call,
                    CASE WHEN shared_blks_hit + shared_blks_read > 0
                        THEN ROUND(
                            100.0 * shared_blks_hit /
                            (shared_blks_hit + shared_blks_read), 1
                        )
                        ELSE 0
                    END AS cache_hit_pct
                FROM pg_stat_statements
                WHERE calls >= %s
                    AND mean_exec_time >= %s
                    AND query NOT LIKE '%%pg_stat_statements%%'
                ORDER BY {sort_col} DESC
                LIMIT %s""",
                (params.min_calls, params.min_mean_time_ms, params.limit),
                tool_name="lakebase_list_slow_queries",
            )

            if not rows:
                return "_No slow queries found matching the criteria._"

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(
                    {"slow_queries": rows, "sort_by": params.sort_by},
                    indent=2,
                    default=str,
                )

            lines = [
                f"## Slow Queries (sorted by {params.sort_by})\n",
                f"**{len(rows)} queries found**\n",
            ]
            for i, r in enumerate(rows, 1):
                lines.append(f"### {i}. `{r['query']}`\n")
                lines.append(
                    f"| Calls | Total (ms) | Mean (ms) | Min (ms) | Max (ms) "
                    f"| Rows/call | Cache Hit% |"
                )
                lines.append("| --- | --- | --- | --- | --- | --- | --- |")
                lines.append(
                    f"| {r['calls']} | {r['total_time_ms']} | {r['mean_time_ms']} "
                    f"| {r['min_time_ms']} | {r['max_time_ms']} "
                    f"| {r['rows_per_call']} | {r['cache_hit_pct']}% |\n"
                )
            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_index_usage",
        annotations={
            "title": "Analyze Index Usage",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_index_usage(params: IndexUsageInput) -> str:
        """Analyze index usage to find unused or underused indexes.

        Shows each index with its scan count, tuple reads, and size.
        Helps identify indexes that can be dropped (saving write overhead
        and storage) and tables that may need new indexes.
        """
        try:
            rows = await pool.execute_readonly(
                """SELECT
                    s.schemaname AS schema,
                    s.relname AS table,
                    s.indexrelname AS index,
                    s.idx_scan AS scans,
                    s.idx_tup_read AS tuples_read,
                    pg_size_pretty(pg_relation_size(s.indexrelid)) AS size,
                    i.indisunique AS is_unique,
                    i.indisprimary AS is_primary
                FROM pg_stat_user_indexes s
                JOIN pg_index i ON s.indexrelid = i.indexrelid
                WHERE s.schemaname = %s
                ORDER BY s.idx_scan ASC, pg_relation_size(s.indexrelid) DESC""",
                (params.schema_name,),
                tool_name="lakebase_index_usage",
            )

            if not rows:
                return f"_No indexes found in schema '{params.schema_name}'._"

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(
                    {"schema": params.schema_name, "indexes": rows},
                    indent=2,
                    default=str,
                )

            lines = [
                f"## Index Usage: `{params.schema_name}`\n",
                f"**{len(rows)} indexes** (sorted by scan count, ascending)\n",
                "| Table | Index | Scans | Tuples Read | Size | Unique | Primary |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
            for r in rows:
                lines.append(
                    f"| {r['table']} | {r['index']} | {r['scans']} "
                    f"| {r['tuples_read']} | {r['size']} "
                    f"| {'Yes' if r['is_unique'] else 'No'} "
                    f"| {'Yes' if r['is_primary'] else 'No'} |"
                )

            # Add recommendations
            unused = [r for r in rows if r["scans"] == 0 and not r["is_primary"] and not r["is_unique"]]
            if unused:
                lines.append(f"\n**{len(unused)} potentially unused indexes** (0 scans, not primary/unique):")
                for r in unused:
                    lines.append(f"- `{r['index']}` on `{r['table']}` ({r['size']})")

            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_table_scan_stats",
        annotations={
            "title": "Table Sequential Scan Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_table_scan_stats(params: TableStatsInput) -> str:
        """Show sequential vs index scan statistics for tables.

        Tables with high sequential scan counts and low index scan counts
        are candidates for adding indexes. Helps identify missing indexes
        that could dramatically improve query performance.
        """
        try:
            rows = await pool.execute_readonly(
                """SELECT
                    schemaname AS schema,
                    relname AS table,
                    seq_scan,
                    seq_tup_read,
                    COALESCE(idx_scan, 0) AS idx_scan,
                    COALESCE(idx_tup_fetch, 0) AS idx_tup_fetch,
                    n_live_tup AS live_rows,
                    n_dead_tup AS dead_rows,
                    CASE WHEN seq_scan + COALESCE(idx_scan, 0) > 0
                        THEN ROUND(
                            100.0 * COALESCE(idx_scan, 0) /
                            (seq_scan + COALESCE(idx_scan, 0)), 1
                        )
                        ELSE 0
                    END AS idx_scan_pct
                FROM pg_stat_user_tables
                WHERE schemaname = %s
                    AND seq_scan >= %s
                ORDER BY seq_scan DESC""",
                (params.schema_name, params.min_seq_scan),
                tool_name="lakebase_table_scan_stats",
            )

            if not rows:
                return f"_No tables found in schema '{params.schema_name}'._"

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(
                    {"schema": params.schema_name, "tables": rows},
                    indent=2,
                    default=str,
                )

            lines = [
                f"## Table Scan Stats: `{params.schema_name}`\n",
                "| Table | Seq Scans | Seq Rows | Idx Scans | Idx Rows | Idx% | Live Rows | Dead Rows |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
            for r in rows:
                lines.append(
                    f"| {r['table']} | {r['seq_scan']} | {r['seq_tup_read']} "
                    f"| {r['idx_scan']} | {r['idx_tup_fetch']} "
                    f"| {r['idx_scan_pct']}% | {r['live_rows']} | {r['dead_rows']} |"
                )

            # Flag tables needing indexes
            needs_index = [
                r for r in rows
                if r["seq_scan"] > 100 and r["idx_scan_pct"] < 50 and r["live_rows"] > 1000
            ]
            if needs_index:
                lines.append(f"\n**{len(needs_index)} tables may need indexes** (high seq scans, >1000 rows):")
                for r in needs_index:
                    lines.append(
                        f"- `{r['table']}`: {r['seq_scan']} seq scans, "
                        f"only {r['idx_scan_pct']}% index usage, {r['live_rows']} rows"
                    )

            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)
