"""Online Feature Store tools for Lakebase."""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.utils.errors import handle_error


class LookupFeaturesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    feature_table: str = Field(
        ..., description="Feature table name (schema.table)"
    )
    entity_keys: dict = Field(
        ...,
        description="Entity key-value pairs for lookup (e.g., {'customer_id': '12345'})",
    )
    features: Optional[List[str]] = Field(
        default=None,
        description="Specific feature columns to return. Returns all if None.",
    )


class ListFeatureTablesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    schema_name: str = Field(
        default="features", description="Schema containing feature tables"
    )


def register_feature_store_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_lookup_features",
        annotations={
            "title": "Lookup Online Features",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_lookup_features(params: LookupFeaturesInput) -> str:
        """Lookup real-time features from the Lakebase online feature store.

        Lakebase serves as the online feature store for Mosaic AI model serving.
        Use this tool to retrieve feature vectors for entities (customers, products, etc.)
        with low-latency (<10ms) point lookups.
        """
        try:
            parts = params.feature_table.split(".")
            schema = parts[0] if len(parts) > 1 else "features"
            table = parts[-1]
            cols = ", ".join(params.features) if params.features else "*"
            conditions = " AND ".join(
                [f"{k} = %s" for k in params.entity_keys.keys()]
            )
            values = tuple(params.entity_keys.values())
            rows = await pool.execute_readonly(
                f"SELECT {cols} FROM {schema}.{table} WHERE {conditions}",
                values,
            )
            return json.dumps(
                {"entity_keys": params.entity_keys, "features": rows},
                indent=2,
                default=str,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_feature_tables",
        annotations={
            "title": "List Feature Tables",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_feature_tables(
        params: ListFeatureTablesInput,
    ) -> str:
        """List all feature tables in the specified schema.
        Feature tables are synced from the lakehouse for online serving."""
        try:
            rows = await pool.execute_readonly(
                """SELECT table_name,
                       pg_stat_get_live_tuples(c.oid) AS row_count,
                       pg_size_pretty(pg_total_relation_size(c.oid)) AS size
                FROM information_schema.tables t
                JOIN pg_class c ON c.relname = t.table_name
                JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.table_schema
                WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
                ORDER BY t.table_name""",
                (params.schema_name,),
            )
            return json.dumps(rows, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
