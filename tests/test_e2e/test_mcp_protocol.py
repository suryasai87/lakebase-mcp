"""End-to-end MCP protocol tests using MCP client."""
import pytest
import os

LIVE_E2E = os.environ.get("LAKEBASE_E2E_TEST", "false").lower() == "true"
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8000/mcp")


@pytest.mark.skipif(not LIVE_E2E, reason="E2E tests disabled")
class TestMCPProtocol:

    async def test_list_tools(self):
        """Verify all 27 expected tools are registered."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [t.name for t in tools.tools]

                expected_tools = [
                    # Query (3)
                    "lakebase_execute_query",
                    "lakebase_read_query",
                    "lakebase_explain_query",
                    # Schema (4)
                    "lakebase_list_schemas",
                    "lakebase_list_tables",
                    "lakebase_describe_table",
                    "lakebase_object_tree",
                    # Project (3)
                    "lakebase_list_projects",
                    "lakebase_describe_project",
                    "lakebase_get_connection_string",
                    # Branching (3)
                    "lakebase_create_branch",
                    "lakebase_list_branches",
                    "lakebase_delete_branch",
                    # Compute (6) — NEW from gap analysis
                    "lakebase_get_compute_status",
                    "lakebase_configure_autoscaling",
                    "lakebase_configure_scale_to_zero",
                    "lakebase_get_compute_metrics",
                    "lakebase_restart_compute",
                    "lakebase_create_read_replica",
                    # Migration (2)
                    "lakebase_prepare_migration",
                    "lakebase_complete_migration",
                    # Sync (2)
                    "lakebase_create_sync",
                    "lakebase_list_syncs",
                    # Quality (1)
                    "lakebase_profile_table",
                    # Feature Store (2)
                    "lakebase_lookup_features",
                    "lakebase_list_feature_tables",
                    # Insights (1)
                    "lakebase_append_insight",
                ]
                for tool in expected_tools:
                    assert tool in tool_names, f"Missing tool: {tool}"
                assert len(tool_names) == 27

    async def test_list_resources(self):
        """Verify memo://insights resource is registered."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                resources = await session.list_resources()
                uris = [r.uri for r in resources.resources]
                assert "memo://insights" in uris

    async def test_list_prompts(self):
        """Verify all 4 prompt templates are registered."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                prompts = await session.list_prompts()
                prompt_names = [p.name for p in prompts.prompts]
                assert "lakebase_explore_database" in prompt_names
                assert "lakebase_safe_migration" in prompt_names
                assert "lakebase_setup_sync" in prompt_names
                assert "lakebase_autoscaling_tuning" in prompt_names

    async def test_call_read_query_tool(self):
        """Test calling lakebase_read_query via MCP protocol."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "lakebase_read_query",
                    arguments={
                        "sql": "SELECT 1 as health_check",
                        "max_rows": 1,
                    },
                )
                assert result.content
                text = result.content[0].text
                assert "health_check" in text or "1" in text
