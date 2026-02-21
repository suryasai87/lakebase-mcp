"""Schema and metadata discovery tools."""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.utils.errors import handle_error
from server.utils.formatting import (
    ResponseFormat,
    format_table_list,
    format_schema_info,
)


class ListSchemasInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class ListTablesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    schema_name: str = Field(
        default="public", description="Schema to list tables from"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class DescribeTableInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    table_name: str = Field(
        ...,
        description="Fully qualified table name: schema.table or just table (defaults to public)",
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class ObjectTreeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    schema_name: Optional[str] = Field(
        default=None, description="Filter to a specific schema"
    )


def register_schema_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_list_schemas",
        annotations={
            "title": "List Database Schemas",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_schemas(params: ListSchemasInput) -> str:
        """List all schemas in the connected Lakebase database.
        Returns schema names, owners, and descriptions.
        Filters out internal PostgreSQL schemas (pg_catalog, information_schema, pg_toast)."""
        try:
            rows = await pool.execute_readonly(
                "SELECT schema_name, schema_owner FROM information_schema.schemata "
                "WHERE schema_name NOT LIKE 'pg_%' AND schema_name != 'information_schema' "
                "ORDER BY schema_name"
            )
            if params.response_format == ResponseFormat.JSON:
                return json.dumps(rows, indent=2, default=str)
            lines = ["## Schemas\n"]
            for r in rows:
                lines.append(
                    f"- **{r['schema_name']}** (owner: {r.get('schema_owner', 'N/A')})"
                )
            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_tables",
        annotations={
            "title": "List Tables in Schema",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_tables(params: ListTablesInput) -> str:
        """List all tables and views in a given schema. Shows table name, type (table/view),
        row estimate, and table size. Useful for exploring database contents."""
        try:
            rows = await pool.execute_readonly(
                """SELECT t.table_name, t.table_type,
                       pg_stat_get_live_tuples(c.oid) AS estimated_rows,
                       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
                FROM information_schema.tables t
                JOIN pg_class c ON c.relname = t.table_name
                JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.table_schema
                WHERE t.table_schema = %s
                ORDER BY t.table_name""",
                (params.schema_name,),
            )
            return format_table_list(rows, fmt=params.response_format)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_describe_table",
        annotations={
            "title": "Describe Table Schema",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_describe_table(params: DescribeTableInput) -> str:
        """Get the full schema of a table: column names, data types, nullability,
        defaults, constraints, and indexes. Essential for writing queries."""
        try:
            parts = params.table_name.split(".")
            schema = parts[0] if len(parts) > 1 else "public"
            table = parts[-1]
            cols = await pool.execute_readonly(
                """SELECT column_name, data_type, is_nullable, column_default,
                       character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position""",
                (schema, table),
            )
            indexes = await pool.execute_readonly(
                """SELECT indexname, indexdef FROM pg_indexes
                WHERE schemaname = %s AND tablename = %s""",
                (schema, table),
            )
            if params.response_format == ResponseFormat.JSON:
                return json.dumps(
                    {
                        "table": params.table_name,
                        "columns": cols,
                        "indexes": indexes,
                    },
                    indent=2,
                    default=str,
                )
            result = format_schema_info(cols, params.table_name)
            if indexes:
                result += "\n\n### Indexes\n"
                for idx in indexes:
                    result += f"- **{idx['indexname']}**: `{idx['indexdef']}`\n"
            return result
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_object_tree",
        annotations={
            "title": "Get Database Object Tree",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_object_tree(params: ObjectTreeInput) -> str:
        """Get a hierarchical tree view of all database objects: schemas -> tables -> columns.
        Like Neon's object tree but enhanced with Unity Catalog metadata overlay."""
        try:
            where = (
                "WHERE n.nspname = %s"
                if params.schema_name
                else "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname != 'information_schema'"
            )
            query_params = (params.schema_name,) if params.schema_name else None
            rows = await pool.execute_readonly(
                f"""SELECT n.nspname AS schema_name, c.relname AS table_name,
                       c.relkind AS object_type,
                       array_agg(a.attname ORDER BY a.attnum) AS columns
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                {where}
                AND c.relkind IN ('r', 'v', 'm')
                GROUP BY n.nspname, c.relname, c.relkind
                ORDER BY n.nspname, c.relname""",
                query_params,
            )
            tree = {}
            for r in rows:
                schema = r["schema_name"]
                if schema not in tree:
                    tree[schema] = []
                kind = {"r": "TABLE", "v": "VIEW", "m": "MATERIALIZED VIEW"}.get(
                    r["object_type"], "OTHER"
                )
                tree[schema].append(
                    {
                        "name": r["table_name"],
                        "type": kind,
                        "columns": r.get("columns", []),
                    }
                )
            return json.dumps(tree, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
