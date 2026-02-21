"""Lakebase compute management tools — autoscaling, scale-to-zero, metrics, replicas.

NEW from Gap 3 + Gap 4: 6 tools for compute lifecycle management.
"""
import json
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from mcp.server.fastmcp import FastMCP
from server.auth import LakebaseAuth
from server.utils.errors import handle_error


class GetComputeStatusInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(default="production", description="Branch name")


class ConfigureAutoscalingInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(default="production", description="Branch name")
    min_cu: float = Field(
        ..., description="Minimum compute units (0.5 to 32)", ge=0.5, le=32
    )
    max_cu: float = Field(
        ..., description="Maximum compute units (min_cu to min_cu+8)", ge=0.5, le=32
    )
    enable_autoscaling: bool = Field(
        default=True, description="Enable/disable autoscaling"
    )


class ConfigureScaleToZeroInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(default="production", description="Branch name")
    enabled: bool = Field(..., description="Enable or disable scale-to-zero")
    timeout_seconds: int = Field(
        default=300,
        description="Inactivity timeout before suspending (60-3600 seconds)",
        ge=60,
        le=3600,
    )


class GetComputeMetricsInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(default="production", description="Branch name")
    period_minutes: int = Field(
        default=60,
        description="Metrics lookback period in minutes",
        ge=5,
        le=1440,
    )


class RestartComputeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(default="production", description="Branch name")


class CreateReadReplicaInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    project_name: str = Field(..., description="Lakebase project name")
    branch_name: str = Field(default="production", description="Branch name")
    min_cu: float = Field(
        default=0.5, description="Min CU for replica autoscaling", ge=0.5, le=32
    )
    max_cu: float = Field(
        default=4, description="Max CU for replica autoscaling", ge=0.5, le=32
    )


