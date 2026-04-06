"""Branch-based database migration tools — inspired by Neon's prepare/commit pattern.

Updated to use project_name (Gap 2).
Fixed Gap 3: actually execute migration DDL on branch and replay on production.
"""
import json
import logging
import uuid
import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error
from server.governance.policy import GovernancePolicy

logger = logging.getLogger(__name__)


async def _execute_ddl_on_branch(
    auth: LakebaseAuth, project_name: str, branch_name: str, migration_sql: str
) -> dict:
    """Connect to a specific Lakebase branch and execute DDL.

    Uses credential vending scoped to the project, then connects to the
    branch-specific compute endpoint and runs the migration SQL.

    Returns a dict with execution details (rows affected, etc.).
    """
    # Get credentials for the project (credential vending handles branch routing)
    creds = await auth.get_lakebase_credentials(project_name)

    # Build connection string targeting the specific branch.
    # Lakebase routes to the correct branch compute via the
    # 'options' connection parameter (same pattern as Neon).
    conninfo = (
        f"host={creds['host']} port={creds['port']} "
        f"dbname={creds['database']} user={creds['user']} "
        f"password={creds['password']}"
    )

    async with await psycopg.AsyncConnection.connect(
        conninfo,
        autocommit=True,
        row_factory=dict_row,
        options=f"-c lakebase.branch={branch_name}",
    ) as conn:
        async with conn.cursor() as cur:
            # Execute the DDL — may contain multiple statements separated by ';'
            await cur.execute(migration_sql)
            affected = cur.rowcount if cur.rowcount and cur.rowcount >= 0 else 0
            logger.info(
                "Executed migration DDL on branch '%s' (project '%s'): %d rows affected",
                branch_name,
                project_name,
                affected,
            )
            return {"rows_affected": affected}


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
    migration_sql: str = Field(
        ...,
        description="The DDL migration SQL to replay on production (same SQL used in prepare step)",
    )
    apply: bool = Field(
        default=True,
        description="True = apply migration to production; False = discard",
    )


def register_migration_tools(mcp: FastMCP, governance: GovernancePolicy = None):

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
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_prepare_migration")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            branch_name = f"migration-{uuid.uuid4().hex[:8]}"
            auth = LakebaseAuth()
            ws = auth.workspace_client

            # Step 1: Create branch from production
            ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}/branches",
                body={
                    "branch_name": branch_name,
                    "parent_branch": "production",
                },
            )
            logger.info(
                "Created migration branch '%s' for project '%s'",
                branch_name,
                params.project_name,
            )

            # Step 2: Execute migration DDL on the new branch
            ddl_result = await _execute_ddl_on_branch(
                auth, params.project_name, branch_name, params.migration_sql
            )

            return json.dumps(
                {
                    "status": "prepared",
                    "migration_branch": branch_name,
                    "project": params.project_name,
                    "migration_sql": params.migration_sql,
                    "ddl_executed": True,
                    "ddl_result": ddl_result,
                    "description": params.description,
                    "next_steps": [
                        f"Test the migration on branch '{branch_name}'",
                        "Run queries to verify schema changes",
                        f"Call lakebase_complete_migration with migration_branch='{branch_name}', "
                        f"migration_sql='<same DDL>', and apply=true to apply",
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

        If apply=true: Migration DDL is replayed on the production branch,
        then the temporary migration branch is deleted.
        If apply=false: The temporary branch is deleted with no changes to production.

        This is the commit step in the prepare -> test -> commit workflow.
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_complete_migration")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client

            if params.apply:
                # Step 1: Replay the DDL on the production branch
                ddl_result = await _execute_ddl_on_branch(
                    auth, params.project_name, "production", params.migration_sql
                )
                logger.info(
                    "Replayed migration DDL on production for project '%s'",
                    params.project_name,
                )

                # Step 2: Clean up — delete the migration branch
                try:
                    ws.api_client.do(
                        "DELETE",
                        f"/api/2.0/lakebase/projects/{params.project_name}"
                        f"/branches/{params.migration_branch}",
                    )
                    branch_deleted = True
                    logger.info(
                        "Deleted migration branch '%s' after successful apply",
                        params.migration_branch,
                    )
                except Exception as cleanup_err:
                    branch_deleted = False
                    logger.warning(
                        "Migration applied successfully but failed to delete branch '%s': %s",
                        params.migration_branch,
                        cleanup_err,
                    )

                return json.dumps(
                    {
                        "status": "applied",
                        "migration_branch": params.migration_branch,
                        "ddl_executed": True,
                        "ddl_result": ddl_result,
                        "branch_deleted": branch_deleted,
                        "message": (
                            f"Migration from '{params.migration_branch}' applied to production branch. "
                            f"{'Migration branch deleted.' if branch_deleted else 'Migration branch still exists — delete manually.'}"
                        ),
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
