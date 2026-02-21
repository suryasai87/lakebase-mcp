"""Test Tool-Level Access Control — all 31 tools across all 4 profiles.

Tests tool categories, profile definitions, ToolAccessPolicy, allow/deny lists,
category overrides, and individual tool overrides.
"""
import pytest
from server.governance.tool_guard import (
    TOOL_CATEGORIES,
    TOOL_PROFILES,
    ToolAccessPolicy,
    resolve_tool_policy,
)


# ── All 31 Tools ──────────────────────────────────────────────────────

ALL_TOOLS = sorted(
    tool for tools in TOOL_CATEGORIES.values() for tool in tools
)

# ── Category Definitions ──────────────────────────────────────────────

class TestToolCategories:
    """Verify category definitions are complete and correct."""

    def test_total_categories(self):
        assert len(TOOL_CATEGORIES) == 14

    def test_total_tools(self):
        assert len(ALL_TOOLS) == 31

    def test_no_duplicate_tools(self):
        all_tools_flat = [t for tools in TOOL_CATEGORIES.values() for t in tools]
        assert len(all_tools_flat) == len(set(all_tools_flat)), "Duplicate tool found across categories"

    def test_sql_query_category(self):
        assert set(TOOL_CATEGORIES["sql_query"]) == {
            "lakebase_execute_query",
            "lakebase_read_query",
            "lakebase_explain_query",
        }

    def test_schema_read_category(self):
        assert set(TOOL_CATEGORIES["schema_read"]) == {
            "lakebase_list_schemas",
            "lakebase_list_tables",
            "lakebase_describe_table",
            "lakebase_object_tree",
        }

    def test_project_read_category(self):
        assert set(TOOL_CATEGORIES["project_read"]) == {
            "lakebase_list_projects",
            "lakebase_describe_project",
            "lakebase_get_connection_string",
        }

    def test_branch_read_category(self):
        assert TOOL_CATEGORIES["branch_read"] == ["lakebase_list_branches"]

    def test_branch_write_category(self):
        assert set(TOOL_CATEGORIES["branch_write"]) == {
            "lakebase_create_branch",
            "lakebase_delete_branch",
        }

    def test_compute_read_category(self):
        assert set(TOOL_CATEGORIES["compute_read"]) == {
            "lakebase_get_compute_status",
            "lakebase_get_compute_metrics",
        }

    def test_compute_write_category(self):
        assert set(TOOL_CATEGORIES["compute_write"]) == {
            "lakebase_configure_autoscaling",
            "lakebase_configure_scale_to_zero",
            "lakebase_restart_compute",
            "lakebase_create_read_replica",
        }

    def test_migration_category(self):
        assert set(TOOL_CATEGORIES["migration"]) == {
            "lakebase_prepare_migration",
            "lakebase_complete_migration",
        }

    def test_sync_read_category(self):
        assert TOOL_CATEGORIES["sync_read"] == ["lakebase_list_syncs"]

    def test_sync_write_category(self):
        assert TOOL_CATEGORIES["sync_write"] == ["lakebase_create_sync"]

    def test_quality_category(self):
        assert TOOL_CATEGORIES["quality"] == ["lakebase_profile_table"]

    def test_feature_read_category(self):
        assert set(TOOL_CATEGORIES["feature_read"]) == {
            "lakebase_lookup_features",
            "lakebase_list_feature_tables",
        }

    def test_insight_category(self):
        assert TOOL_CATEGORIES["insight"] == ["lakebase_append_insight"]

    def test_uc_governance_category(self):
        assert set(TOOL_CATEGORIES["uc_governance"]) == {
            "lakebase_get_uc_permissions",
            "lakebase_check_my_access",
            "lakebase_governance_summary",
            "lakebase_list_catalog_grants",
        }


# ── Profile Definitions ──────────────────────────────────────────────

class TestToolProfiles:
    """Verify all 4 tool profiles are correct."""

    def test_read_only_categories(self):
        expected = [
            "sql_query", "schema_read", "project_read", "branch_read",
            "compute_read", "sync_read", "quality", "feature_read",
            "insight", "uc_governance",
        ]
        assert TOOL_PROFILES["read_only"] == expected

    def test_analyst_same_as_read_only(self):
        assert TOOL_PROFILES["analyst"] == TOOL_PROFILES["read_only"]

    def test_developer_categories(self):
        expected = [
            "sql_query", "schema_read", "project_read", "branch_read",
            "branch_write", "compute_read", "compute_write", "migration",
            "sync_read", "sync_write", "quality", "feature_read",
            "insight", "uc_governance",
        ]
        assert TOOL_PROFILES["developer"] == expected

    def test_admin_has_all_categories(self):
        assert set(TOOL_PROFILES["admin"]) == set(TOOL_CATEGORIES.keys())

    def test_profile_hierarchy(self):
        """Each profile's category set is a superset of the previous."""
        ro = set(TOOL_PROFILES["read_only"])
        an = set(TOOL_PROFILES["analyst"])
        dev = set(TOOL_PROFILES["developer"])
        adm = set(TOOL_PROFILES["admin"])

        assert ro == an  # analyst == read_only for tools
        assert ro.issubset(dev)
        assert dev.issubset(adm)


