"""Lakebase endpoint management tools — CRUD for project endpoints.

Endpoints are the network entry points for connecting to Lakebase branches.
Each endpoint has its own host, status, branch association, and CU allocation.
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class ListEndpointsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class CreateEndpointInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    endpoint_name: str = Field(
        ...,
        description="Name for the new endpoint (e.g., 'analytics-ro', 'dev-endpoint')",
    )
    branch: str = Field(
        default="production",
        description="Branch to associate the endpoint with (default: production)",
    )
    min_cu: Optional[int] = Field(
        default=None,
        description="Minimum compute units (CU) for autoscaling. Omit for project default.",
    )
    max_cu: Optional[int] = Field(
        default=None,
        description="Maximum compute units (CU) for autoscaling. Omit for project default.",
    )


class UpdateEndpointInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    endpoint_name: str = Field(..., description="Name of the endpoint to update")
    min_cu: Optional[int] = Field(
        default=None,
        description="New minimum compute units (CU) for autoscaling",
    )
    max_cu: Optional[int] = Field(
        default=None,
        description="New maximum compute units (CU) for autoscaling",
    )
    scale_to_zero_timeout: Optional[int] = Field(
        default=None,
        description="Idle timeout in seconds before scaling to zero. 0 disables scale-to-zero.",
    )


class DeleteEndpointInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    endpoint_name: str = Field(..., description="Name of the endpoint to delete")


def register_endpoint_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_list_endpoints",
        annotations={
            "title": "List Lakebase Endpoints",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_endpoints(params: ListEndpointsInput) -> str:
        """List all endpoints for a Lakebase project.

        Shows endpoint name, host, status, associated branch, and CU allocation
        (min/max compute units). Use this to discover available connection points
        and their current state before connecting or making changes."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/endpoints",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_create_endpoint",
        annotations={
            "title": "Create Lakebase Endpoint",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_endpoint(params: CreateEndpointInput) -> str:
        """Create a new endpoint for a Lakebase project.

        Endpoints provide network access to a specific branch with independent
        autoscaling configuration. Use cases:
        - Read-only analytics endpoint on production branch
        - Dedicated endpoint for a feature branch
        - Separate endpoint with different CU limits for workload isolation
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            body = {
                "endpoint_name": params.endpoint_name,
                "branch": params.branch,
            }
            if params.min_cu is not None:
                body["min_cu"] = params.min_cu
            if params.max_cu is not None:
                body["max_cu"] = params.max_cu

            result = ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/endpoints",
                body=body,
            )
            return json.dumps(
                {
                    "status": "created",
                    "endpoint": params.endpoint_name,
                    "project": params.project_name,
                    "branch": params.branch,
                    "message": (
                        f"Endpoint '{params.endpoint_name}' created on branch '{params.branch}'. "
                        f"Use lakebase_list_endpoints to check when it becomes active."
                    ),
                    "details": result,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_update_endpoint",
        annotations={
            "title": "Update Lakebase Endpoint",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_update_endpoint(params: UpdateEndpointInput) -> str:
        """Update the configuration of an existing Lakebase endpoint.

        Modify autoscaling limits (min/max CU) or scale-to-zero timeout.
        Changes may trigger a brief compute restart depending on the update."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            body = {}
            if params.min_cu is not None:
                body["min_cu"] = params.min_cu
            if params.max_cu is not None:
                body["max_cu"] = params.max_cu
            if params.scale_to_zero_timeout is not None:
                body["scale_to_zero_timeout"] = params.scale_to_zero_timeout

            if not body:
                return json.dumps(
                    {
                        "status": "no_change",
                        "message": "No update parameters provided. Specify at least one of: min_cu, max_cu, scale_to_zero_timeout.",
                    },
                    indent=2,
                )

            result = ws.api_client.do(
                "PATCH",
                f"/api/2.0/lakebase/projects/{params.project_name}/endpoints/{params.endpoint_name}",
                body=body,
            )
            return json.dumps(
                {
                    "status": "updated",
                    "endpoint": params.endpoint_name,
                    "project": params.project_name,
                    "changes": body,
                    "message": (
                        f"Endpoint '{params.endpoint_name}' updated. "
                        f"Changes may take a moment to apply."
                    ),
                    "details": result,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_delete_endpoint",
        annotations={
            "title": "Delete Lakebase Endpoint",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_delete_endpoint(params: DeleteEndpointInput) -> str:
        """Delete a Lakebase endpoint. This is irreversible.

        The primary endpoint cannot be deleted — this is a safety measure to
        prevent accidental loss of the main connection point for a project.
        Delete secondary/feature endpoints when they are no longer needed."""
        try:
            # Production protection: refuse to delete the primary endpoint
            if params.endpoint_name.lower() in ("primary", "main", "default"):
                return json.dumps(
                    {
                        "status": "refused",
                        "message": (
                            f"Cannot delete the primary endpoint '{params.endpoint_name}'. "
                            "This is a safety measure to protect the main connection point. "
                            "If you truly need to remove it, do so via the Databricks UI."
                        ),
                    },
                    indent=2,
                )

            auth = LakebaseAuth()
            ws = auth.workspace_client
            ws.api_client.do(
                "DELETE",
                f"/api/2.0/lakebase/projects/{params.project_name}/endpoints/{params.endpoint_name}",
            )
            return json.dumps(
                {
                    "status": "deleted",
                    "endpoint": params.endpoint_name,
                    "project": params.project_name,
                    "message": f"Endpoint '{params.endpoint_name}' deleted from project '{params.project_name}'.",
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)
