"""Unit tests for error handling — including autoscaling-aware messages."""
import pytest
from server.utils.errors import handle_error


class TestErrorHandling:
    def test_timeout_error(self):
        result = handle_error(TimeoutError("connection timed out"))
        assert "scale-to-zero" in result.lower() or "timed out" in result.lower()

    def test_generic_error(self):
        result = handle_error(ValueError("test error"))
        assert "ValueError" in result
        assert "test error" in result

    def test_scale_to_zero_connection_error(self):
        result = handle_error(
            ConnectionError(
                "Failed to connect after 5 attempts. "
                "Lakebase compute may still be starting. "
                "Last error: scale-to-zero wake-up"
            )
        )
        assert "scale-to-zero" in result.lower()
        assert "lakebase_get_compute_status" in result
