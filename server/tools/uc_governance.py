"""Unity Catalog governance tools — permissions, grants, roles for Lakebase objects.

Surfaces UC permissions and roles so AI agents can understand what they're
allowed to do before attempting operations.
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.config import config
from server.utils.errors import handle_error


class GetPermissionsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    securable_type: str = Field(
        default="SCHEMA",
        description="Type of object: CATALOG, SCHEMA, TABLE, VOLUME, FUNCTION, CONNECTION",
    )
    full_name: str = Field(
        ...,
        description="Fully qualified object name (e.g., 'catalog.schema' or 'catalog.schema.table')",
    )
    principal: Optional[str] = Field(
        default=None,
        description="Filter by principal (email, group name, or SP ID). If None, shows all grants.",
    )


class CheckMyAccessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    catalog: str = Field(
        ..., description="Catalog name to check permissions on"
    )
    schema_name: Optional[str] = Field(
        default=None, description="Schema name (optional, for schema-level check)"
    )
    table_name: Optional[str] = Field(
        default=None, description="Table name (optional, for table-level check)"
    )


class GovernanceSummaryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    catalog: Optional[str] = Field(
        default=None,
        description="Catalog to summarize. If None, uses LAKEBASE_CATALOG env var.",
    )


class ListCatalogGrantsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    catalog: str = Field(
        ..., description="Catalog name to list all grants for"
    )
    include_schemas: bool = Field(
        default=True,
        description="Also list grants on schemas within the catalog",
    )


def register_uc_governance_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_get_uc_permissions",
        annotations={
            "title": "Get Unity Catalog Permissions",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_get_uc_permissions(params: GetPermissionsInput) -> str:
        """Get Unity Catalog effective permissions on a Lakebase object.

        Shows both direct and inherited (from parent catalog/schema) grants.
        Helps agents understand what operations are permitted before attempting them.

        Returns: principal, privilege list, and inheritance source for each grant.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client

            grants = ws.grants.get_effective(
                securable_type=params.securable_type,
                full_name=params.full_name,
                principal=params.principal,
            )

            if not grants.privilege_assignments:
                return (
                    f"No permissions found on {params.securable_type} "
                    f"'{params.full_name}'"
                    + (f" for principal '{params.principal}'" if params.principal else "")
                    + ". The object may not exist or you may lack MANAGE permissions."
                )

            lines = [
                f"## UC Permissions: {params.securable_type} `{params.full_name}`\n"
            ]

            for assignment in grants.privilege_assignments:
                principal = assignment.principal
                lines.append(f"### Principal: `{principal}`\n")
                lines.append("| Privilege | Inherited From | Source Type |")
                lines.append("|-----------|---------------|-------------|")

                for priv in assignment.privileges:
                    inherited = priv.inherited_from_name or "*(direct grant)*"
                    source = priv.inherited_from_type or "DIRECT"
                    lines.append(
                        f"| {priv.privilege} | {inherited} | {source} |"
                    )
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_check_my_access",
        annotations={
            "title": "Check My Access to Lakebase Object",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_check_my_access(params: CheckMyAccessInput) -> str:
        """Check the current user's effective permissions on a Lakebase catalog/schema/table.

        Use this before executing queries to understand what you're allowed to do.
        Shows: SELECT, INSERT, UPDATE, DELETE, CREATE, MODIFY, and other privileges.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client

            # Get current user identity
            try:
                me = ws.current_user.me()
                user_email = me.user_name
            except Exception:
                user_email = None

            # Determine target and securable type
            if params.table_name:
                full_name = f"{params.catalog}.{params.schema_name}.{params.table_name}"
                sec_type = "TABLE"
            elif params.schema_name:
                full_name = f"{params.catalog}.{params.schema_name}"
                sec_type = "SCHEMA"
            else:
                full_name = params.catalog
                sec_type = "CATALOG"

            grants = ws.grants.get_effective(
                securable_type=sec_type,
                full_name=full_name,
                principal=user_email,
            )

            if not grants.privilege_assignments:
                return (
                    f"You ({user_email or 'current user'}) have **no permissions** "
                    f"on {sec_type} `{full_name}`.\n\n"
                    f"Ask a catalog admin to grant access:\n"
                    f"```sql\nGRANT SELECT ON {sec_type} `{full_name}` TO `{user_email}`;\n```"
                )

            lines = [
                f"## Your Access: {sec_type} `{full_name}`",
                f"**User**: `{user_email or 'current user'}`\n",
            ]

            all_privileges = []
            for assignment in grants.privilege_assignments:
                for priv in assignment.privileges:
                    inherited = priv.inherited_from_name
                    source = f" *(inherited from {priv.inherited_from_type} `{inherited}`)*" if inherited else ""
                    all_privileges.append(f"- **{priv.privilege}**{source}")

            lines.append("### Effective Privileges\n")
            lines.extend(all_privileges)

            # Summary line mapping to governance
            priv_names = {p.privilege for a in grants.privilege_assignments for p in a.privileges}
            can_read = "SELECT" in priv_names or "ALL_PRIVILEGES" in priv_names
            can_write = "MODIFY" in priv_names or "ALL_PRIVILEGES" in priv_names
            can_create = "CREATE_TABLE" in priv_names or "ALL_PRIVILEGES" in priv_names

            lines.append(f"\n### Summary")
            lines.append(f"- Can read (SELECT): {'Yes' if can_read else 'No'}")
            lines.append(f"- Can write (MODIFY): {'Yes' if can_write else 'No'}")
            lines.append(f"- Can create objects: {'Yes' if can_create else 'No'}")

            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_governance_summary",
        annotations={
            "title": "Governance Summary",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_governance_summary(params: GovernanceSummaryInput) -> str:
        """Get a combined governance summary: MCP tool governance + UC permissions.

        Shows the current agent's effective access including:
        - MCP governance profile (SQL statement types allowed)
        - MCP tool access restrictions
        - UC permissions on the Lakebase catalog
        - Recommended profile based on UC permissions

        Use this tool first to understand what you can and cannot do.
        """
        try:
            from server.governance.policy import build_governance_policy
            from server.governance.sql_guard import SQLStatementType

            policy = build_governance_policy()

            lines = ["## Lakebase Governance Summary\n"]

            # Part 1: MCP SQL Governance
            sql_types = sorted(t.value for t in policy.sql_governor.allowed_types)
            lines.append("### SQL Statement Governance")
            lines.append(f"**Allowed types** ({len(sql_types)}): {', '.join(sql_types)}\n")

            all_types = sorted(t.value for t in SQLStatementType)
            denied_types = sorted(set(all_types) - set(sql_types))
            if denied_types:
                lines.append(f"**Denied types**: {', '.join(denied_types)}\n")

            # Part 2: MCP Tool Governance
            lines.append("### Tool Access Governance")
            if policy.tool_policy.allowed_tools:
                lines.append(
                    f"**Allowed tools** ({len(policy.tool_policy.allowed_tools)}): "
                    f"{', '.join(sorted(policy.tool_policy.allowed_tools))}\n"
                )
            else:
                lines.append("**Tool restrictions**: None (all tools accessible)\n")

            if policy.tool_policy.denied_tools:
                lines.append(
                    f"**Denied tools**: {', '.join(sorted(policy.tool_policy.denied_tools))}\n"
                )

            # Part 3: UC Permissions (if catalog configured)
            catalog = params.catalog or config.lakebase_catalog
            if catalog:
                lines.append(f"### Unity Catalog Permissions: `{catalog}`")
                try:
                    auth = LakebaseAuth()
                    ws = auth.workspace_client

                    try:
                        me = ws.current_user.me()
                        user_email = me.user_name
                        lines.append(f"**User**: `{user_email}`\n")
                    except Exception:
                        user_email = None
                        lines.append("**User**: *(could not determine)*\n")

                    grants = ws.grants.get_effective(
                        securable_type="CATALOG",
                        full_name=catalog,
                        principal=user_email,
                    )

                    if grants.privilege_assignments:
                        priv_names = set()
                        for a in grants.privilege_assignments:
                            for p in a.privileges:
                                priv_names.add(p.privilege)

                        lines.append(
                            f"**Catalog privileges**: {', '.join(sorted(priv_names))}\n"
                        )

                        # Recommendation
                        if "ALL_PRIVILEGES" in priv_names:
                            rec = "admin"
                        elif "MODIFY" in priv_names or "CREATE_TABLE" in priv_names:
                            rec = "developer"
                        elif "SELECT" in priv_names:
                            rec = "read_only or analyst"
                        else:
                            rec = "read_only"

                        lines.append(
                            f"**Recommended MCP profile**: `{rec}` "
                            f"(based on your UC privileges)"
                        )
                    else:
                        lines.append(
                            f"No UC grants found on catalog `{catalog}`. "
                            f"You may need admin to grant USE_CATALOG."
                        )
                except Exception as e:
                    lines.append(
                        f"*Could not check UC permissions "
                        f"(Databricks SDK may not be configured): {e}*"
                    )
            else:
                lines.append(
                    "### Unity Catalog Permissions\n"
                    "*No catalog configured (set LAKEBASE_CATALOG env var)*"
                )

            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_list_catalog_grants",
        annotations={
            "title": "List Catalog Grants",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_list_catalog_grants(params: ListCatalogGrantsInput) -> str:
        """List all grants on a Lakebase catalog and optionally its schemas.

        Shows which principals have access and what privileges they hold.
        Useful for auditing access control before granting MCP access to agents.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client

            lines = [f"## Grants on Catalog `{params.catalog}`\n"]

            # Catalog-level grants
            try:
                cat_grants = ws.grants.get(
                    securable_type="CATALOG",
                    full_name=params.catalog,
                )

                if cat_grants.privilege_assignments:
                    lines.append("### Catalog-Level Grants\n")
                    lines.append("| Principal | Privileges |")
                    lines.append("|-----------|-----------|")
                    for a in cat_grants.privilege_assignments:
                        privs = ", ".join(p.privilege for p in a.privileges)
                        lines.append(f"| `{a.principal}` | {privs} |")
                    lines.append("")
                else:
                    lines.append("No direct grants on catalog.\n")
            except Exception as e:
                lines.append(f"Could not read catalog grants: {e}\n")

            # Schema-level grants
            if params.include_schemas:
                try:
                    schemas = list(ws.schemas.list(catalog_name=params.catalog))
                    for schema in schemas:
                        schema_name = f"{params.catalog}.{schema.name}"
                        try:
                            schema_grants = ws.grants.get(
                                securable_type="SCHEMA",
                                full_name=schema_name,
                            )
                            if schema_grants.privilege_assignments:
                                lines.append(f"### Schema: `{schema_name}`\n")
                                lines.append("| Principal | Privileges |")
                                lines.append("|-----------|-----------|")
                                for a in schema_grants.privilege_assignments:
                                    privs = ", ".join(
                                        p.privilege for p in a.privileges
                                    )
                                    lines.append(
                                        f"| `{a.principal}` | {privs} |"
                                    )
                                lines.append("")
                        except Exception:
                            pass  # Skip schemas we can't access
                except Exception as e:
                    lines.append(f"Could not list schemas: {e}\n")

            return "\n".join(lines)
        except Exception as e:
            return handle_error(e)
