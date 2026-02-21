"""Response formatting helpers."""
import json
from enum import Enum
from typing import Any


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


def format_query_results(
    rows: list[dict],
    columns: list[str] = None,
    fmt: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps(
            {"row_count": len(rows), "rows": rows}, indent=2, default=str
        )
    if not rows:
        return "_No results returned._"
    cols = columns or list(rows[0].keys())
    lines = [f"**{len(rows)} row(s) returned**\n"]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for row in rows[:50]:
        vals = [str(row.get(c, "")) for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    if len(rows) > 50:
        lines.append(f"\n_...and {len(rows) - 50} more rows (use LIMIT to control)_")
    return "\n".join(lines)


def format_table_list(
    tables: list[dict], fmt: ResponseFormat = ResponseFormat.MARKDOWN
) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps(tables, indent=2, default=str)
    if not tables:
        return "_No tables found._"
    lines = ["## Tables\n"]
    for t in tables:
        name = t.get("table_name", t.get("tablename", "unknown"))
        schema = t.get("schemaname", "public")
        lines.append(f"- **{schema}.{name}**")
        if t.get("description"):
            lines.append(f"  - {t['description']}")
    return "\n".join(lines)


def format_schema_info(
    columns: list[dict],
    table_name: str,
    fmt: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps(
            {"table": table_name, "columns": columns}, indent=2, default=str
        )
    lines = [f"## Schema: `{table_name}`\n"]
    lines.append("| Column | Type | Nullable | Default |")
    lines.append("| --- | --- | --- | --- |")
    for c in columns:
        lines.append(
            f"| {c['column_name']} | {c['data_type']} | "
            f"{c.get('is_nullable', 'YES')} | {c.get('column_default', '')} |"
        )
    return "\n".join(lines)
