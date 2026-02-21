"""Unit tests for response formatting."""
import json
import pytest
from server.utils.formatting import (
    format_query_results,
    format_table_list,
    format_schema_info,
    ResponseFormat,
)


class TestQueryResultFormatting:
    def test_empty_results_markdown(self):
        result = format_query_results([], fmt=ResponseFormat.MARKDOWN)
        assert "No results" in result

    def test_results_markdown_table(self, sample_rows):
        result = format_query_results(sample_rows)
        assert "2 row(s)" in result
        assert "Alice" in result
        assert "| id |" in result

    def test_results_json(self, sample_rows):
        result = format_query_results(sample_rows, fmt=ResponseFormat.JSON)
        data = json.loads(result)
        assert data["row_count"] == 2
        assert len(data["rows"]) == 2

    def test_truncation_at_50(self):
        rows = [{"id": i} for i in range(100)]
        result = format_query_results(rows)
        assert "...and 50 more rows" in result


class TestSchemaFormatting:
    def test_schema_info_markdown(self, sample_columns):
        result = format_schema_info(sample_columns, "public.users")
        assert "public.users" in result
        assert "integer" in result
        assert "character varying" in result

    def test_schema_info_json(self, sample_columns):
        result = format_schema_info(
            sample_columns, "public.users", fmt=ResponseFormat.JSON
        )
        data = json.loads(result)
        assert data["table"] == "public.users"
        assert len(data["columns"]) == 3
