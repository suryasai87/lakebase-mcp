"""Integration tests for authentication."""
import pytest
import os

LIVE_TEST = os.environ.get("LAKEBASE_LIVE_TEST", "false").lower() == "true"


@pytest.mark.skipif(not LIVE_TEST, reason="Live Lakebase tests disabled")
class TestAuth:

    async def test_workspace_client_initializes(self):
        from server.auth import LakebaseAuth

        auth = LakebaseAuth(obo=False)
        assert auth.workspace_client is not None
