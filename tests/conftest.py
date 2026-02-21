"""Shared test fixtures for Lakebase MCP tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_pool():
    """Mock database connection pool."""
    mock = AsyncMock()
    mock.execute_readonly = AsyncMock(return_value=[])
    mock.execute_query = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def sample_columns():
    return [
        {
            "column_name": "id",
            "data_type": "integer",
            "is_nullable": "NO",
            "column_default": "nextval('id_seq')",
        },
        {
            "column_name": "name",
            "data_type": "character varying",
            "is_nullable": "YES",
            "column_default": None,
        },
        {
            "column_name": "created_at",
            "data_type": "timestamp with time zone",
            "is_nullable": "NO",
            "column_default": "now()",
        },
    ]


@pytest.fixture
def sample_rows():
    return [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ]


@pytest.fixture
def mock_workspace_client():
    mock = MagicMock()
    mock.api_client.do = MagicMock(return_value={"status": "ok"})
    return mock
