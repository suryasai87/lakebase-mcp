"""Lakebase Data API tools — REST-based CRUD via the PostgREST interface.

The Data API provides a RESTful interface to Lakebase tables, authenticated
with Databricks OAuth tokens. It supports filtering (eq, gte, lte, neq,
like, in), sorting, pagination, column selection, and resource embedding.

Ref: https://docs.databricks.com/aws/en/oltp/projects/data-api
"""

import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.config import config
from server.data_api_client import LakebaseDataAPIClient, DataAPIError
from server.governance.policy import GovernancePolicy


class DataAPIGetInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    table: str = Field(
        ...,
        description="Table name to query (e.g., 'clients', 'projects')",
    )
    schema_name: str = Field(
        default="public",
        description="Schema name (default: public). Must be in the Data API's exposed schemas.",
    )
    filters: Optional[dict[str, str]] = Field(
        default=None,
        description=(
            "PostgREST filter expressions as key-value pairs. "
            "Keys are column names, values use operator syntax: "
            "eq.value, gte.5, lte.100, neq.draft, like.*foo*, in.(a,b,c). "
            "Example: {'status': 'eq.active', 'priority': 'gte.3'}"
        ),
    )
    select: Optional[str] = Field(
        default=None,
        description=(
            "Columns to return, comma-separated. Supports resource embedding: "
            "'id,name,projects(id,name)' embeds related projects."
        ),
    )
    order: Optional[str] = Field(
        default=None,
        description="Sort order: 'column.asc' or 'column.desc' (e.g., 'created_at.desc')",
    )
    limit: Optional[int] = Field(
        default=None, description="Maximum rows to return", ge=1, le=10000
    )
    offset: Optional[int] = Field(
        default=None, description="Number of rows to skip (for pagination)", ge=0
    )
    use_replica: bool = Field(
        default=False,
        description="Route to read replica endpoint for lower latency reads",
    )


class DataAPIInsertInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    table: str = Field(..., description="Table name to insert into")
    schema_name: str = Field(default="public", description="Schema name")
    rows: list[dict[str, Any]] = Field(
        ...,
        description="Rows to insert as a list of dicts. Example: [{'name': 'Alice', 'email': 'alice@co.com'}]",
        min_length=1,
        max_length=1000,
    )


class DataAPIUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    table: str = Field(..., description="Table name to update")
    schema_name: str = Field(default="public", description="Schema name")
    filters: dict[str, str] = Field(
        ...,
        description=(
            "Filter to select rows to update. REQUIRED to prevent accidental full-table updates. "
            "Example: {'id': 'eq.5'}"
        ),
    )
    data: dict[str, Any] = Field(
        ...,
        description="Column values to set. Example: {'status': 'completed', 'updated_at': 'now()'}",
    )


class DataAPIDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    table: str = Field(..., description="Table name to delete from")
    schema_name: str = Field(default="public", description="Schema name")
    filters: dict[str, str] = Field(
        ...,
        description=(
            "Filter to select rows to delete. REQUIRED to prevent accidental full-table deletes. "
            "Example: {'id': 'eq.5'}"
        ),
    )


class DataAPISchemaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


class DataAPIConfigureInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    exposed_schemas: Optional[list[str]] = Field(
        default=None,
        description="Schemas to expose via Data API (default: ['public'])",
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="Maximum rows per response. Set 0 for no limit.",
        ge=0,
    )
    cors_allowed_origins: Optional[list[str]] = Field(
        default=None,
        description=(
            "Allowed CORS origins. Empty list allows all origins. "
            "List production origins for security."
        ),
    )
    openapi_enabled: Optional[bool] = Field(
        default=None,
        description="Enable /openapi.json endpoint for client generation",
    )
    server_timing_enabled: Optional[bool] = Field(
        default=None,
        description="Enable Server-Timing headers for performance debugging",
    )


class DataAPIStatusInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")


async def _get_data_api_client(
    project_name: str,
) -> LakebaseDataAPIClient:
    """Create a Data API client with a fresh OAuth token."""
    auth = LakebaseAuth()
    ws = auth.workspace_client

    project = ws.api_client.do(
        "GET", f"/api/2.0/lakebase/projects/{project_name}"
    )

    endpoint_id = project.get("primary_endpoint_id", "")
    region = project.get("region", config.data_api_region or "us-east-1")
    workspace_id = project.get("workspace_id", "")
    database = project.get("database", config.lakebase_database or "databricks_postgres")

    base_url = (
        config.data_api_base_url
        or f"https://{endpoint_id}.database.{region}.cloud.databricks.com"
           f"/api/2.0/workspace/{workspace_id}/rest/{database}"
    )

    replica_url = ""
    replica_endpoint_id = project.get("replica_endpoint_id", "")
    if replica_endpoint_id:
        replica_url = (
            f"https://{replica_endpoint_id}.database.{region}.cloud.databricks.com"
            f"/api/2.0/workspace/{workspace_id}/rest/{database}"
        )

    endpoint_path = (
        f"projects/{project_name}/branches/production/endpoints/primary"
    )
    try:
        credential = ws.api_client.do(
            "POST",
            "/api/2.0/postgres/generate-database-credential",
            body={"endpoint": endpoint_path},
        )
        token = credential.get("token", "")
    except Exception:
        token = ws.config.token

    return LakebaseDataAPIClient(base_url, token, replica_url)


