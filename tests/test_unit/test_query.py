"""Unit tests for SQL query tools."""
import pytest
from server.tools.query import ExecuteQueryInput, WRITE_PATTERNS
from server.utils.formatting import ResponseFormat


class TestWriteDetection:
    def test_select_is_not_write(self):
        assert not WRITE_PATTERNS.match("SELECT * FROM users")

    def test_insert_is_write(self):
        assert WRITE_PATTERNS.match("INSERT INTO users VALUES (1, 'test')")

    def test_update_is_write(self):
        assert WRITE_PATTERNS.match("UPDATE users SET name = 'test'")

    def test_delete_is_write(self):
        assert WRITE_PATTERNS.match("DELETE FROM users WHERE id = 1")

    def test_drop_is_write(self):
        assert WRITE_PATTERNS.match("DROP TABLE users")

    def test_create_is_write(self):
        assert WRITE_PATTERNS.match("CREATE TABLE test (id int)")

    def test_with_leading_whitespace(self):
        assert WRITE_PATTERNS.match("  INSERT INTO users VALUES (1)")

    def test_case_insensitive(self):
        assert WRITE_PATTERNS.match("insert into users values (1)")


class TestQueryInputValidation:
    def test_valid_query(self):
        params = ExecuteQueryInput(sql="SELECT 1")
        assert params.sql == "SELECT 1"

    def test_default_max_rows(self):
        params = ExecuteQueryInput(sql="SELECT 1")
        assert params.max_rows == 100

    def test_dangerous_function_blocked(self):
        with pytest.raises(ValueError, match="blocked function"):
            ExecuteQueryInput(sql="SELECT pg_terminate_backend(123)")

    def test_empty_sql_rejected(self):
        with pytest.raises(ValueError):
            ExecuteQueryInput(sql="")

    def test_max_rows_bounds(self):
        with pytest.raises(ValueError):
            ExecuteQueryInput(sql="SELECT 1", max_rows=2000)
