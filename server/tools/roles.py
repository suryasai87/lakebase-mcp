"""Lakebase Postgres role management and Data API access setup.

Manages OAuth-linked Postgres roles for users, service principals, and groups,
and configures the authenticator role grants required for Data API access.

Ref: https://docs.databricks.com/aws/en/oltp/projects/authentication
     https://docs.databricks.com/aws/en/oltp/projects/data-api
"""

import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.db import pool
from server.utils.errors import handle_error
from server.governance.policy import GovernancePolicy


class CreateDBRoleInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    identity_name: str = Field(
        ...,
        description=(
            "Databricks identity: email for USER, application UUID for SERVICE_PRINCIPAL, "
            "or display name for GROUP"
        ),
    )
    identity_type: Literal["USER", "SERVICE_PRINCIPAL", "GROUP"] = Field(
        ...,
        description="Identity type: USER, SERVICE_PRINCIPAL, or GROUP",
    )


class SetupDataAPIAccessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    identity_name: str = Field(
        ...,
        description="Databricks identity (email, SP UUID, or group name) to grant access",
    )
    schema_name: str = Field(
        default="public",
        description="Schema to grant access on (default: public)",
    )
    privileges: list[str] = Field(
        default=["SELECT"],
        description=(
            "Privileges to grant: SELECT, INSERT, UPDATE, DELETE. "
            "Use ['SELECT'] for read-only access."
        ),
    )
    grant_sequences: bool = Field(
        default=True,
        description="Also grant USAGE on all sequences in the schema",
    )
    grant_functions: bool = Field(
        default=False,
        description="Also grant EXECUTE on all functions in the schema (for RPC)",
    )


class GenerateCredentialInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(
        default="production", description="Branch name"
    )
    endpoint_name: str = Field(
        default="primary",
        description="Endpoint name (primary, or a read replica name)",
    )
    redact: bool = Field(
        default=True,
        description="Redact token in output (default: True). Set False for full token.",
    )


class ListDBRolesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    include_system: bool = Field(
        default=False,
        description="Include Databricks system roles (databricks_*, cloud_admin, etc.)",
    )