def register_data_api_tools(mcp: FastMCP, governance: GovernancePolicy = None):

    @mcp.tool(
        name="lakebase_data_api_get",
        annotations={
            "title": "Data API — Query Rows",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_get(params: DataAPIGetInput) -> str:
        """Query rows from a Lakebase table via the REST Data API.

        Uses the PostgREST-based Data API for HTTP-native access without
        a PostgreSQL wire connection. Supports:
        - Filtering: eq, gte, lte, neq, like, in operators
        - Column selection and resource embedding (joins)
        - Sorting and pagination (limit/offset)
        - Read replica routing for lower latency

        Authentication uses Databricks OAuth tokens. The requesting identity
        must have a Postgres role granted to the authenticator role.

        Example filters:
          {'status': 'eq.active', 'created_at': 'gte.2024-01-01'}
          {'name': 'like.*Smith*'}
          {'category': 'in.(electronics,clothing)'}
        """
        try:
            client = await _get_data_api_client(params.project_name)
            try:
                result = await client.get(
                    params.schema_name,
                    params.table,
                    filters=params.filters,
                    select=params.select,
                    order=params.order,
                    limit=params.limit,
                    offset=params.offset,
                    use_replica=params.use_replica,
                )
                rows = result if isinstance(result, list) else [result]
                return json.dumps(
                    {"row_count": len(rows), "rows": rows},
                    indent=2,
                    default=str,
                )
            finally:
                await client.close()
        except DataAPIError as e:
            return _format_data_api_error(e)
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"

    @mcp.tool(
        name="lakebase_data_api_insert",
        annotations={
            "title": "Data API — Insert Rows",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_insert(params: DataAPIInsertInput) -> str:
        """Insert rows into a Lakebase table via the REST Data API.

        Sends a POST request to the PostgREST endpoint. Supports single or
        bulk inserts (up to 1000 rows per call).

        The requesting identity must have INSERT privileges granted on the
        target table, and the role must be granted to authenticator.

        Returns the inserted rows with server-generated values (IDs, defaults).
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_data_api_insert")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            client = await _get_data_api_client(params.project_name)
            try:
                result = await client.insert(
                    params.schema_name, params.table, params.rows
                )
                return json.dumps(
                    {
                        "status": "inserted",
                        "rows_inserted": len(params.rows),
                        "result": result,
                    },
                    indent=2,
                    default=str,
                )
            finally:
                await client.close()
        except DataAPIError as e:
            return _format_data_api_error(e)
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"

    @mcp.tool(
        name="lakebase_data_api_update",
        annotations={
            "title": "Data API — Update Rows",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_update(params: DataAPIUpdateInput) -> str:
        """Update rows in a Lakebase table via the REST Data API.

        Sends a PATCH request to the PostgREST endpoint. Filters are REQUIRED
        to prevent accidental full-table updates.

        The requesting identity must have UPDATE privileges on the target table.

        Returns the updated rows.
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_data_api_update")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            client = await _get_data_api_client(params.project_name)
            try:
                result = await client.update(
                    params.schema_name,
                    params.table,
                    params.filters,
                    params.data,
                )
                return json.dumps(
                    {"status": "updated", "result": result},
                    indent=2,
                    default=str,
                )
            finally:
                await client.close()
        except DataAPIError as e:
            return _format_data_api_error(e)
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"

    @mcp.tool(
        name="lakebase_data_api_delete",
        annotations={
            "title": "Data API — Delete Rows",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_delete(params: DataAPIDeleteInput) -> str:
        """Delete rows from a Lakebase table via the REST Data API.

        Sends a DELETE request to the PostgREST endpoint. Filters are REQUIRED
        to prevent accidental full-table deletes.

        The requesting identity must have DELETE privileges on the target table.
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_data_api_delete")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            client = await _get_data_api_client(params.project_name)
            try:
                result = await client.delete(
                    params.schema_name, params.table, params.filters
                )
                return json.dumps(
                    {"status": "deleted", "result": result},
                    indent=2,
                    default=str,
                )
            finally:
                await client.close()
        except DataAPIError as e:
            return _format_data_api_error(e)
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"

    @mcp.tool(
        name="lakebase_data_api_schema",
        annotations={
            "title": "Data API — OpenAPI Schema",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_schema(params: DataAPISchemaInput) -> str:
        """Fetch the OpenAPI 3 schema from the Data API.

        Requires the OpenAPI setting to be enabled in the Data API configuration.
        The schema describes all exposed tables, their columns, and available
        operations. Can be used to generate typed clients (TypeScript, Python, Go)
        or imported into Postman/Swagger UI.
        """
        try:
            client = await _get_data_api_client(params.project_name)
            try:
                result = await client.get_openapi_schema()
                return json.dumps(result, indent=2, default=str)
            finally:
                await client.close()
        except DataAPIError as e:
            return _format_data_api_error(e)
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"

    @mcp.tool(
        name="lakebase_data_api_configure",
        annotations={
            "title": "Data API — Configure Settings",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_configure(
        params: DataAPIConfigureInput,
    ) -> str:
        """Configure the Lakebase Data API settings for a project.

        Settings include:
        - exposed_schemas: Which schemas are accessible via REST (default: public)
        - max_rows: Hard cap on rows per response (paginate beyond this)
        - cors_allowed_origins: CORS whitelist (empty = allow all; list production origins)
        - openapi_enabled: Enable /openapi.json for client generation
        - server_timing_enabled: Enable Server-Timing headers for debugging

        After changing exposed schemas, refresh the schema cache for changes
        to take effect immediately.
        """
        if governance:
            allowed, error_msg = governance.check_tool_access("lakebase_data_api_configure")
            if not allowed:
                return f"Error: {error_msg}"
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            body: dict[str, Any] = {}
            if params.exposed_schemas is not None:
                body["exposed_schemas"] = params.exposed_schemas
            if params.max_rows is not None:
                body["max_rows"] = params.max_rows
            if params.cors_allowed_origins is not None:
                body["cors_allowed_origins"] = params.cors_allowed_origins
            if params.openapi_enabled is not None:
                body["openapi_enabled"] = params.openapi_enabled
            if params.server_timing_enabled is not None:
                body["server_timing_enabled"] = params.server_timing_enabled

            if not body:
                return json.dumps(
                    {
                        "status": "no_change",
                        "message": "No settings provided. Specify at least one setting to update.",
                    },
                    indent=2,
                )

            result = ws.api_client.do(
                "PATCH",
                f"/api/2.0/lakebase/projects/{params.project_name}/data-api",
                body=body,
            )
            return json.dumps(
                {
                    "status": "configured",
                    "changes": body,
                    "message": (
                        "Data API settings updated. "
                        "If you changed exposed_schemas, refresh the schema cache "
                        "for changes to take effect."
                    ),
                    "details": result,
                },
                indent=2,
                default=str,
            )
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"

    @mcp.tool(
        name="lakebase_data_api_status",
        annotations={
            "title": "Data API — Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_data_api_status(params: DataAPIStatusInput) -> str:
        """Check the Data API status for a Lakebase project.

        Returns whether the Data API is enabled, the REST endpoint URL,
        current configuration (exposed schemas, CORS, max rows, OpenAPI),
        and the authenticator role status.

        Use this before making Data API calls to verify the API is active
        and get the correct endpoint URL.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}/data-api",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error: {type(e).__name__} — {e}"


def _format_data_api_error(e: DataAPIError) -> str:
    """Format Data API errors with actionable messages."""
    if e.status_code == 401:
        return (
            "Error: Data API authentication failed. The OAuth token may be expired "
            "or the requesting identity may not have a Postgres role. "
            "Use lakebase_setup_data_api_access to configure role permissions."
        )
    if e.status_code == 403:
        return (
            f"Error: Data API permission denied — {e.detail}. "
            "The identity's Postgres role may lack the required table privileges. "
            "Use lakebase_setup_data_api_access to grant permissions."
        )
    if e.status_code == 404:
        return (
            f"Error: Resource not found — {e.detail}. "
            "Check that the table exists and is in an exposed schema. "
            "Use lakebase_data_api_status to verify configuration."
        )
    if e.status_code == 405 and e.error_code == "25006":
        return (
            "Error: Write operation rejected — this endpoint is a read replica. "
            "Writes (INSERT, UPDATE, DELETE) must be sent to the primary endpoint. "
            "Set use_replica=false or use the primary endpoint URL."
        )
    return f"Error: Data API returned HTTP {e.status_code} — {e.detail}"
