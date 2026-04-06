"""Synced Tables API tools — Delta → Lakebase reverse sync and sync status polling.

GAP-4 (HIGH): Delta → Lakebase reverse sync via Databricks REST API.
GAP-12 (LOW): Lakehouse Sync status polling via REST API.
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class ListSyncedTablesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class CreateSyncedTableInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    source_catalog: str = Field(
        ..., description="Unity Catalog catalog containing the source Delta table"
    )
    source_schema: str = Field(
        ..., description="Schema containing the source Delta table"
    )
    source_table: str = Field(
        ..., description="Source Delta table name"
    )
    target_schema: str = Field(
        ..., description="Target Lakebase schema for the synced table"
    )
    target_table: str = Field(
        ..., description="Target table name in Lakebase"
    )


class DeleteSyncedTableInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    table_name: str = Field(
        ..., description="Name of the synced table to delete"
    )


class GetSyncStatusInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    table_name: str = Field(
        ..., description="Name of the synced table to check status for"
    )


def register_synced_table_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_list_synced_tables",
        annotations={
            "title": "List Synced Tables",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_synced_tables(params: ListSyncedTablesInput) -> str:
        """List all synced tables for a Lakebase project.

        Shows source Delta table, target Lakebase table, sync status, and lag
        for each Delta → Lakebase synced table mapping."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/synced_tables",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_create_synced_table",
        annotations={
            "title": "Create Synced Table",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_synced_table(params: CreateSyncedTableInput) -> str:
        """Create a new Delta → Lakebase synced table.

        Sets up continuous synchronization from a Unity Catalog Delta table
        into a Lakebase table for low-latency serving. The sync is CDC-based
        and keeps the Lakebase table up to date as the source Delta table changes.

        Requires SELECT permission on the source Delta table and WRITE permission
        on the target Lakebase schema."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            source_full_name = (
                f"{params.source_catalog}.{params.source_schema}.{params.source_table}"
            )
            result = ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/synced_tables",
                body={
                    "source_catalog": params.source_catalog,
                    "source_schema": params.source_schema,
                    "source_table": params.source_table,
                    "target_schema": params.target_schema,
                    "target_table": params.target_table,
                },
            )
            return json.dumps(
                {
                    "status": "created",
                    "source": source_full_name,
                    "target": f"{params.target_schema}.{params.target_table}",
                    "project": params.project_name,
                    "synced_table_id": result.get("synced_table_id"),
                    "message": (
                        f"Synced table created: {source_full_name} → "
                        f"{params.target_schema}.{params.target_table}. "
                        "Use lakebase_get_sync_status to monitor synchronization progress."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_delete_synced_table",
        annotations={
            "title": "Delete Synced Table",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_delete_synced_table(params: DeleteSyncedTableInput) -> str:
        """Delete a synced table mapping. This stops synchronization and removes
        the sync configuration. The target Lakebase table data is NOT deleted —
        only the sync pipeline is removed."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            ws.api_client.do(
                "DELETE",
                f"/api/2.0/lakebase/projects/{params.project_name}/synced_tables/{params.table_name}",
            )
            return json.dumps(
                {
                    "status": "deleted",
                    "table_name": params.table_name,
                    "project": params.project_name,
                    "message": (
                        f"Synced table '{params.table_name}' deleted from project "
                        f"'{params.project_name}'. The target Lakebase table data "
                        "is preserved but will no longer receive updates."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_get_sync_status",
        annotations={
            "title": "Get Sync Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_get_sync_status(params: GetSyncStatusInput) -> str:
        """Poll detailed sync status for a synced table.

        Returns:
        - lag_bytes: bytes behind the source Delta table
        - lag_seconds: seconds behind the source Delta table
        - last_sync_time: timestamp of the last successful sync
        - row_count: number of rows in the target Lakebase table
        - status: current sync state (ACTIVE, SYNCING, ERROR, INITIALIZING)

        Use this to monitor sync health and verify data freshness."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/synced_tables/{params.table_name}/status",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
