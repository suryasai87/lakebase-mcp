"""Lakebase project lifecycle management tools.

Merged: base instance tools RENAMED to project hierarchy (Gap 2).
Autoscaling model: Workspace -> Project(s) -> Branch(es) -> Compute(s) + Read Replica(s)
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class ListProjectsInput(BaseModel):
    """List Lakebase projects (replaces ListInstancesInput)."""

    model_config = ConfigDict(str_strip_whitespace=True)
    catalog: Optional[str] = Field(
        default=None, description="Filter by UC catalog name"
    )


class DescribeProjectInput(BaseModel):
    """Describe a Lakebase project (replaces DescribeInstanceInput)."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class GetConnectionStringInput(BaseModel):
    """Get connection string for a specific project/branch/compute."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(
        default="production", description="Branch name (default: production)"
    )
    compute_type: str = Field(
        default="primary",
        description="'primary' (read-write) or 'replica' (read-only)",
    )


def register_instance_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_list_projects",
        annotations={
            "title": "List Lakebase Projects",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_projects(params: ListProjectsInput) -> str:
        """List all Lakebase projects accessible to the current user.
        Shows project name, state, catalog, region, branches, and compute status.

        Lakebase Autoscaling hierarchy: Project -> Branch(es) -> Compute(s)."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do("GET", "/api/2.0/lakebase/projects")
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_describe_project",
        annotations={
            "title": "Describe Lakebase Project",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_describe_project(params: DescribeProjectInput) -> str:
        """Get detailed information about a Lakebase project:
        configuration, branches, compute sizes, storage usage, sync pipelines, and status."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET", f"/api/2.0/lakebase/projects/{params.project_name}"
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_get_connection_string",
        annotations={
            "title": "Get Lakebase Connection String",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_get_connection_string(
        params: GetConnectionStringInput,
    ) -> str:
        """Get the PostgreSQL connection string for a Lakebase project/branch.

        Returns the host, port, database, and temporary credentials.
        Specify branch_name and compute_type to target a specific endpoint:
        - primary: read-write (default)
        - replica: read-only (lower latency for analytics)

        Credentials are short-lived and scoped to the current user's UC permissions."""
        try:
            auth = LakebaseAuth()
            creds = await auth.get_lakebase_credentials(params.project_name)
            conn_str = (
                f"postgresql://{creds['user']}:{creds['password']}"
                f"@{creds['host']}:{creds['port']}/{creds['database']}"
            )
            return json.dumps(
                {
                    "connection_string": conn_str,
                    "host": creds["host"],
                    "port": creds["port"],
                    "database": creds["database"],
                    "user": creds["user"],
                    "branch": params.branch_name,
                    "compute_type": params.compute_type,
                    "note": "Credentials are temporary and scoped to your Unity Catalog permissions.",
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)
