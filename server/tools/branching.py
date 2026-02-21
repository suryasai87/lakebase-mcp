"""Lakebase branching tools — leveraging Neon's copy-on-write architecture.

Merged: base branching + Gap 2 (project_name hierarchy).
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class CreateBranchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(
        ..., description="Lakebase project name to branch from"
    )
    branch_name: str = Field(
        ...,
        description="Name for the new branch (e.g., 'feature-user-auth', 'migration-v2')",
    )
    parent_branch: Optional[str] = Field(
        default=None,
        description="Parent branch to fork from. Defaults to production.",
    )


class ListBranchesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class DeleteBranchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(
        ..., description="Branch to delete (cannot delete production)"
    )


def register_branching_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_create_branch",
        annotations={
            "title": "Create Database Branch",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_branch(params: CreateBranchInput) -> str:
        """Create a copy-on-write branch of a Lakebase project.

        Branches are instant, cost-effective clones — they share the same underlying
        data until writes diverge. Each branch gets its own compute (with autoscaling).
        Perfect for:
        - Feature development (branch per git branch)
        - Safe schema migrations (test on branch before merging)
        - Data experiments and A/B testing
        - Agent sandbox environments
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/branches",
                body={
                    "branch_name": params.branch_name,
                    "parent_branch": params.parent_branch or "production",
                },
            )
            return json.dumps(
                {
                    "status": "created",
                    "branch": params.branch_name,
                    "project": params.project_name,
                    "parent": params.parent_branch or "production",
                    "message": (
                        f"Branch '{params.branch_name}' created with its own compute. "
                        f"Use lakebase_get_connection_string to connect."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_branches",
        annotations={
            "title": "List Database Branches",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_branches(params: ListBranchesInput) -> str:
        """List all branches of a Lakebase project. Shows branch name, creation time,
        parent branch, compute status (active/suspended/scaling), and CU allocation."""
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/branches",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_delete_branch",
        annotations={
            "title": "Delete Database Branch",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_delete_branch(params: DeleteBranchInput) -> str:
        """Delete a Lakebase database branch. This is irreversible.
        The 'production' branch cannot be deleted."""
        try:
            if params.branch_name.lower() in ("production", "main"):
                return "Error: Cannot delete the production/main branch."
            auth = LakebaseAuth()
            ws = auth.workspace_client
            ws.api_client.do(
                "DELETE",
                f"/api/2.0/lakebase/projects/{params.project_name}/branches/{params.branch_name}",
            )
            return f"Branch '{params.branch_name}' deleted from project '{params.project_name}'."
        except Exception as e:
            return handle_error(e)
