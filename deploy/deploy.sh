#!/bin/bash
set -euo pipefail

# Authenticate
databricks auth login --host "$DATABRICKS_HOST"

# Create the app
databricks apps create lakebase-mcp-server

# Sync and deploy
DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
databricks sync . "/Users/$DATABRICKS_USERNAME/lakebase-mcp-server"
databricks apps deploy lakebase-mcp-server \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/lakebase-mcp-server"

echo "Deployed! MCP endpoint: https://<app-url>/mcp"
