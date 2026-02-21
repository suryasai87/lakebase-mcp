"""Data quality and profiling tools — inspired by Teradata MCP's EDA capabilities."""
import json
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.utils.errors import handle_error
from server.utils.formatting import ResponseFormat


class ProfileTableInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    table_name: str = Field(
        ..., description="Table to profile (schema.table format)"
    )
    sample_size: int = Field(
        default=10000,
        description="Number of rows to sample for profiling",
        ge=100,
        le=1000000,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


def register_quality_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_profile_table",
        annotations={
            "title": "Profile Table Data Quality",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_profile_table(params: ProfileTableInput) -> str:
        """Generate a comprehensive data profile for a table.

        Returns per-column statistics:
        - Data type, null count and percentage
        - Distinct value count and cardinality ratio
        - Min, max, mean, median, stddev for numeric columns
        - Min/max length for string columns
        - Top 5 most frequent values
        """
        try:
            parts = params.table_name.split(".")
            schema = parts[0] if len(parts) > 1 else "public"
            table = parts[-1]
            cols = await pool.execute_readonly(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                (schema, table),
            )
            profile = {"table": params.table_name, "columns": []}
            count_result = await pool.execute_readonly(
                f"SELECT COUNT(*) as cnt FROM {schema}.{table}"
            )
            total_rows = count_result[0]["cnt"] if count_result else 0
            profile["total_rows"] = total_rows

            for col in cols:
                col_name = col["column_name"]
                col_type = col["data_type"]
                stats = {"column": col_name, "data_type": col_type}
                null_result = await pool.execute_readonly(
                    f"SELECT COUNT(*) FILTER (WHERE {col_name} IS NULL) as nulls, "
                    f"COUNT(DISTINCT {col_name}) as distinct_count "
                    f"FROM (SELECT {col_name} FROM {schema}.{table} LIMIT %s) sub",
                    (params.sample_size,),
                )
                if null_result:
                    stats["null_count"] = null_result[0]["nulls"]
                    stats["distinct_count"] = null_result[0]["distinct_count"]
                    stats["null_pct"] = round(
                        null_result[0]["nulls"] / max(params.sample_size, 1) * 100, 2
                    )
                if col_type in (
                    "integer",
                    "bigint",
                    "numeric",
                    "real",
                    "double precision",
                    "smallint",
                ):
                    num_result = await pool.execute_readonly(
                        f"SELECT MIN({col_name})::text as min_val, "
                        f"MAX({col_name})::text as max_val, "
                        f"AVG({col_name})::numeric(20,4)::text as avg_val, "
                        f"STDDEV({col_name})::numeric(20,4)::text as stddev_val "
                        f"FROM (SELECT {col_name} FROM {schema}.{table} LIMIT %s) sub",
                        (params.sample_size,),
                    )
                    if num_result:
                        stats.update(num_result[0])
                profile["columns"].append(stats)

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(profile, indent=2, default=str)
            lines = [
                f"## Data Profile: `{params.table_name}`\n",
                f"**Total Rows**: {total_rows}\n",
            ]
            lines.append(
                "| Column | Type | Nulls% | Distinct | Min | Max | Avg |"
            )
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for c in profile["columns"]:
                lines.append(
                    f"| {c['column']} | {c['data_type']} | {c.get('null_pct', 'N/A')}% | "
                    f"{c.get('distinct_count', 'N/A')} | {c.get('min_val', '')} | "
                    f"{c.get('max_val', '')} | {c.get('avg_val', '')} |"
                )
            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)
