"""Delta <-> Lakebase data synchronization tools.

Updated to use project_name (Gap 2).
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class SyncDirection(str, Enum):
    DELTA_TO_LAKEBASE = "delta_to_lakebase"
    LAKEBASE_TO_DELTA = "lakebase_to_delta"


class SyncFrequency(str, Enum):
    SNAPSHOT = "snapshot"
    TRIGGERED = "triggered"
    CONTINUOUS = "continuous"


class CreateSyncInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    source_table: str = Field(
        ...,
        description="Source table (e.g., 'catalog.schema.table' for UC or 'schema.table' for Lakebase)",
    )
    target_table: str = Field(..., description="Target table")
    direction: SyncDirection = Field(
        ..., description="Sync direction: delta_to_lakebase or lakebase_to_delta"
    )
    frequency: SyncFrequency = Field(
        default=SyncFrequency.TRIGGERED, description="Sync frequency"
    )
    project_name: str = Field(..., description="Lakebase project name")


class ListSyncsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


def register_sync_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_create_sync",
        annotations={
            "title": "Create Data Sync Pipeline",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_sync(params: CreateSyncInput) -> str:
        """Create a data synchronization pipeline between Delta tables (Unity Catalog) and Lakebase.

        Supports:
        - delta_to_lakebase: Sync UC managed tables INTO Lakebase for low-latency serving
        - lakebase_to_delta: Sync operational Lakebase data INTO the lakehouse for analytics

        Frequency options:
        - snapshot: One-time copy
        - triggered: Manual or event-triggered sync
        - continuous: Near real-time CDC-based sync
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/syncs",
                body={
                    "source_table": params.source_table,
                    "target_table": params.target_table,
                    "direction": params.direction.value,
                    "frequency": params.frequency.value,
                },
            )
            return json.dumps(
                {
                    "status": "created",
                    "sync_id": result.get("sync_id"),
                    "direction": params.direction.value,
                    "frequency": params.frequency.value,
                    "message": f"Sync pipeline created: {params.source_table} -> {params.target_table}",
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_syncs",
        annotations={
            "title": "List Sync Pipelines",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_syncs(params: ListSyncsInput) -> str:
        """List all data sync pipelines for a Lakebase project.
        Shows source, target, direction, frequency, status, and last sync time."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/syncs",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
