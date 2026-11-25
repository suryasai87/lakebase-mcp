"""MCP server observability tools — latency metrics, slow queries, error rates.

Exposes the in-memory metrics collected by server.observability to AI agents
so they can gauge end-to-end performance without external dashboards.
"""

import json
from typing import Optional
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from server.observability import (
    OperationType,
    get_latency_stats,
    get_slow_operations,
    get_error_summary,
    get_server_summary,
    reset_metrics,
)
from server.governance.policy import GovernancePolicy


class LatencyStatsInput(BaseModel):
    op_type: Optional[str] = Field(
        default=None,
        description=(
            "Filter by operation type: tool_call, sql_query, sql_readonly, "
            "data_api, connection. Omit for all types."
        ),
    )
    window_seconds: int = Field(
        default=300,
        description="Time window in seconds to analyze (default 300 = last 5 minutes)",
        ge=10,
        le=3600,
    )


class SlowOpsInput(BaseModel):
    threshold_ms: float = Field(
        default=1000,
        description="Minimum duration in milliseconds to qualify as slow (default 1000ms)",
        ge=0,
    )
    limit: int = Field(
        default=20,
        description="Maximum number of slow operations to return",
        ge=1,
        le=100,
    )


def register_observability_tools(mcp: FastMCP, governance: GovernancePolicy):

    @mcp.tool(
        name="lakebase_performance_metrics",
        annotations={
            "title": "Performance Metrics (Latency Percentiles)",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_performance_metrics(params: LatencyStatsInput) -> str:
        """Get latency percentile stats (p50/p90/p99/mean/max) for all operations.

        Groups metrics by operation type and name. Use op_type to filter to
        a specific layer: tool_call (end-to-end), sql_query/sql_readonly
        (database), data_api (REST), or connection (pool acquisition).
        Adjust window_seconds to focus on recent or longer-term performance.
        """
        allowed, err = governance.check_tool_access("lakebase_performance_metrics")
        if not allowed:
            return f"Error: {err}"

        op_filter = None
        if params.op_type:
            try:
                op_filter = OperationType(params.op_type)
            except ValueError:
                valid = ", ".join(t.value for t in OperationType)
                return f"Error: Invalid op_type '{params.op_type}'. Valid: {valid}"

        stats = get_latency_stats(op_type=op_filter, last_seconds=params.window_seconds)
        if not stats:
            return (
                f"_No metrics recorded in the last {params.window_seconds}s._ "
                "Run some operations first, then check again."
            )

        lines = [f"## Performance Metrics (last {params.window_seconds}s)\n"]
        lines.append("| Operation | Count | Mean | p50 | p90 | p99 | Max |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for key, s in stats.items():
            lines.append(
                f"| {key} | {s['count']} | {s['mean_ms']}ms | "
                f"{s['p50_ms']}ms | {s['p90_ms']}ms | {s['p99_ms']}ms | {s['max_ms']}ms |"
            )
        return "\n".join(lines)

    @mcp.tool(
        name="lakebase_slow_operations",
        annotations={
            "title": "Slow Operations",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_slow_operations(params: SlowOpsInput) -> str:
        """List the slowest operations above a threshold.

        Returns operations sorted by duration (slowest first) with their
        type, name, duration, success status, and metadata (row counts,
        SQL snippets, HTTP status codes). Use to identify bottlenecks.
        """
        allowed, err = governance.check_tool_access("lakebase_slow_operations")
        if not allowed:
            return f"Error: {err}"

        ops = get_slow_operations(
            threshold_ms=params.threshold_ms, last_n=params.limit
        )
        if not ops:
            return (
                f"_No operations slower than {params.threshold_ms}ms found._ "
                "Either performance is healthy or no operations have been recorded yet."
            )

        lines = [f"## Slow Operations (>{params.threshold_ms}ms)\n"]
        for i, op in enumerate(ops, 1):
            status = "OK" if op["success"] else "ERROR"
            meta_str = json.dumps(op["metadata"], default=str) if op["metadata"] else ""
            lines.append(
                f"**{i}.** `{op['name']}` ({op['op_type']}) — "
                f"**{op['duration_ms']}ms** [{status}]"
            )
            if meta_str:
                lines.append(f"   {meta_str}")
        return "\n".join(lines)

    @mcp.tool(
        name="lakebase_error_rates",
        annotations={
            "title": "Error Rates",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_error_rates() -> str:
        """Show error counts and rates for all operations.

        Returns total invocations and error count per operation,
        useful for identifying unreliable endpoints or tools.
        """
        allowed, err = governance.check_tool_access("lakebase_error_rates")
        if not allowed:
            return f"Error: {err}"

        summary = get_error_summary()
        if not summary:
            return "_No operations recorded yet._"

        lines = ["## Error Rates\n"]
        lines.append("| Operation | Total | Errors | Error % |")
        lines.append("| --- | ---: | ---: | ---: |")
        for key, s in summary.items():
            rate = round(s["errors"] / s["total"] * 100, 1) if s["total"] else 0
            lines.append(
                f"| {key} | {s['total']} | {s['errors']} | {rate}% |"
            )
        return "\n".join(lines)

    @mcp.tool(
        name="lakebase_server_health",
        annotations={
            "title": "Server Health Summary",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_server_health() -> str:
        """High-level MCP server health: uptime, throughput, error rate, and
        recent latency summary. Quick check before diving into detailed metrics.
        """
        allowed, err = governance.check_tool_access("lakebase_server_health")
        if not allowed:
            return f"Error: {err}"

        s = get_server_summary()
        hours = int(s["uptime_seconds"] // 3600)
        mins = int((s["uptime_seconds"] % 3600) // 60)
        uptime_str = f"{hours}h {mins}m" if hours else f"{mins}m"

        lines = [
            "## Server Health\n",
            f"| Metric | Value |",
            f"| --- | --- |",
            f"| Uptime | {uptime_str} |",
            f"| Total operations | {s['total_operations']} |",
            f"| Total errors | {s['total_errors']} |",
            f"| Error rate | {s['error_rate_pct']}% |",
            f"| Metric buffer | {s['buffer_usage']} |",
            "",
            "### Last 60 seconds\n",
            f"| Metric | Value |",
            f"| --- | --- |",
            f"| Operations | {s['last_60s']['operations']} |",
            f"| Mean latency | {s['last_60s']['mean_latency_ms']}ms |",
            f"| Max latency | {s['last_60s']['max_latency_ms']}ms |",
        ]
        return "\n".join(lines)

    @mcp.tool(
        name="lakebase_reset_metrics",
        annotations={
            "title": "Reset Performance Metrics",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_reset_metrics() -> str:
        """Clear all collected performance metrics and reset counters.

        Use after configuration changes or deployments to get a clean baseline.
        Returns counts of cleared data.
        """
        allowed, err = governance.check_tool_access("lakebase_reset_metrics")
        if not allowed:
            return f"Error: {err}"

        counts = reset_metrics()
        return (
            f"Metrics reset. Cleared {counts['spans_cleared']} spans "
            f"and {counts['counters_cleared']} counter entries."
        )
