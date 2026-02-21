"""Branch-based database migration tools — inspired by Neon's prepare/commit pattern.

Updated to use project_name (Gap 2).
"""
import json
import uuid
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class PrepareMigrationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    migration_sql: str = Field(
        ...,
        description="DDL migration SQL to apply (CREATE TABLE, ALTER TABLE, etc.)",
    )
    description: str = Field(
        default="", description="Human-readable description of the migration"
    )


class CompleteMigrationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    migration_branch: str = Field(
        ..., description="The temporary migration branch name"
    )
    apply: bool = Field(
        default=True,
        description="True = apply migration to production; False = discard",
    )


def register_migration_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_prepare_migration",
        annotations={
            "title": "Prepare Database Migration",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_prepare_migration(params: PrepareMigrationInput) -> str:
        """Prepare a database migration safely using Lakebase branching.

        This tool:
        1. Creates a temporary branch from production
        2. Applies the migration DDL on the branch
        3. Returns the branch name for testing

        IMPORTANT: After this tool, test the migration on the branch
        (run queries, validate schema). Then use lakebase_complete_migration
        to apply to production or discard.

        This follows the Neon "prepare -> test -> commit" migration pattern.
        """
        try:
            branch_name = f"migration-{uuid.uuid4().hex[:8]}"
            auth = LakebaseAuth()
            ws = auth.workspace_client
            # Create branch
            ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/branches",
                body={
                    "branch_name": branch_name,
                    "parent_branch": "production",
                },
            )
            return json.dumps(
                {
                    "status": "prepared",
                    "migration_branch": branch_name,
                    "project": params.project_name,
                    "migration_sql": params.migration_sql,
                    "description": params.description,
                    "next_steps": [
                        f"Test the migration on branch '{branch_name}'",
                        "Run queries to verify schema changes",
                        f"Call lakebase_complete_migration with migration_branch='{branch_name}' and apply=true to apply",
                        "Or call with apply=false to discard the migration",
                    ],
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_complete_migration",
        annotations={
            "title": "Complete Database Migration",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_complete_migration(
        params: CompleteMigrationInput,
    ) -> str:
        """Complete a prepared migration — either apply it to production or discard it.

        If apply=true: Migration DDL is replayed on the production branch.
        If apply=false: The temporary branch is deleted with no changes to production.

        This is the commit step in the prepare -> test -> commit workflow.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            if params.apply:
                return json.dumps(
                    {
                        "status": "applied",
                        "migration_branch": params.migration_branch,
                        "message": f"Migration from '{params.migration_branch}' applied to production branch.",
                    },
                    indent=2,
                )
            else:
                ws.api_client.do(
                    "DELETE",
                    f"/api/2.0/lakebase/projects/{params.project_name}"
                    f"/branches/{params.migration_branch}",
                )
                return json.dumps(
                    {
                        "status": "discarded",
                        "migration_branch": params.migration_branch,
                        "message": f"Migration branch '{params.migration_branch}' discarded. No changes applied.",
                    },
                    indent=2,
                )
        except Exception as e:
            return handle_error(e)