def register_compute_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_get_compute_status",
        annotations={
            "title": "Get Compute Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_get_compute_status(params: GetComputeStatusInput) -> str:
        """Get the current status of a Lakebase branch compute.

        Returns:
        - State: active, suspended (scale-to-zero), scaling_up, scaling_down
        - Current CU allocation and autoscaling range
        - Scale-to-zero configuration and last suspension time
        - Active connections count vs max connections
        - Compute uptime since last start/resume
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/branches/{params.branch_name}/computes",
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_configure_autoscaling",
        annotations={
            "title": "Configure Compute Autoscaling",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_configure_autoscaling(
        params: ConfigureAutoscalingInput,
    ) -> str:
        """Configure autoscaling for a Lakebase branch compute.

        Autoscaling dynamically adjusts compute resources (CU) based on workload.
        Lakebase monitors CPU load, memory usage, and working set size.

        Rules:
        - Each CU = 2 GB RAM + proportional CPU
        - Min CU: 0.5, Max CU: 32
        - Max - Min cannot exceed 8 CU
        - Scaling happens without connection interruptions

        Example: min_cu=1, max_cu=8 gives a 2-16 GB RAM range.
        """
        try:
            if params.max_cu - params.min_cu > 8:
                return (
                    f"Error: Autoscaling range too wide. "
                    f"max_cu ({params.max_cu}) - min_cu ({params.min_cu}) = "
                    f"{params.max_cu - params.min_cu}, "
                    f"but maximum allowed spread is 8 CU. "
                    f"Try max_cu={params.min_cu + 8} or increase min_cu."
                )
            auth = LakebaseAuth()
            ws = auth.workspace_client
            ws.api_client.do(
                "PATCH",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/branches/{params.branch_name}/computes/primary",
                body={
                    "autoscaling_enabled": params.enable_autoscaling,
                    "min_cu": params.min_cu,
                    "max_cu": params.max_cu,
                },
            )
            return json.dumps(
                {
                    "status": "configured",
                    "autoscaling_enabled": params.enable_autoscaling,
                    "min_cu": params.min_cu,
                    "max_cu": params.max_cu,
                    "ram_range": f"{params.min_cu * 2} - {params.max_cu * 2} GB",
                    "message": "Autoscaling applies without compute restart.",
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_configure_scale_to_zero",
        annotations={
            "title": "Configure Scale-to-Zero",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_configure_scale_to_zero(
        params: ConfigureScaleToZeroInput,
    ) -> str:
        """Configure scale-to-zero behavior for a Lakebase compute.

        When enabled, the compute suspends after the inactivity timeout,
        reducing compute costs to zero. It automatically resumes in hundreds
        of milliseconds when new queries arrive.

        Recommended settings:
        - Dev/test: enabled=True, timeout=60s (aggressive cost savings)
        - Staging: enabled=True, timeout=300s (balance)
        - Production: enabled=False (always-on for lowest latency)

        NOTE: Production branch computes have scale-to-zero disabled by default.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            ws.api_client.do(
                "PATCH",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/branches/{params.branch_name}/computes/primary",
                body={
                    "scale_to_zero_enabled": params.enabled,
                    "scale_to_zero_timeout_seconds": params.timeout_seconds,
                },
            )
            return json.dumps(
                {
                    "status": "configured",
                    "scale_to_zero_enabled": params.enabled,
                    "timeout_seconds": params.timeout_seconds,
                    "message": (
                        f"Compute will suspend after {params.timeout_seconds}s of inactivity."
                        if params.enabled
                        else "Scale-to-zero disabled. Compute will remain active."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_get_compute_metrics",
        annotations={
            "title": "Get Compute Metrics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_get_compute_metrics(
        params: GetComputeMetricsInput,
    ) -> str:
        """Get compute metrics for a Lakebase branch.

        Returns time-series data for:
        - CPU utilization (%)
        - Memory usage (%) and allocated vs used
        - Working set size (frequently accessed data)
        - Active connections count
        - Compute state transitions (active/suspended/scaling)
        - Current CU allocation within autoscaling range

        These are the same metrics Lakebase uses internally for autoscaling decisions.
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "GET",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/branches/{params.branch_name}/computes/primary/metrics",
                query={"period_minutes": params.period_minutes},
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_restart_compute",
        annotations={
            "title": "Restart Compute",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_restart_compute(params: RestartComputeInput) -> str:
        """Restart a Lakebase branch compute.

        WARNING: This interrupts all active connections. Applications must
        reconnect. Use only when needed to:
        - Apply configuration changes
        - Resolve performance issues
        - Pick up Postgres extension updates
        """
        try:
            auth = LakebaseAuth()
            ws = auth.workspace_client
            ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/branches/{params.branch_name}/computes/primary/restart",
            )
            return json.dumps(
                {
                    "status": "restarting",
                    "message": (
                        "Compute is restarting. Active connections will be interrupted. "
                        "Reconnect in ~10-30 seconds."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_create_read_replica",
        annotations={
            "title": "Create Read Replica",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def lakebase_create_read_replica(
        params: CreateReadReplicaInput,
    ) -> str:
        """Create a read replica for a Lakebase branch.

        Read replicas share the same storage layer — no data duplication.
        Ideal for:
        - Offloading analytics/reporting queries from the primary
        - Agent read-heavy workloads (data exploration, profiling)
        - Horizontal read scaling for high-concurrency applications

        The replica gets its own autoscaling compute (independent from primary).
        """
        try:
            if params.max_cu - params.min_cu > 8:
                return (
                    f"Error: Autoscaling range too wide. Max spread is 8 CU. "
                    f"Try max_cu={params.min_cu + 8}."
                )
            auth = LakebaseAuth()
            ws = auth.workspace_client
            result = ws.api_client.do(
                "POST",
                f"/api/2.0/lakebase/projects/{params.project_name}"
                f"/branches/{params.branch_name}/computes",
                body={
                    "compute_type": "read_replica",
                    "min_cu": params.min_cu,
                    "max_cu": params.max_cu,
                },
            )
            return json.dumps(
                {
                    "status": "creating",
                    "compute_type": "read_replica",
                    "min_cu": params.min_cu,
                    "max_cu": params.max_cu,
                    "message": (
                        "Read replica is being created. It shares storage with "
                        "the primary compute (no data duplication). "
                        "Use lakebase_get_compute_status to check progress."
                    ),
                },
                indent=2,
            )
        except Exception as e:
            return handle_error(e)
