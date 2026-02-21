"""Test Unified Governance Policy — integration of SQL + tool governance.

Tests backward compatibility, legacy mode, new governance mode,
YAML config loading, env var precedence, and dual-layer enforcement.
"""
import os
import pytest
import tempfile
from unittest.mock import patch
from server.governance.policy import (
    GovernanceConfig,
    GovernancePolicy,
    build_governance_policy,
    load_governance_config,
    _parse_env_list,
)
from server.governance.sql_guard import SQLStatementType, PROFILES as SQL_PROFILES
from server.governance.tool_guard import (
    TOOL_CATEGORIES,
    TOOL_PROFILES,
    resolve_tool_policy,
)


# ── Helper ────────────────────────────────────────────────────────────

def _clear_governance_env():
    """Remove all governance env vars for clean test state."""
    vars_to_clear = [
        "LAKEBASE_SQL_PROFILE",
        "LAKEBASE_TOOL_PROFILE",
        "LAKEBASE_SQL_ALLOWED_TYPES",
        "LAKEBASE_SQL_DENIED_TYPES",
        "LAKEBASE_TOOL_ALLOWED_CATEGORIES",
        "LAKEBASE_TOOL_DENIED_CATEGORIES",
        "LAKEBASE_TOOL_ALLOWED",
        "LAKEBASE_TOOL_DENIED",
        "LAKEBASE_GOVERNANCE_CONFIG",
        "LAKEBASE_ALLOW_WRITE",
    ]
    env = {k: v for k, v in os.environ.items() if k not in vars_to_clear}
    return env


# ── _parse_env_list Tests ─────────────────────────────────────────────

class TestParseEnvList:
    """Test the env var parser."""

    def test_empty_string(self):
        with patch.dict(os.environ, {"TEST_VAR": ""}, clear=False):
            assert _parse_env_list("TEST_VAR") is None

    def test_unset_var(self):
        assert _parse_env_list("NONEXISTENT_VAR_XYZ") is None

    def test_single_value(self):
        with patch.dict(os.environ, {"TEST_VAR": "select"}, clear=False):
            assert _parse_env_list("TEST_VAR") == ["select"]

    def test_multiple_values(self):
        with patch.dict(os.environ, {"TEST_VAR": "select,insert,update"}, clear=False):
            assert _parse_env_list("TEST_VAR") == ["select", "insert", "update"]

    def test_whitespace_handling(self):
        with patch.dict(os.environ, {"TEST_VAR": " select , insert , update "}, clear=False):
            assert _parse_env_list("TEST_VAR") == ["select", "insert", "update"]

    def test_trailing_comma(self):
        with patch.dict(os.environ, {"TEST_VAR": "select,insert,"}, clear=False):
            assert _parse_env_list("TEST_VAR") == ["select", "insert"]


# ── Backward Compatibility Tests ──────────────────────────────────────

class TestBackwardCompatibility:
    """Verify legacy LAKEBASE_ALLOW_WRITE behavior is preserved."""

    def test_legacy_write_disabled(self):
        """ALLOW_WRITE=false with no governance = read_only SQL, all tools."""
        config = GovernanceConfig(allow_write=False)
        policy = build_governance_policy(config)

        # SQL: only read_only types allowed
        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)")[0] is False

        # Tools: all allowed (no tool restrictions)
        assert policy.check_tool_access("lakebase_execute_query") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch") == (True, "")
        assert policy.check_tool_access("lakebase_delete_branch") == (True, "")

    def test_legacy_write_enabled(self):
        """ALLOW_WRITE=true with no governance = admin SQL, all tools."""
        config = GovernanceConfig(allow_write=True)
        policy = build_governance_policy(config)

        # SQL: all types allowed
        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)") == (True, "")
        assert policy.check_sql("DROP TABLE t") == (True, "")

        # Tools: all allowed
        assert policy.check_tool_access("lakebase_execute_query") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch") == (True, "")

    def test_governance_overrides_legacy(self):
        """New governance takes precedence over ALLOW_WRITE."""
        config = GovernanceConfig(
            allow_write=True,  # legacy says admin
            sql_profile="read_only",  # but new governance says read_only
        )
        policy = build_governance_policy(config)

        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)")[0] is False  # governance wins


# ── GovernanceConfig from env vars ────────────────────────────────────