def register_role_tools(mcp: FastMCP, governance: GovernancePolicy = None):

    @mcp.tool(
        name="lakebase_create_db_role",
        annotations={
            "title": "Create Postgres Role",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_db_role(params: CreateDBRoleInput) -> str:
        """Create an OAuth-linked Postgres role for a Databricks identity.

        Uses the databricks_auth extension to create a role that maps
        a Databricks identity (user, service principal, or group) to a
        Postgres role. The role gets LOGIN but no privileges — grant those
        separately.

        Prerequisites:
        - CREATE and CREATE ROLE permissions on the database
        - Must be authenticated with an OAuth token (not native Postgres)
        - databricks_auth extension must be installed

        Service principal IDs: found under Settings > Identity and access >
        Service principals (use the application UUID, not the display name).

        Group names are case-sensitive and must match the workspace exactly.
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_create_db_role")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            await pool.execute_query(
                "CREATE EXTENSION IF NOT EXISTS databricks_auth",
                tool_name="lakebase_create_db_role",
            )
            await pool.execute_query(
                "SELECT databricks_create_role(%s, %s)",
                (params.identity_name, params.identity_type),
                tool_name="lakebase_create_db_role",
            )
            return json.dumps(
                {
                    "status": "created",
                    "identity_name": params.identity_name,
                    "identity_type": params.identity_type,
                    "message": (
                        f"Postgres role created for {params.identity_type} "
                        f"'{params.identity_name}'. The role has LOGIN but no privileges. "
                        "Use lakebase_setup_data_api_access to grant permissions."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_setup_data_api_access",
        annotations={
            "title": "Setup Data API Access",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_setup_data_api_access(
        params: SetupDataAPIAccessInput,
    ) -> str:
        """Grant a Databricks identity the permissions needed for Data API access.

        The Data API requires:
        1. The identity's Postgres role is GRANTED to authenticator
        2. The role has USAGE on the target schema
        3. The role has specific table privileges (SELECT, INSERT, etc.)
        4. Optionally: USAGE on sequences (for serial columns) and EXECUTE on functions (for RPC)

        WARNING: Do not grant the project owner role to authenticator. Use a
        service principal or non-owner user. Roles created via the UI (not
        databricks_create_role) cannot be granted to authenticator.

        Steps this tool executes:
        1. GRANT "{identity}" TO authenticator
        2. GRANT USAGE ON SCHEMA {schema} TO "{identity}"
        3. GRANT {privileges} ON ALL TABLES IN SCHEMA {schema} TO "{identity}"
        4. (optional) GRANT USAGE ON ALL SEQUENCES
        5. (optional) GRANT EXECUTE ON ALL FUNCTIONS
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_setup_data_api_access")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            identity = params.identity_name
            schema = params.schema_name
            grants_executed = []

            await pool.execute_query(
                f'GRANT "{identity}" TO authenticator',
                tool_name="lakebase_setup_data_api_access",
            )
            grants_executed.append(f'GRANT "{identity}" TO authenticator')

            await pool.execute_query(
                f'GRANT USAGE ON SCHEMA {schema} TO "{identity}"',
                tool_name="lakebase_setup_data_api_access",
            )
            grants_executed.append(f'GRANT USAGE ON SCHEMA {schema} TO "{identity}"')

            privs = ", ".join(params.privileges)
            await pool.execute_query(
                f'GRANT {privs} ON ALL TABLES IN SCHEMA {schema} TO "{identity}"',
                tool_name="lakebase_setup_data_api_access",
            )
            grants_executed.append(
                f'GRANT {privs} ON ALL TABLES IN SCHEMA {schema} TO "{identity}"'
            )

            if params.grant_sequences:
                await pool.execute_query(
                    f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO "{identity}"',
                    tool_name="lakebase_setup_data_api_access",
                )
                grants_executed.append(
                    f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO "{identity}"'
                )

            if params.grant_functions:
                await pool.execute_query(
                    f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {schema} TO "{identity}"',
                    tool_name="lakebase_setup_data_api_access",
                )
                grants_executed.append(
                    f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {schema} TO "{identity}"'
                )

            return json.dumps(
                {
                    "status": "configured",
                    "identity": identity,
                    "schema": schema,
                    "privileges": params.privileges,
                    "grants_executed": grants_executed,
                    "message": (
                        f"Data API access configured for '{identity}' on schema '{schema}'. "
                        f"The identity can now use the REST Data API with Databricks OAuth tokens."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            error_str = str(e)
            if "42501" in error_str and "permission denied to grant role" in error_str.lower():
                return (
                    f"Error: Cannot grant role '{params.identity_name}' to authenticator. "
                    "This happens when:\n"
                    "- The role was created via the UI instead of databricks_create_role\n"
                    "- The target is the project owner role\n"
                    "Fix: use lakebase_create_db_role to create the role via SQL, then retry."
                )
            return handle_error(e)

    @mcp.tool(
        name="lakebase_generate_credential",
        annotations={
            "title": "Generate Database Credential",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_generate_credential(
        params: GenerateCredentialInput,
    ) -> str:
        """Generate a short-lived OAuth database credential for a Lakebase endpoint.

        Returns a temporary token (1-hour expiry) that can be used as the
        PostgreSQL password for direct wire protocol or Data API access.

        The token is scoped to the requesting user's Databricks identity.
        Token expiry is checked only at login; open connections stay alive.

        Use for:
        - Connecting external tools (DBeaver, pgAdmin, Postman) to Lakebase
        - Programmatic access from scripts or CI/CD
        - Testing Data API access with curl

        By default, the token is redacted for safety. Set redact=False for the full token.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            endpoint_path = (
                f"projects/{params.project_name}/branches/{params.branch_name}"
                f"/endpoints/{params.endpoint_name}"
            )
            result = ws.api_client.do(
                "POST",
                "/api/2.0/postgres/generate-database-credential",
                body={"endpoint": endpoint_path},
            )
            token = result.get("token", "")
            expire_time = result.get("expire_time", "")

            if params.redact and len(token) > 8:
                token_display = token[:4] + "..." + token[-4:]
            elif params.redact:
                token_display = "****"
            else:
                token_display = token

            output = {
                "token": token_display,
                "expire_time": expire_time,
                "endpoint": endpoint_path,
                "usage": (
                    "Use the token as the PostgreSQL password with your Databricks "
                    "identity (email) as the username, or as the Bearer token for "
                    "Data API requests."
                ),
            }

            if not params.redact:
                output["warning"] = (
                    "Token is returned in PLAINTEXT. Do not log or share this output. "
                    "Token expires in ~1 hour."
                )

            return json.dumps(output, indent=2)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_db_roles",
        annotations={
            "title": "List Database Roles",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_db_roles(params: ListDBRolesInput) -> str:
        """List all Postgres roles in the Lakebase database.

        Shows role name, login capability, and membership in other roles.
        By default excludes Databricks system roles (databricks_*, cloud_admin).
        Set include_system=True to see all roles.
        """
        try:
            where = ""
            if not params.include_system:
                where = (
                    "WHERE r.rolname NOT LIKE 'databricks_%' "
                    "AND r.rolname NOT LIKE 'cloud_%' "
                    "AND r.rolname NOT LIKE 'pg_%' "
                    "AND r.rolname NOT IN ('authenticator', 'anon')"
                )
            sql = f"""
                SELECT
                    r.rolname AS role_name,
                    r.rolcanlogin AS can_login,
                    r.rolcreatedb AS can_create_db,
                    r.rolcreaterole AS can_create_role,
                    COALESCE(
                        array_agg(m.rolname ORDER BY m.rolname)
                        FILTER (WHERE m.rolname IS NOT NULL),
                        ARRAY[]::text[]
                    ) AS member_of
                FROM pg_roles r
                LEFT JOIN pg_auth_members am ON am.member = r.oid
                LEFT JOIN pg_roles m ON m.oid = am.roleid
                {where}
                GROUP BY r.rolname, r.rolcanlogin, r.rolcreatedb, r.rolcreaterole
                ORDER BY r.rolname
            """
            rows = await pool.execute_readonly(
                sql, tool_name="lakebase_list_db_roles"
            )
            return json.dumps(rows, indent=2, default=str)
        except Exception as e:
            return handle_error(e)
