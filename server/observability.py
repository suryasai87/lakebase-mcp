"""End-to-end observability for Lakebase MCP Server.

Collects timing metrics for tool calls, SQL queries, Data API requests,
and connection acquisition. Uses an in-memory ring buffer (bounded memory)
with no external dependencies.

Metrics flow:
  tool call → (optional SQL / Data API sub-operation) → response
  Each span is captured with operation type, name, duration, and metadata.
"""

import time
import threading
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class OperationType(str, Enum):
    TOOL_CALL = "tool_call"
    SQL_QUERY = "sql_query"
    SQL_READONLY = "sql_readonly"
    DATA_API = "data_api"
    CONNECTION = "connection"


@dataclass
class Span:
    """A single timed operation."""
    op_type: OperationType
    name: str
    duration_ms: float
    timestamp: float
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


_MAX_SPANS = 2000
_lock = threading.Lock()
_spans: deque[Span] = deque(maxlen=_MAX_SPANS)
_counters: dict[str, int] = defaultdict(int)
_error_counters: dict[str, int] = defaultdict(int)
_server_start_time: float = time.time()


def record_span(
    op_type: OperationType,
    name: str,
    duration_ms: float,
    success: bool = True,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    span = Span(
        op_type=op_type,
        name=name,
        duration_ms=duration_ms,
        timestamp=time.time(),
        success=success,
        metadata=metadata or {},
    )
    with _lock:
        _spans.append(span)
        key = f"{op_type.value}:{name}"
        _counters[key] += 1
        if not success:
            _error_counters[key] += 1


def get_spans(
    op_type: Optional[OperationType] = None,
    name: Optional[str] = None,
    last_n: int = 100,
) -> list[Span]:
    with _lock:
        filtered = list(_spans)
    if op_type:
        filtered = [s for s in filtered if s.op_type == op_type]
    if name:
        filtered = [s for s in filtered if s.name == name]
    return filtered[-last_n:]


def get_latency_stats(
    op_type: Optional[OperationType] = None,
    last_seconds: int = 300,
) -> dict[str, dict[str, Any]]:
    """Compute p50/p90/p99/mean/max per operation name within the time window."""
    cutoff = time.time() - last_seconds
    with _lock:
        spans = [s for s in _spans if s.timestamp >= cutoff]
    if op_type:
        spans = [s for s in spans if s.op_type == op_type]

    grouped: dict[str, list[float]] = defaultdict(list)
    for s in spans:
        key = f"{s.op_type.value}:{s.name}"
        grouped[key].append(s.duration_ms)

    result: dict[str, dict[str, Any]] = {}
    for key, durations in sorted(grouped.items()):
        durations.sort()
        n = len(durations)
        result[key] = {
            "count": n,
            "mean_ms": round(statistics.mean(durations), 2),
            "p50_ms": round(durations[n // 2], 2),
            "p90_ms": round(durations[int(n * 0.9)], 2) if n >= 2 else round(durations[-1], 2),
            "p99_ms": round(durations[int(n * 0.99)], 2) if n >= 2 else round(durations[-1], 2),
            "max_ms": round(max(durations), 2),
            "min_ms": round(min(durations), 2),
        }
    return result


def get_slow_operations(threshold_ms: float = 1000, last_n: int = 20) -> list[dict]:
    """Return the slowest operations above the threshold."""
    with _lock:
        slow = [s for s in _spans if s.duration_ms >= threshold_ms]
    slow.sort(key=lambda s: s.duration_ms, reverse=True)
    return [
        {
            "op_type": s.op_type.value,
            "name": s.name,
            "duration_ms": round(s.duration_ms, 2),
            "success": s.success,
            "metadata": s.metadata,
            "timestamp": s.timestamp,
        }
        for s in slow[:last_n]
    ]


def get_error_summary() -> dict[str, dict[str, int]]:
    """Return error counts per operation alongside total counts."""
    with _lock:
        total = dict(_counters)
        errors = dict(_error_counters)
    result = {}
    for key in sorted(set(total) | set(errors)):
        result[key] = {
            "total": total.get(key, 0),
            "errors": errors.get(key, 0),
        }
    return result


def get_server_summary() -> dict[str, Any]:
    """High-level server health summary."""
    now = time.time()
    uptime = now - _server_start_time
    with _lock:
        total_spans = len(_spans)
        total_errors = sum(_error_counters.values())
        total_calls = sum(_counters.values())

    recent_cutoff = now - 60
    with _lock:
        recent = [s for s in _spans if s.timestamp >= recent_cutoff]
    recent_durations = [s.duration_ms for s in recent]

    return {
        "uptime_seconds": round(uptime, 1),
        "total_operations": total_calls,
        "total_errors": total_errors,
        "error_rate_pct": round(total_errors / total_calls * 100, 2) if total_calls else 0,
        "buffer_usage": f"{total_spans}/{_MAX_SPANS}",
        "last_60s": {
            "operations": len(recent),
            "mean_latency_ms": round(statistics.mean(recent_durations), 2) if recent_durations else 0,
            "max_latency_ms": round(max(recent_durations), 2) if recent_durations else 0,
        },
    }


def reset_metrics() -> dict[str, int]:
    """Clear all collected metrics. Returns counts before reset."""
    global _server_start_time
    with _lock:
        counts = {
            "spans_cleared": len(_spans),
            "counters_cleared": sum(_counters.values()),
        }
        _spans.clear()
        _counters.clear()
        _error_counters.clear()
        _server_start_time = time.time()
    return counts