class TestLoadGovernanceConfig:
    """Test config loading from environment variables."""

    def test_load_sql_profile(self):
        env = _clear_governance_env()
        env["LAKEBASE_SQL_PROFILE"] = "analyst"
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            assert config.sql_profile == "analyst"

    def test_load_tool_profile(self):
        env = _clear_governance_env()
        env["LAKEBASE_TOOL_PROFILE"] = "developer"
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            assert config.tool_profile == "developer"

    def test_load_sql_denied_types(self):
        env = _clear_governance_env()
        env["LAKEBASE_SQL_DENIED_TYPES"] = "drop,truncate,grant"
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            assert config.sql_denied_types == ["drop", "truncate", "grant"]

    def test_load_tool_denied(self):
        env = _clear_governance_env()
        env["LAKEBASE_TOOL_DENIED"] = "lakebase_execute_query,lakebase_delete_branch"
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            assert config.tool_denied_tools == ["lakebase_execute_query", "lakebase_delete_branch"]

    def test_load_allow_write_true(self):
        env = _clear_governance_env()
        env["LAKEBASE_ALLOW_WRITE"] = "true"
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            assert config.allow_write is True

    def test_load_allow_write_false_default(self):
        env = _clear_governance_env()
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            assert config.allow_write is False


# ── YAML Config Loading ───────────────────────────────────────────────

class TestYAMLConfig:
    """Test YAML governance config loading."""

    def test_load_yaml_config(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        yaml_content = """
sql:
  profile: analyst
  denied_types:
    - drop
    - truncate
tools:
  profile: developer
  denied_tools:
    - lakebase_execute_query
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            env = _clear_governance_env()
            env["LAKEBASE_GOVERNANCE_CONFIG"] = yaml_path
            with patch.dict(os.environ, env, clear=True):
                config = load_governance_config()
                assert config.sql_profile == "analyst"
                assert config.sql_denied_types == ["drop", "truncate"]
                assert config.tool_profile == "developer"
                assert config.tool_denied_tools == ["lakebase_execute_query"]
        finally:
            os.unlink(yaml_path)

    def test_env_overrides_yaml(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")

        yaml_content = """
sql:
  profile: analyst
tools:
  profile: developer
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            env = _clear_governance_env()
            env["LAKEBASE_GOVERNANCE_CONFIG"] = yaml_path
            env["LAKEBASE_SQL_PROFILE"] = "admin"  # env overrides YAML
            with patch.dict(os.environ, env, clear=True):
                config = load_governance_config()
                assert config.sql_profile == "admin"  # env wins
                assert config.tool_profile == "developer"  # yaml still applies
        finally:
            os.unlink(yaml_path)

    def test_missing_yaml_file(self):
        env = _clear_governance_env()
        env["LAKEBASE_GOVERNANCE_CONFIG"] = "/nonexistent/path/governance.yaml"
        with patch.dict(os.environ, env, clear=True):
            config = load_governance_config()
            # Should not crash, just warn and use env vars
            assert config.sql_profile is None


# ── Full Policy Integration Tests ─────────────────────────────────────

class TestFullPolicyIntegration:
    """Test complete governance policy with SQL + tool layers."""

    def test_read_only_profile(self):
        config = GovernanceConfig(sql_profile="read_only", tool_profile="read_only")
        policy = build_governance_policy(config)

        # SQL
        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)")[0] is False
        assert policy.check_sql("DROP TABLE t")[0] is False

        # Tools
        assert policy.check_tool_access("lakebase_read_query") == (True, "")
        assert policy.check_tool_access("lakebase_list_schemas") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch")[0] is False
        assert policy.check_tool_access("lakebase_configure_autoscaling")[0] is False

    def test_analyst_profile(self):
        config = GovernanceConfig(sql_profile="analyst", tool_profile="analyst")
        policy = build_governance_policy(config)

        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)") == (True, "")
        assert policy.check_sql("UPDATE t SET col = 1")[0] is False
        assert policy.check_sql("DROP TABLE t")[0] is False

        assert policy.check_tool_access("lakebase_read_query") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch")[0] is False

    def test_developer_profile(self):
        config = GovernanceConfig(sql_profile="developer", tool_profile="developer")
        policy = build_governance_policy(config)

        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)") == (True, "")
        assert policy.check_sql("UPDATE t SET col = 1") == (True, "")
        assert policy.check_sql("CREATE TABLE t (id int)") == (True, "")
        assert policy.check_sql("DROP TABLE t")[0] is False
        assert policy.check_sql("MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.col = s.col")[0] is False

        assert policy.check_tool_access("lakebase_create_branch") == (True, "")
        assert policy.check_tool_access("lakebase_prepare_migration") == (True, "")

    def test_admin_profile(self):
        config = GovernanceConfig(sql_profile="admin", tool_profile="admin")
        policy = build_governance_policy(config)

        # All SQL types
        for sql in [
            "SELECT 1", "INSERT INTO t VALUES (1)", "UPDATE t SET col = 1",
            "DELETE FROM t", "CREATE TABLE t (id int)", "DROP TABLE t",
            "ALTER TABLE t ADD COLUMN c int",
            "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.col = s.col",
            "EXPLAIN SELECT 1",
        ]:
            assert policy.check_sql(sql) == (True, ""), f"Admin should allow: {sql}"

        # All tools
        all_tools = [t for tools in TOOL_CATEGORIES.values() for t in tools]
        for tool in all_tools:
            assert policy.check_tool_access(tool) == (True, ""), f"Admin should allow tool: {tool}"


