"""Register Lakebase MCP server in Unity Catalog MCP Catalog."""
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
w.api_client.do(
    "POST",
    "/api/2.0/unity-catalog/mcp-servers",
    body={
        "name": "lakebase-mcp",
        "description": (
            "Lakebase PostgreSQL database tools: query, schema, branching, "
            "sync, migration, quality, feature store, compute management, "
            "autoscaling, scale-to-zero, read replicas"
        ),
        "server_url": "https://lakebase-mcp-server-1602460480284688.aws.databricksapps.com/mcp",
        "auth_type": "DATABRICKS_OAUTH",
    },
)
print("Registered lakebase-mcp in Unity Catalog MCP Catalog")
