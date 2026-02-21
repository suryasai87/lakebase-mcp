"""Aggregated insights memo resource — inspired by Snowflake MCP's memo://insights."""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

_insights: list[str] = []


class AppendInsightInput(BaseModel):
    insight: str = Field(
        ...,
        description="Data insight to record (e.g., 'Revenue grows 5% MoM in Q4')",
    )


def register_insight_resources(mcp: FastMCP):

    @mcp.resource("memo://insights")
    async def get_insights() -> str:
        """Aggregated data insights discovered during this session."""
        if not _insights:
            return "No insights recorded yet. Use lakebase_append_insight to add discoveries."
        return "\n".join(f"- {i}" for i in _insights)

    @mcp.tool(
        name="lakebase_append_insight",
        annotations={
            "title": "Record Data Insight",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_append_insight(params: AppendInsightInput) -> str:
        """Record a data insight discovered during analysis.
        Insights are aggregated in the memo://insights resource for reference."""
        _insights.append(params.insight)
        return f"Insight recorded ({len(_insights)} total). View all at memo://insights"
