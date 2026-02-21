"""SQL query execution tools with safety controls.

Uses sqlglot-based SQL governance for fine-grained statement-type permissions.
"""
import json
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.config import config
from server.utils.errors import handle_error
from server.utils.formatting import ResponseFormat, format_query_results
from server.governance.policy import GovernancePolicy
from server.governance.sql_guard import SQLStatementType


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


def register_query_tools(mcp: FastMCP, governance: GovernancePolicy):

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
        Statement types are governed by the SQL governance policy
        (LAKEBASE_SQL_PROFILE or LAKEBASE_ALLOW_WRITE).
        All queries are subject to Unity Catalog permission enforcement.

        Returns results in markdown table or JSON format.
        """
        try:
            # SQL governance check (replaces old WRITE_PATTERNS regex)
            allowed, error_msg = governance.check_sql(params.sql)
            if not allowed:
                return f"Error: {error_msg}"

            # Route to read-only or read-write pool based on SQL classification
            if governance.sql_governor.is_write(params.sql):
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

        Only SELECT and EXPLAIN statements are allowed regardless of governance
        policy. The query runs inside a READ ONLY transaction for safety.
        Routes to read replica if available.
        Ideal for data exploration, analytics, and reporting.
        """
        try:
            # read_query always enforces SELECT/EXPLAIN-only regardless of governance
            read_allowed = {
                SQLStatementType.SELECT,
                SQLStatementType.EXPLAIN,
                SQLStatementType.SHOW,
                SQLStatementType.DESCRIBE,
            }
            types = governance.sql_governor.classify(params.sql)
            if not types or any(t not in read_allowed for t in types):
                return (
                    "Error: Only SELECT, EXPLAIN, SHOW, and DESCRIBE queries "
                    "are allowed with read_query. "
                    "Use lakebase_execute_query for writes."
                )
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
