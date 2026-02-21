"""Integration tests for database connectivity (requires live Lakebase)."""
import pytest
import os

LIVE_TEST = os.environ.get("LAKEBASE_LIVE_TEST", "false").lower() == "true"


@pytest.mark.skipif(not LIVE_TEST, reason="Live Lakebase tests disabled")
class TestLiveConnection:

    @pytest.fixture(autouse=True)
    async def setup_pool(self):
        from server.db import pool
        from server.config import config

        conninfo = (
            f"host={config.lakebase_host} port={config.lakebase_port} "
            f"dbname={config.lakebase_database}"
        )
        await pool.initialize(conninfo)
        yield
        await pool.close()

    async def test_simple_query(self):
        from server.db import pool

        result = await pool.execute_readonly("SELECT 1 as test_value")
        assert result[0]["test_value"] == 1

    async def test_list_schemas(self):
        from server.db import pool

        result = await pool.execute_readonly(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'public'"
        )
        assert any(r["schema_name"] == "public" for r in result)

    async def test_readonly_blocks_writes(self):
        from server.db import pool
        import psycopg

        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            await pool.execute_readonly("CREATE TABLE test_should_fail (id int)")

    async def test_scale_to_zero_recovery(self):
        """Test that the pool can recover after a scale-to-zero wake-up.
        This test is only meaningful if the Lakebase compute has been idle."""
        from server.db import pool

        result = await pool.execute_readonly("SELECT now() as wake_time")
        assert result[0]["wake_time"] is not None