# ── ToolAccessPolicy Tests ────────────────────────────────────────────

class TestToolAccessPolicy:
    """Test the ToolAccessPolicy dataclass."""

    def test_empty_policy_allows_all(self):
        """No allow/deny lists means all tools allowed."""
        policy = ToolAccessPolicy()
        for tool in ALL_TOOLS:
            assert policy.is_tool_allowed(tool) is True

    def test_allow_list_only(self):
        """Only tools in allow list are permitted."""
        policy = ToolAccessPolicy(
            allowed_tools={"lakebase_read_query", "lakebase_list_schemas"}
        )
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_list_schemas") is True
        assert policy.is_tool_allowed("lakebase_execute_query") is False
        assert policy.is_tool_allowed("lakebase_create_branch") is False

    def test_deny_list_only(self):
        """Tools in deny list are blocked; all others allowed."""
        policy = ToolAccessPolicy(
            denied_tools={"lakebase_execute_query", "lakebase_delete_branch"}
        )
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_execute_query") is False
        assert policy.is_tool_allowed("lakebase_delete_branch") is False

    def test_deny_overrides_allow(self):
        """If tool is in both allow and deny, deny wins."""
        policy = ToolAccessPolicy(
            allowed_tools={"lakebase_read_query", "lakebase_execute_query"},
            denied_tools={"lakebase_execute_query"},
        )
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_execute_query") is False

    def test_unknown_tool(self):
        """Unknown tools are blocked when allow list is set."""
        policy = ToolAccessPolicy(
            allowed_tools={"lakebase_read_query"}
        )
        assert policy.is_tool_allowed("unknown_tool") is False


# ── resolve_tool_policy Tests ─────────────────────────────────────────

class TestResolveToolPolicy:
    """Test the policy resolution function."""

    def test_read_only_profile_resolves(self):
        policy = resolve_tool_policy(profile="read_only")
        # read_only should allow all tools in read categories
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_list_schemas") is True
        assert policy.is_tool_allowed("lakebase_list_tables") is True
        assert policy.is_tool_allowed("lakebase_profile_table") is True
        assert policy.is_tool_allowed("lakebase_get_uc_permissions") is True
        # Should deny write tools
        assert policy.is_tool_allowed("lakebase_create_branch") is False
        assert policy.is_tool_allowed("lakebase_delete_branch") is False
        assert policy.is_tool_allowed("lakebase_configure_autoscaling") is False
        assert policy.is_tool_allowed("lakebase_restart_compute") is False
        assert policy.is_tool_allowed("lakebase_prepare_migration") is False
        assert policy.is_tool_allowed("lakebase_create_sync") is False

    def test_analyst_profile_resolves(self):
        policy = resolve_tool_policy(profile="analyst")
        # Same as read_only
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_create_branch") is False
        assert policy.is_tool_allowed("lakebase_prepare_migration") is False

    def test_developer_profile_resolves(self):
        policy = resolve_tool_policy(profile="developer")
        # Has all read + write categories except admin-only
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_create_branch") is True
        assert policy.is_tool_allowed("lakebase_delete_branch") is True
        assert policy.is_tool_allowed("lakebase_configure_autoscaling") is True
        assert policy.is_tool_allowed("lakebase_prepare_migration") is True
        assert policy.is_tool_allowed("lakebase_create_sync") is True
        assert policy.is_tool_allowed("lakebase_get_uc_permissions") is True

    def test_admin_profile_resolves(self):
        policy = resolve_tool_policy(profile="admin")
        for tool in ALL_TOOLS:
            assert policy.is_tool_allowed(tool) is True, f"{tool} should be allowed in admin"

    def test_category_deny_override(self):
        """Developer profile with compute_write denied."""
        policy = resolve_tool_policy(
            profile="developer",
            denied_categories=["compute_write", "migration"],
        )
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_create_branch") is True
        assert policy.is_tool_allowed("lakebase_configure_autoscaling") is False
        assert policy.is_tool_allowed("lakebase_restart_compute") is False
        assert policy.is_tool_allowed("lakebase_prepare_migration") is False
        assert policy.is_tool_allowed("lakebase_get_compute_status") is True  # compute_read not denied

    def test_individual_tool_deny(self):
        """Admin profile with specific tools denied."""
        policy = resolve_tool_policy(
            profile="admin",
            denied_tools=["lakebase_execute_query", "lakebase_delete_branch"],
        )
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_execute_query") is False
        assert policy.is_tool_allowed("lakebase_create_branch") is True
        assert policy.is_tool_allowed("lakebase_delete_branch") is False

    def test_category_allow_override(self):
        """No profile, but specific categories allowed."""
        policy = resolve_tool_policy(
            allowed_categories=["sql_query", "schema_read"],
        )
        assert policy.is_tool_allowed("lakebase_read_query") is True
        assert policy.is_tool_allowed("lakebase_execute_query") is True
        assert policy.is_tool_allowed("lakebase_list_schemas") is True
        assert policy.is_tool_allowed("lakebase_create_branch") is False
        assert policy.is_tool_allowed("lakebase_profile_table") is False

    def test_no_profile_no_overrides(self):
        """No configuration means permissive (empty policy)."""
        policy = resolve_tool_policy()
        for tool in ALL_TOOLS:
            assert policy.is_tool_allowed(tool) is True


