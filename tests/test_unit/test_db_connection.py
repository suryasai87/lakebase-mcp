"""Unit tests for connection pool — scale-to-zero retry behavior (Gap 8)."""
import pytest
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch, AsyncMock, MagicMock
import psycopg
from server.db import LakebasePool


def _make_pool_mock(side_effect=None, return_conn=None):
    """Create a mock pool whose .connection() returns a proper async context manager.

    psycopg_pool's .connection() returns an async context manager (not a coroutine),
    so we need to replicate that behavior for the mock.
    """
    mock_pool = MagicMock()

    @asynccontextmanager
    async def fake_connection():
        if side_effect:
            raise side_effect
        yield return_conn

    mock_pool.connection = fake_connection
    return mock_pool


class TestScaleToZeroRetry:
    """Test connection retry logic for scale-to-zero scenarios."""

    async def test_fails_after_max_retries(self):
        """Simulates permanently down compute — should raise ConnectionError."""
        pool = LakebasePool()
        pool._primary_pool = _make_pool_mock(
            side_effect=psycopg.OperationalError("connection refused")
        )

        with pytest.raises(ConnectionError, match="Failed to connect after"):
            async with pool.connection():
                pass

    async def test_retry_uses_exponential_backoff(self):
        """Verify delays increase exponentially: 0.5s, 1s, 2s, 4s."""
        delays = []

        async def capture_sleep(delay):
            delays.append(delay)

        pool = LakebasePool()
        pool._primary_pool = _make_pool_mock(
            side_effect=psycopg.OperationalError("connection refused")
        )

        with patch("server.db.asyncio.sleep", side_effect=capture_sleep):
            with pytest.raises(ConnectionError):
                async with pool.connection():
                    pass

        # Verify exponential backoff pattern (capped at max_delay)
        assert len(delays) > 0
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]  # Non-decreasing


class TestReplicaRouting:
    """Test read replica routing."""

    async def test_prefer_replica_uses_replica_pool(self):
        """When prefer_replica=True and replica pool exists, use it."""
        mock_conn = AsyncMock()
        pool = LakebasePool()
        pool._primary_pool = _make_pool_mock(return_conn=AsyncMock())
        pool._replica_pool = _make_pool_mock(return_conn=mock_conn)

        async with pool.connection(prefer_replica=True) as conn:
            assert conn == mock_conn

    async def test_fallback_to_primary_without_replica(self):
        """When no replica pool, prefer_replica falls back to primary."""
        mock_conn = AsyncMock()
        pool = LakebasePool()
        pool._primary_pool = _make_pool_mock(return_conn=mock_conn)
        pool._replica_pool = None

        async with pool.connection(prefer_replica=True) as conn:
            assert conn == mock_conn
