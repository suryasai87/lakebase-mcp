"""Databricks OAuth + Unity Catalog authentication."""
import logging
from typing import Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.credentials_provider import ModelServingUserCredentials

logger = logging.getLogger(__name__)


class LakebaseAuth:
    """Manages authentication to Databricks and Lakebase."""

    def __init__(self, obo: bool = True):
        if obo:
            self._ws = WorkspaceClient(credentials_strategy=ModelServingUserCredentials())
        else:
            self._ws = WorkspaceClient()

    @property
    def workspace_client(self) -> WorkspaceClient:
        return self._ws

    async def get_lakebase_credentials(self, project_name: str) -> dict:
        """Retrieve Lakebase credentials via Databricks credential vending.
        Uses Unity Catalog permissions to validate access."""
        try:
            creds = self._ws.lakebase.get_credentials(instance_name=project_name)
            return {
                "host": creds.host,
                "port": creds.port,
                "user": creds.user,
                "password": creds.password,
                "database": creds.database,
            }
        except Exception as e:
            logger.error(f"Failed to get Lakebase credentials: {e}")
            raise

    async def generate_database_credential(
        self, project_name: str, branch_name: str = "production",
        endpoint_name: str = "primary",
    ) -> dict:
        """Generate a short-lived OAuth token for Lakebase PostgreSQL access.

        Returns a 1-hour token usable as the PG password or Data API Bearer token.
        Token expiry is checked only at login; open connections stay alive.
        """
        try:
            endpoint_path = (
                f"projects/{project_name}/branches/{branch_name}"
                f"/endpoints/{endpoint_name}"
            )
            result = self._ws.api_client.do(
                "POST",
                "/api/2.0/postgres/generate-database-credential",
                body={"endpoint": endpoint_path},
            )
            return {
                "token": result.get("token", ""),
                "expire_time": result.get("expire_time", ""),
                "endpoint": endpoint_path,
            }
        except Exception as e:
            logger.error(f"Failed to generate database credential: {e}")
            raise

    def check_uc_permission(
        self, catalog: str, schema: str, table: str = None
    ) -> bool:
        """Verify Unity Catalog permissions for the current user."""
        try:
            target = f"{catalog}.{schema}"
            if table:
                target = f"{target}.{table}"
            grants = self._ws.grants.get_effective(
                securable_type="TABLE" if table else "SCHEMA",
                full_name=target,
            )
            return len(grants.privilege_assignments) > 0
        except Exception:
            return False
