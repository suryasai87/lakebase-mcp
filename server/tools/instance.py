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
    redact: bool = Field(
        default=True,
        description="Redact password in output (default: True). Set False to see full credentials.",
    )


class RotateCredentialsInput(BaseModel):
    """Rotate database credentials for a Lakebase project."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class ListCredentialsInput(BaseModel):
    """List credential grants for a Lakebase project."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class CreateProjectInput(BaseModel):
    """Create a new Lakebase project."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Name for the new Lakebase project")
    catalog_name: str = Field(..., description="Unity Catalog catalog name to associate with the project")


class DeleteProjectInput(BaseModel):
    """Delete a Lakebase project."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name to delete")
    confirm: bool = Field(
        default=False,
        description="Safety confirmation. Must be set to True to proceed with deletion.",
    )


class GetOperationStatusInput(BaseModel):
    """Poll the status of a long-running Lakebase operation."""

    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    operation_id: str = Field(
        ...,
        description=(
            "Operation ID returned by async tools (e.g., create_branch, "
            "create_pitr_branch, create_read_replica, restart_compute)."
        ),
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

        By default, passwords are redacted for security. Set redact=False to
        retrieve the full connection string (a security warning will be included).

        Credentials are short-lived and scoped to the current user's UC permissions."""
        try:
            auth = LakebaseAuth()
            creds = await auth.get_lakebase_credentials(params.project_name)

            password_raw = creds["password"]
            if params.redact:
                # Show only last 4 chars of the password
                if len(password_raw) > 4:
                    password_display = "****" + password_raw[-4:]
                else:
                    password_display = "****"
            else:
                password_display = password_raw

            conn_str = (
                f"postgresql://{creds['user']}:{password_display}"
                f"@{creds['host']}:{creds['port']}/{creds['database']}"
            )

            result = {
                "connection_string": conn_str,
                "host": creds["host"],
                "port": creds["port"],
                "database": creds["database"],
                "user": creds["user"],
                "branch": params.branch_name,
                "compute_type": params.compute_type,
                "note": "Credentials are temporary and scoped to your Unity Catalog permissions.",
            }

            if not params.redact:
                result["warning"] = (
                    "Credentials are returned in PLAINTEXT. "
                    "Do not log or share this output. "
                    "Consider using redact=True (default) for safer handling."
                )

            return json.dumps(result, indent=2)
        except Exception as e:
            return handle_error(e)

    # --- GAP-6: Credential management tools ---

    @mcp.tool(
        name="lakebase_rotate_credentials",
        annotations={
            "title": "Rotate Lakebase Credentials",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_rotate_credentials(params: RotateCredentialsInput) -> str:
        """Rotate database credentials for a Lakebase project.

        Generates new credentials and invalidates old ones.
        Existing connections using old credentials will need to reconnect."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/credentials/rotate",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_credentials",
        annotations={
            "title": "List Lakebase Credentials",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_credentials(params: ListCredentialsInput) -> str:
        """List credential grants for a Lakebase project.

        Shows which principals have credential access to the project."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/credentials",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    # --- GAP-11: Project-level CRUD ---

    @mcp.tool(
        name="lakebase_create_project",
        annotations={
            "title": "Create Lakebase Project",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_project(params: CreateProjectInput) -> str:
        """Create a new Lakebase project.

        Provisions a new Lakebase project associated with the specified Unity Catalog catalog.
        The project will be created with a default 'production' branch."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "POST",
                "/api/2.0/lakebase/projects",
                body={
                    "project_name": params.project_name,
                    "catalog_name": params.catalog_name,
                },
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_delete_project",
        annotations={
            "title": "Delete Lakebase Project",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_delete_project(params: DeleteProjectInput) -> str:
        """Delete a Lakebase project.

        THIS IS A DESTRUCTIVE OPERATION. All branches, computes, and data
        associated with the project will be permanently deleted.

        Requires confirm=True as a safety check. Without it, the request is rejected."""
        try:
            if not params.confirm:
                return json.dumps(
                    {
                        "error": "Safety check failed. Set confirm=True to proceed with deletion.",
                        "project_name": params.project_name,
                        "hint": "This will permanently delete the project and all associated data.",
                    },
                    indent=2,
                )
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "DELETE",
                f"/api/2.0/lakebase/projects/{params.project_name}",
            )
            return json.dumps(
                result if result else {"status": "deleted", "project_name": params.project_name},
                indent=2,
                default=str,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_get_operation_status",
        annotations={
            "title": "Get Operation Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_get_operation_status(params: GetOperationStatusInput) -> str:
        """Poll a long-running Lakebase operation by its ID.

        Branch creation, PITR restore, read-replica creation, and compute restarts
        all return asynchronously via an `operation_id`. Use this tool to check
        whether the operation is still running, completed, or failed — and to get
        the resulting resource name (e.g., the new branch/compute) when ready.

        Typical states: PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/operations/{params.operation_id}",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