# ── Dual-Layer Enforcement ────────────────────────────────────────────

class TestDualLayerEnforcement:
    """Test that SQL and tool governance enforce independently."""

    def test_admin_tools_read_only_sql(self):
        """All tools accessible but SQL restricted to SELECT."""
        config = GovernanceConfig(sql_profile="read_only", tool_profile="admin")
        policy = build_governance_policy(config)

        # Tool access: admin allows everything
        assert policy.check_tool_access("lakebase_execute_query") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch") == (True, "")

        # SQL: still restricted
        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)")[0] is False

    def test_read_only_tools_admin_sql(self):
        """SQL unrestricted but many tools blocked."""
        config = GovernanceConfig(sql_profile="admin", tool_profile="read_only")
        policy = build_governance_policy(config)

        # SQL: admin allows everything
        assert policy.check_sql("DROP TABLE t") == (True, "")

        # Tool access: read_only blocks write tools
        assert policy.check_tool_access("lakebase_read_query") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch")[0] is False
        assert policy.check_tool_access("lakebase_prepare_migration")[0] is False

    def test_mixed_profile_with_overrides(self):
        """Developer tools with analyst SQL, plus specific tool denial."""
        config = GovernanceConfig(
            sql_profile="analyst",
            tool_profile="developer",
            tool_denied_tools=["lakebase_execute_query"],
        )
        policy = build_governance_policy(config)

        # SQL: analyst (select, insert, show, describe, explain, set)
        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)") == (True, "")
        assert policy.check_sql("UPDATE t SET col = 1")[0] is False

        # Tools: developer minus execute_query
        assert policy.check_tool_access("lakebase_read_query") == (True, "")
        assert policy.check_tool_access("lakebase_execute_query")[0] is False
        assert policy.check_tool_access("lakebase_create_branch") == (True, "")


# ── Customer Demo Scenario (DB-I-15833) ──────────────────────────────

class TestCustomerDemoScenario:
    """DB-I-15833: Read-only agent with maximum restrictions."""

    @pytest.fixture
    def policy(self):
        config = GovernanceConfig(
            sql_profile="read_only",
            tool_profile="read_only",
            tool_denied_tools=["lakebase_execute_query"],
        )
        return build_governance_policy(config)

    def test_read_query_allowed(self, policy):
        assert policy.check_tool_access("lakebase_read_query") == (True, "")

    def test_execute_query_denied(self, policy):
        assert policy.check_tool_access("lakebase_execute_query")[0] is False

    def test_schema_tools_allowed(self, policy):
        assert policy.check_tool_access("lakebase_list_schemas") == (True, "")
        assert policy.check_tool_access("lakebase_list_tables") == (True, "")
        assert policy.check_tool_access("lakebase_describe_table") == (True, "")
        assert policy.check_tool_access("lakebase_object_tree") == (True, "")

    def test_quality_tools_allowed(self, policy):
        assert policy.check_tool_access("lakebase_profile_table") == (True, "")

    def test_write_tools_denied(self, policy):
        assert policy.check_tool_access("lakebase_create_branch")[0] is False
        assert policy.check_tool_access("lakebase_delete_branch")[0] is False
        assert policy.check_tool_access("lakebase_configure_autoscaling")[0] is False
        assert policy.check_tool_access("lakebase_prepare_migration")[0] is False

    def test_sql_select_allowed(self, policy):
        assert policy.check_sql("SELECT * FROM users") == (True, "")

    def test_sql_insert_denied(self, policy):
        assert policy.check_sql("INSERT INTO users (name) VALUES ('test')")[0] is False

    def test_sql_drop_denied(self, policy):
        assert policy.check_sql("DROP TABLE users")[0] is False

    def test_uc_governance_tools_allowed(self, policy):
        assert policy.check_tool_access("lakebase_get_uc_permissions") == (True, "")
        assert policy.check_tool_access("lakebase_check_my_access") == (True, "")
        assert policy.check_tool_access("lakebase_governance_summary") == (True, "")
        assert policy.check_tool_access("lakebase_list_catalog_grants") == (True, "")


