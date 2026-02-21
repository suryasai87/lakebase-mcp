"""Tool-level access control with allow/deny lists.

Enforces per-tool permissions before tool function execution.
Configurable via env vars or YAML governance config.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# Tool categories for bulk allow/deny — all 27 tools + 1 resource tool
TOOL_CATEGORIES: dict[str, list[str]] = {
    "sql_query": [
        "lakebase_execute_query",
        "lakebase_read_query",
        "lakebase_explain_query",
    ],
    "schema_read": [
        "lakebase_list_schemas",
        "lakebase_list_tables",
        "lakebase_describe_table",
        "lakebase_object_tree",
    ],
    "project_read": [
        "lakebase_list_projects",
        "lakebase_describe_project",
        "lakebase_get_connection_string",
    ],
    "branch_read": [
        "lakebase_list_branches",
    ],
    "branch_write": [
        "lakebase_create_branch",
        "lakebase_delete_branch",
    ],
    "compute_read": [
        "lakebase_get_compute_status",
        "lakebase_get_compute_metrics",
    ],
    "compute_write": [
        "lakebase_configure_autoscaling",
        "lakebase_configure_scale_to_zero",
        "lakebase_restart_compute",
        "lakebase_create_read_replica",
    ],
    "migration": [
        "lakebase_prepare_migration",
        "lakebase_complete_migration",
    ],
    "sync_read": [
        "lakebase_list_syncs",
    ],
    "sync_write": [
        "lakebase_create_sync",
    ],
    "quality": [
        "lakebase_profile_table",
    ],
    "feature_read": [
        "lakebase_lookup_features",
        "lakebase_list_feature_tables",
    ],
    "insight": [
        "lakebase_append_insight",
    ],
}

# Pre-built tool profiles (composable with SQL profiles)
TOOL_PROFILES: dict[str, list[str]] = {
    "read_only": [
        "sql_query",  # SQL governance layer further restricts to SELECT only
        "schema_read",
        "project_read",
        "branch_read",
        "compute_read",
        "sync_read",
        "quality",
        "feature_read",
        "insight",
    ],
    "analyst": [
        "sql_query",
        "schema_read",
        "project_read",
        "branch_read",
        "compute_read",
        "sync_read",
        "quality",
        "feature_read",
        "insight",
    ],
    "developer": [
        "sql_query",
        "schema_read",
        "project_read",
        "branch_read",
        "branch_write",
        "compute_read",
        "compute_write",
        "migration",
        "sync_read",
        "sync_write",
        "quality",
        "feature_read",
        "insight",
    ],
    "admin": list(TOOL_CATEGORIES.keys()),
}


@dataclass
class ToolAccessPolicy:
    """Resolved tool access policy."""

    allowed_tools: set[str] = field(default_factory=set)
    denied_tools: set[str] = field(default_factory=set)

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a specific tool is allowed.

        Logic:
        1. If deny list has entries and tool is in deny list -> DENIED
        2. If allow list has entries and tool is NOT in allow list -> DENIED
        3. If neither list has entries -> ALLOWED (permissive default for backward compat)
        """
        if self.denied_tools and tool_name in self.denied_tools:
            return False
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False
        return True


def resolve_tool_policy(
    profile: Optional[str] = None,
    allowed_categories: Optional[list[str]] = None,
    denied_categories: Optional[list[str]] = None,
    allowed_tools: Optional[list[str]] = None,
    denied_tools: Optional[list[str]] = None,
) -> ToolAccessPolicy:
    """Resolve a tool access policy from profile + overrides.

    Priority order (later overrides earlier):
    1. Profile expands to category list
    2. allowed_categories / denied_categories override profile
    3. allowed_tools / denied_tools override everything (individual tool names)
    """
    policy = ToolAccessPolicy()

    # Step 1: Expand profile to tool names
    if profile and profile in TOOL_PROFILES:
        categories = TOOL_PROFILES[profile]
        for cat in categories:
            if cat in TOOL_CATEGORIES:
                policy.allowed_tools.update(TOOL_CATEGORIES[cat])

    # Step 2: Apply category overrides
    if allowed_categories:
        for cat in allowed_categories:
            if cat in TOOL_CATEGORIES:
                policy.allowed_tools.update(TOOL_CATEGORIES[cat])

    if denied_categories:
        for cat in denied_categories:
            if cat in TOOL_CATEGORIES:
                policy.denied_tools.update(TOOL_CATEGORIES[cat])

    # Step 3: Apply individual tool overrides
    if allowed_tools:
        policy.allowed_tools.update(allowed_tools)

    if denied_tools:
        policy.denied_tools.update(denied_tools)

    return policy
