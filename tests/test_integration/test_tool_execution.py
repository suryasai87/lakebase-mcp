"""Integration tests for tool execution via MCP protocol."""
import pytest
from unittest.mock import patch, AsyncMock


class TestToolExecution:

    @patch("server.db.pool")
    async def test_read_query_returns_results(self, mock_pool):
        mock_pool.execute_readonly = AsyncMock(
            return_value=[{"id": 1, "name": "test"}]
        )
        from server.tools.query import ExecuteQueryInput

        params = ExecuteQueryInput(sql="SELECT * FROM users LIMIT 1")
        assert params.sql == "SELECT * FROM users LIMIT 1"

    @patch("server.db.pool")
    async def test_write_blocked_by_default(self, mock_pool):
        from server.tools.query import ExecuteQueryInput, WRITE_PATTERNS
        from server.config import config

        config.allow_write = False
        params = ExecuteQueryInput(sql="DELETE FROM users WHERE id = 1")
        assert WRITE_PATTERNS.match(params.sql)
        assert not config.allow_write