# ── Full Tool Matrix per Profile ──────────────────────────────────────

class TestFullToolMatrixReadOnly:
    """Test every tool against read_only profile."""

    @pytest.fixture
    def policy(self):
        return resolve_tool_policy(profile="read_only")

    # Tools that SHOULD be allowed in read_only
    ALLOWED = [
        "lakebase_execute_query",
        "lakebase_read_query",
        "lakebase_explain_query",
        "lakebase_list_schemas",
        "lakebase_list_tables",
        "lakebase_describe_table",
        "lakebase_object_tree",
        "lakebase_list_projects",
        "lakebase_describe_project",
        "lakebase_get_connection_string",
        "lakebase_list_branches",
        "lakebase_get_compute_status",
        "lakebase_get_compute_metrics",
        "lakebase_list_syncs",
        "lakebase_profile_table",
        "lakebase_lookup_features",
        "lakebase_list_feature_tables",
        "lakebase_append_insight",
        "lakebase_get_uc_permissions",
        "lakebase_check_my_access",
        "lakebase_governance_summary",
        "lakebase_list_catalog_grants",
    ]

    # Tools that SHOULD be denied in read_only
    DENIED = [
        "lakebase_create_branch",
        "lakebase_delete_branch",
        "lakebase_configure_autoscaling",
        "lakebase_configure_scale_to_zero",
        "lakebase_restart_compute",
        "lakebase_create_read_replica",
        "lakebase_prepare_migration",
        "lakebase_complete_migration",
        "lakebase_create_sync",
    ]

    @pytest.mark.parametrize("tool", ALLOWED)
    def test_allowed_tools(self, policy, tool):
        assert policy.is_tool_allowed(tool) is True, f"{tool} should be ALLOWED in read_only"

    @pytest.mark.parametrize("tool", DENIED)
    def test_denied_tools(self, policy, tool):
        assert policy.is_tool_allowed(tool) is False, f"{tool} should be DENIED in read_only"

    def test_complete_coverage(self, policy):
        """All 31 tools are covered in either ALLOWED or DENIED."""
        covered = set(self.ALLOWED + self.DENIED)
        assert covered == set(ALL_TOOLS), f"Missing tools: {set(ALL_TOOLS) - covered}"


class TestFullToolMatrixDeveloper:
    """Test every tool against developer profile."""

    @pytest.fixture
    def policy(self):
        return resolve_tool_policy(profile="developer")

    # All 31 tools should be allowed in developer
    ALLOWED = ALL_TOOLS  # developer has all categories

    @pytest.mark.parametrize("tool", ALL_TOOLS)
    def test_all_tools_allowed(self, policy, tool):
        assert policy.is_tool_allowed(tool) is True, f"{tool} should be ALLOWED in developer"


class TestFullToolMatrixAdmin:
    """Test every tool against admin profile."""

    @pytest.fixture
    def policy(self):
        return resolve_tool_policy(profile="admin")

    @pytest.mark.parametrize("tool", ALL_TOOLS)
    def test_all_tools_allowed(self, policy, tool):
        assert policy.is_tool_allowed(tool) is True, f"{tool} should be ALLOWED in admin"
