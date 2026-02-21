"""Unified governance policy engine.

Loads config from env vars (primary) and optional YAML file.
Composes SQL governance + tool access control into a single policy.
"""
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from server.governance.sql_guard import (
    SQLGovernor,
    SQLStatementType,
    PROFILES as SQL_PROFILES,
)
from server.governance.tool_guard import (
    ToolAccessPolicy,
    TOOL_PROFILES,
    resolve_tool_policy,
)

logger = logging.getLogger(__name__)


@dataclass
class GovernanceConfig:
    """Parsed governance configuration."""

    # SQL governance
    sql_profile: Optional[str] = None
    sql_allowed_types: Optional[list[str]] = None
    sql_denied_types: Optional[list[str]] = None

    # Tool governance
    tool_profile: Optional[str] = None
    tool_allowed_categories: Optional[list[str]] = None
    tool_denied_categories: Optional[list[str]] = None
    tool_allowed_tools: Optional[list[str]] = None
    tool_denied_tools: Optional[list[str]] = None

    # Legacy compat
    allow_write: bool = False


@dataclass
class GovernancePolicy:
    """Resolved governance policy — the runtime enforcement object."""

    sql_governor: SQLGovernor
    tool_policy: ToolAccessPolicy
    _config: GovernanceConfig = field(repr=False)

    def check_tool_access(self, tool_name: str) -> tuple[bool, str]:
        """Check if a tool is accessible. Returns (allowed, error_msg)."""
        if self.tool_policy.is_tool_allowed(tool_name):
            return True, ""
        return False, (
            f"Tool '{tool_name}' is not permitted by the current governance policy. "
            f"Contact your administrator to request access."
        )

    def check_sql(self, sql: str) -> tuple[bool, str]:
        """Check if a SQL statement is allowed. Returns (allowed, error_msg)."""
        result = self.sql_governor.check(sql)
        if result.allowed:
            return True, ""
        return False, result.error_message


def _load_yaml_config(path: str) -> dict:
    """Load governance config from YAML file."""
    try:
        import yaml
    except ImportError:
        logger.warning(
            "PyYAML not installed. Install with: pip install pyyaml. "
            "Falling back to env var configuration."
        )
        return {}

    config_path = Path(path)
    if not config_path.exists():
        logger.warning(f"Governance config file not found: {path}")
        return {}

    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def _parse_env_list(env_var: str) -> Optional[list[str]]:
    """Parse comma-separated env var into list. Returns None if unset."""
    val = os.environ.get(env_var, "").strip()
    if not val:
        return None
    return [item.strip() for item in val.split(",") if item.strip()]


def load_governance_config() -> GovernanceConfig:
    """Load governance config from env vars + optional YAML.

    Env vars take precedence over YAML for all settings.
    """
    config = GovernanceConfig()

    # Load YAML base (if specified)
    yaml_path = os.environ.get("LAKEBASE_GOVERNANCE_CONFIG", "")
    yaml_data = {}
    if yaml_path:
        yaml_data = _load_yaml_config(yaml_path)

    # SQL governance
    sql_section = yaml_data.get("sql", {})
    config.sql_profile = os.environ.get(
        "LAKEBASE_SQL_PROFILE", sql_section.get("profile")
    ) or None
    config.sql_allowed_types = _parse_env_list("LAKEBASE_SQL_ALLOWED_TYPES") or (
        sql_section.get("allowed_types")
    )
    config.sql_denied_types = _parse_env_list("LAKEBASE_SQL_DENIED_TYPES") or (
        sql_section.get("denied_types")
    )

    # Tool governance
    tool_section = yaml_data.get("tools", {})
    config.tool_profile = os.environ.get(
        "LAKEBASE_TOOL_PROFILE", tool_section.get("profile")
    ) or None
    config.tool_allowed_categories = _parse_env_list(
        "LAKEBASE_TOOL_ALLOWED_CATEGORIES"
    ) or (tool_section.get("allowed_categories"))
    config.tool_denied_categories = _parse_env_list(
        "LAKEBASE_TOOL_DENIED_CATEGORIES"
    ) or (tool_section.get("denied_categories"))
    config.tool_allowed_tools = _parse_env_list("LAKEBASE_TOOL_ALLOWED") or (
        tool_section.get("allowed_tools")
    )
    config.tool_denied_tools = _parse_env_list("LAKEBASE_TOOL_DENIED") or (
        tool_section.get("denied_tools")
    )

    # Legacy compatibility
    config.allow_write = (
        os.environ.get("LAKEBASE_ALLOW_WRITE", "false").lower() == "true"
    )

    return config