# ── GovernancePolicy Error Messages ───────────────────────────────────

class TestGovernancePolicyErrorMessages:
    """Test that error messages are informative."""

    def test_sql_error_message_includes_type(self):
        config = GovernanceConfig(sql_profile="read_only")
        policy = build_governance_policy(config)
        allowed, msg = policy.check_sql("INSERT INTO t VALUES (1)")
        assert allowed is False
        assert "insert" in msg.lower()
        assert "permitted types" in msg.lower()

    def test_tool_error_message_includes_name(self):
        config = GovernanceConfig(tool_profile="read_only")
        policy = build_governance_policy(config)
        allowed, msg = policy.check_tool_access("lakebase_create_branch")
        assert allowed is False
        assert "lakebase_create_branch" in msg
        assert "governance policy" in msg.lower()

    def test_check_sql_allowed_returns_empty_msg(self):
        config = GovernanceConfig(sql_profile="admin")
        policy = build_governance_policy(config)
        allowed, msg = policy.check_sql("SELECT 1")
        assert allowed is True
        assert msg == ""

    def test_check_tool_allowed_returns_empty_msg(self):
        config = GovernanceConfig(tool_profile="admin")
        policy = build_governance_policy(config)
        allowed, msg = policy.check_tool_access("lakebase_create_branch")
        assert allowed is True
        assert msg == ""


# ── SQL Denied Types with Profile ─────────────────────────────────────

class TestSQLDeniedTypesWithProfile:
    """Test sql_denied_types removes types from profile."""

    def test_developer_minus_create_alter(self):
        config = GovernanceConfig(
            sql_profile="developer",
            sql_denied_types=["create", "alter"],
        )
        policy = build_governance_policy(config)

        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)") == (True, "")
        assert policy.check_sql("UPDATE t SET col = 1") == (True, "")
        assert policy.check_sql("CREATE TABLE t (id int)")[0] is False
        assert policy.check_sql("ALTER TABLE t ADD COLUMN c int")[0] is False

    def test_admin_minus_drop_truncate_grant(self):
        config = GovernanceConfig(
            sql_profile="admin",
            sql_denied_types=["drop", "truncate", "grant"],
        )
        policy = build_governance_policy(config)

        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("CREATE TABLE t (id int)") == (True, "")
        assert policy.check_sql("DROP TABLE t")[0] is False

    def test_sql_allowed_types_additive(self):
        """allowed_types adds to profile."""
        config = GovernanceConfig(
            sql_profile="read_only",
            sql_allowed_types=["insert"],
        )
        policy = build_governance_policy(config)

        assert policy.check_sql("SELECT 1") == (True, "")
        assert policy.check_sql("INSERT INTO t VALUES (1)") == (True, "")
        assert policy.check_sql("UPDATE t SET col = 1")[0] is False


# ── Tool Category Deny with Profile ──────────────────────────────────

class TestToolCategoryDenyWithProfile:
    """Test tool_denied_categories removes categories from profile."""

    def test_developer_minus_compute_write_migration(self):
        config = GovernanceConfig(
            tool_profile="developer",
            tool_denied_categories=["compute_write", "migration"],
        )
        policy = build_governance_policy(config)

        assert policy.check_tool_access("lakebase_read_query") == (True, "")
        assert policy.check_tool_access("lakebase_create_branch") == (True, "")
        assert policy.check_tool_access("lakebase_configure_autoscaling")[0] is False
        assert policy.check_tool_access("lakebase_restart_compute")[0] is False
        assert policy.check_tool_access("lakebase_prepare_migration")[0] is False
        assert policy.check_tool_access("lakebase_complete_migration")[0] is False
        # compute_read still works
        assert policy.check_tool_access("lakebase_get_compute_status") == (True, "")
        assert policy.check_tool_access("lakebase_get_compute_metrics") == (True, "")
