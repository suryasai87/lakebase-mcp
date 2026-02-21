"""SQL query execution tools with safety controls."""
import re
import json
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.config import config
from server.utils.errors import handle_error
from server.utils.formatting import ResponseFormat, format_query_results

# SQL statement classifier
WRITE_PATTERNS = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)


class ExecuteQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    sql: str = Field(
        ...,
        description="SQL query to execute against the Lakebase database",
        min_length=1,
        max_length=50000,
    )
    max_rows: Optional[int] = Field(
        default=100, description="Maximum rows to return (1-1000)", ge=1, le=1000
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator("sql")
    @classmethod
    def validate_no_dangerous(cls, v: str) -> str:
        dangerous = ["pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf"]
        for d in dangerous:
            if d.lower() in v.lower():
                raise ValueError(f"Query contains blocked function: {d}")
        return v


class ExplainQueryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    sql: str = Field(
        ..., description="SQL query to analyze with EXPLAIN ANALYZE", min_length=1
    )
    analyze: bool = Field(
        default=False,
        description="Run EXPLAIN ANALYZE (actually executes the query)",
    )


def register_query_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_execute_query",
        annotations={
            "title": "Execute SQL Query",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_execute_query(params: ExecuteQueryInput) -> str:
        """Execute a SQL query against the connected Lakebase PostgreSQL database.

        Supports SELECT, INSERT, UPDATE, DELETE and DDL statements.
        Write operations require LAKEBASE_ALLOW_WRITE=true.
        All queries are subject to Unity Catalog permission enforcement.

        Returns results in markdown table or JSON format.
        """
        try:
            is_write = bool(WRITE_PATTERNS.match(params.sql))
            if is_write and not config.allow_write:
                return (
                    "Error: Write operations are disabled. "
                    "Set LAKEBASE_ALLOW_WRITE=true to enable INSERT, UPDATE, DELETE, DDL. "
                    "Use lakebase_read_query for read-only operations."
                )
            if is_write:
                rows = await pool.execute_query(params.sql, max_rows=params.max_rows)
            else:
                rows = await pool.execute_readonly(params.sql, max_rows=params.max_rows)
            return format_query_results(rows, fmt=params.response_format)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_read_query",
        annotations={
            "title": "Execute Read-Only SQL Query",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_read_query(params: ExecuteQueryInput) -> str:
        """Execute a read-only SQL query against Lakebase.

        Only SELECT statements are allowed. The query runs inside a
        READ ONLY transaction for safety. Routes to read replica if available.
        Ideal for data exploration, analytics, and reporting.
        """
        try:
            if WRITE_PATTERNS.match(params.sql):
                return "Error: Only SELECT queries are allowed with read_query. Use lakebase_execute_query for writes."
            rows = await pool.execute_readonly(params.sql, max_rows=params.max_rows)
            return format_query_results(rows, fmt=params.response_format)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_explain_query",
        annotations={
            "title": "Explain Query Execution Plan",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_explain_query(params: ExplainQueryInput) -> str:
        """Get the PostgreSQL execution plan for a SQL query using EXPLAIN.

        Helps understand query performance, identify missing indexes,
        and optimize slow queries. Use analyze=true to get actual timing
        (note: this executes the query).
        """
        try:
            explain_cmd = "EXPLAIN (FORMAT JSON, VERBOSE"
            if params.analyze:
                explain_cmd += ", ANALYZE, BUFFERS"
            explain_cmd += f") {params.sql}"
            rows = await pool.execute_readonly(explain_cmd)
            return json.dumps(rows, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
