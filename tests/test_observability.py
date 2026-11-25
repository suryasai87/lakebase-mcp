"""Test observability metrics collection — ring buffer, stats, error tracking."""

import time
import pytest
from server.observability import (
    OperationType,
    record_span,
    get_spans,
    get_latency_stats,
    get_slow_operations,
    get_error_summary,
    get_server_summary,
    reset_metrics,
)


@pytest.fixture(autouse=True)
def clean_metrics():
    """Reset metrics before and after each test."""
    reset_metrics()
    yield
    reset_metrics()


class TestRecordAndRetrieve:

    def test_record_single_span(self):
        record_span(OperationType.TOOL_CALL, "test_tool", 42.5)
        spans = get_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_tool"
        assert spans[0].duration_ms == 42.5
        assert spans[0].success is True

    def test_record_error_span(self):
        record_span(OperationType.SQL_QUERY, "bad_query", 100.0, success=False)
        spans = get_spans()
        assert len(spans) == 1
        assert spans[0].success is False

    def test_metadata_preserved(self):
        record_span(
            OperationType.DATA_API, "GET:public.users", 55.0,
            metadata={"status_code": 200, "method": "GET"},
        )
        spans = get_spans()
        assert spans[0].metadata["status_code"] == 200

    def test_filter_by_op_type(self):
        record_span(OperationType.TOOL_CALL, "tool_a", 10.0)
        record_span(OperationType.SQL_QUERY, "query_a", 20.0)
        record_span(OperationType.DATA_API, "api_a", 30.0)

        tool_spans = get_spans(op_type=OperationType.TOOL_CALL)
        assert len(tool_spans) == 1
        assert tool_spans[0].name == "tool_a"

    def test_filter_by_name(self):
        record_span(OperationType.TOOL_CALL, "tool_a", 10.0)
        record_span(OperationType.TOOL_CALL, "tool_b", 20.0)

        spans = get_spans(name="tool_a")
        assert len(spans) == 1

    def test_last_n_limit(self):
        for i in range(50):
            record_span(OperationType.TOOL_CALL, f"tool_{i}", float(i))
        spans = get_spans(last_n=5)
        assert len(spans) == 5
        assert spans[0].name == "tool_45"


class TestLatencyStats:

    def test_basic_stats(self):
        for d in [10.0, 20.0, 30.0, 40.0, 50.0]:
            record_span(OperationType.TOOL_CALL, "my_tool", d)

        stats = get_latency_stats(last_seconds=60)
        key = "tool_call:my_tool"
        assert key in stats
        assert stats[key]["count"] == 5
        assert stats[key]["mean_ms"] == 30.0
        assert stats[key]["min_ms"] == 10.0
        assert stats[key]["max_ms"] == 50.0

    def test_stats_filtered_by_op_type(self):
        record_span(OperationType.TOOL_CALL, "tool_a", 10.0)
        record_span(OperationType.SQL_QUERY, "query_a", 20.0)

        stats = get_latency_stats(op_type=OperationType.SQL_QUERY, last_seconds=60)
        assert "sql_query:query_a" in stats
        assert "tool_call:tool_a" not in stats

    def test_empty_stats(self):
        stats = get_latency_stats(last_seconds=60)
        assert stats == {}


class TestSlowOperations:

    def test_finds_slow_ops(self):
        record_span(OperationType.SQL_QUERY, "fast", 50.0)
        record_span(OperationType.SQL_QUERY, "slow", 2000.0)
        record_span(OperationType.SQL_QUERY, "medium", 500.0)

        slow = get_slow_operations(threshold_ms=1000)
        assert len(slow) == 1
        assert slow[0]["name"] == "slow"
        assert slow[0]["duration_ms"] == 2000.0

    def test_sorted_by_duration(self):
        record_span(OperationType.TOOL_CALL, "a", 1500.0)
        record_span(OperationType.TOOL_CALL, "b", 3000.0)
        record_span(OperationType.TOOL_CALL, "c", 2000.0)

        slow = get_slow_operations(threshold_ms=1000)
        durations = [op["duration_ms"] for op in slow]
        assert durations == [3000.0, 2000.0, 1500.0]

    def test_empty_when_all_fast(self):
        record_span(OperationType.TOOL_CALL, "fast", 10.0)
        assert get_slow_operations(threshold_ms=1000) == []


class TestErrorSummary:

    def test_error_counts(self):
        record_span(OperationType.TOOL_CALL, "tool_a", 10.0, success=True)
        record_span(OperationType.TOOL_CALL, "tool_a", 10.0, success=True)
        record_span(OperationType.TOOL_CALL, "tool_a", 10.0, success=False)

        summary = get_error_summary()
        key = "tool_call:tool_a"
        assert summary[key]["total"] == 3
        assert summary[key]["errors"] == 1

    def test_empty_summary(self):
        assert get_error_summary() == {}


class TestServerSummary:

    def test_basic_summary(self):
        record_span(OperationType.TOOL_CALL, "t", 10.0)
        record_span(OperationType.TOOL_CALL, "t", 20.0, success=False)

        s = get_server_summary()
        assert s["total_operations"] == 2
        assert s["total_errors"] == 1
        assert s["error_rate_pct"] == 50.0
        assert s["last_60s"]["operations"] == 2


class TestResetMetrics:

    def test_reset_clears_all(self):
        for i in range(10):
            record_span(OperationType.TOOL_CALL, "t", float(i))

        counts = reset_metrics()
        assert counts["spans_cleared"] == 10
        assert get_spans() == []
        assert get_error_summary() == {}


class TestRingBufferBound:

    def test_buffer_does_not_exceed_max(self):
        for i in range(3000):
            record_span(OperationType.TOOL_CALL, f"t_{i}", float(i))
        spans = get_spans(last_n=5000)
        assert len(spans) <= 2000