def build_governance_policy(
    config: GovernanceConfig = None,
) -> GovernancePolicy:
    """Build the runtime governance policy from config.

    Backward compatibility logic:
    - If NO governance env vars or YAML are set, fall back to legacy behavior:
      - LAKEBASE_ALLOW_WRITE=false -> sql_profile="read_only", all tools allowed
      - LAKEBASE_ALLOW_WRITE=true  -> sql_profile="admin", all tools allowed
    - If governance config IS present, it takes full control
    """
    if config is None:
        config = load_governance_config()

    # Determine if new governance is configured
    has_governance = any(
        [
            config.sql_profile,
            config.sql_allowed_types,
            config.sql_denied_types,
            config.tool_profile,
            config.tool_allowed_categories,
            config.tool_denied_categories,
            config.tool_allowed_tools,
            config.tool_denied_tools,
        ]
    )

    if not has_governance:
        # LEGACY MODE: honor LAKEBASE_ALLOW_WRITE exactly as before
        if config.allow_write:
            sql_allowed = set(SQLStatementType)  # all types
        else:
            sql_allowed = SQL_PROFILES["read_only"]

        logger.info(
            f"Governance: legacy mode (allow_write={config.allow_write}, "
            f"sql_types={len(sql_allowed)}, all tools accessible)"
        )
        return GovernancePolicy(
            sql_governor=SQLGovernor(sql_allowed),
            tool_policy=ToolAccessPolicy(),  # empty = allow all tools
            _config=config,
        )

    # NEW GOVERNANCE MODE
    # Resolve SQL permissions
    sql_allowed: set[SQLStatementType] = set()
    if config.sql_profile and config.sql_profile in SQL_PROFILES:
        sql_allowed = SQL_PROFILES[config.sql_profile].copy()

    if config.sql_allowed_types:
        for t in config.sql_allowed_types:
            try:
                sql_allowed.add(SQLStatementType(t.lower()))
            except ValueError:
                logger.warning(f"Unknown SQL statement type: {t}")

    if config.sql_denied_types:
        for t in config.sql_denied_types:
            try:
                sql_allowed.discard(SQLStatementType(t.lower()))
            except ValueError:
                logger.warning(f"Unknown SQL statement type: {t}")

    # If nothing resolved, default to read_only (default-deny)
    if not sql_allowed:
        sql_allowed = SQL_PROFILES["read_only"]

    # Resolve tool permissions
    tool_policy = resolve_tool_policy(
        profile=config.tool_profile,
        allowed_categories=config.tool_allowed_categories,
        denied_categories=config.tool_denied_categories,
        allowed_tools=config.tool_allowed_tools,
        denied_tools=config.tool_denied_tools,
    )

    logger.info(
        f"Governance: active (sql_profile={config.sql_profile}, "
        f"sql_types={len(sql_allowed)}, tool_profile={config.tool_profile}, "
        f"tool_allow={len(tool_policy.allowed_tools)}, "
        f"tool_deny={len(tool_policy.denied_tools)})"
    )
    return GovernancePolicy(
        sql_governor=SQLGovernor(sql_allowed),
        tool_policy=tool_policy,
        _config=config,
    )
