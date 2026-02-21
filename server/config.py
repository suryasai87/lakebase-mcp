"""Configuration for Lakebase MCP Server.

Merged: base config + autoscaling settings (scale-to-zero retry, replica, pool lifecycle).
"""
import os
from dataclasses import dataclass, field


@dataclass
class LakebaseConfig:
    """Server configuration loaded from environment variables."""

    # Databricks workspace
    workspace_host: str = field(
        default_factory=lambda: os.environ.get("DATABRICKS_HOST", "")
    )

    # Lakebase connection (primary)
    lakebase_host: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_HOST", "")
    )
    lakebase_port: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_PORT", "5432"))
    )
    lakebase_database: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_DATABASE", "")
    )
    lakebase_catalog: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_CATALOG", "")
    )

    # Safety
    allow_write: bool = field(
        default_factory=lambda: os.environ.get("LAKEBASE_ALLOW_WRITE", "false").lower()
        == "true"
    )
    max_rows: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_MAX_ROWS", "1000"))
    )
    query_timeout_seconds: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_QUERY_TIMEOUT", "30"))
    )

    # Governance (fine-grained access control — see server/governance/policy.py)
    governance_config_path: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_GOVERNANCE_CONFIG", "")
    )
    sql_profile: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_SQL_PROFILE", "")
    )
    tool_profile: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_TOOL_PROFILE", "")
    )

    # Pool settings
    pool_min_size: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_POOL_MIN", "2"))
    )
    pool_max_size: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_POOL_MAX", "10"))
    )

    # --- Autoscaling settings (from gap analysis) ---

    # Scale-to-zero retry behavior
    scale_to_zero_retry_attempts: int = field(
        default_factory=lambda: int(
            os.environ.get("LAKEBASE_S2Z_RETRY_ATTEMPTS", "5")
        )
    )
    scale_to_zero_retry_base_delay: float = field(
        default_factory=lambda: float(
            os.environ.get("LAKEBASE_S2Z_RETRY_DELAY", "0.5")
        )
    )
    scale_to_zero_max_delay: float = field(
        default_factory=lambda: float(
            os.environ.get("LAKEBASE_S2Z_MAX_DELAY", "10.0")
        )
    )

    # Read replica
    replica_host: str = field(
        default_factory=lambda: os.environ.get("LAKEBASE_REPLICA_HOST", "")
    )
    replica_port: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_REPLICA_PORT", "5432"))
    )

    # Pool lifecycle (handles compute restarts)
    pool_max_lifetime: int = field(
        default_factory=lambda: int(
            os.environ.get("LAKEBASE_POOL_MAX_LIFETIME", "300")
        )
    )
    pool_max_idle: int = field(
        default_factory=lambda: int(os.environ.get("LAKEBASE_POOL_MAX_IDLE", "60"))
    )


config = LakebaseConfig()
