"""Centralized error handling with actionable messages.

Merged: base error handlers + Gap 5 (autoscaling-state-aware messages).
"""
import psycopg


def handle_error(e: Exception) -> str:
    """Return a human-readable, actionable error message.

    Distinguishes between:
    - Scale-to-zero wake-up (transient — retry)
    - Autoscaling in progress (transient — retry)
    - Compute restart (transient — wait longer)
    - Permission / syntax / infrastructure errors
    """
    # --- Autoscaling-specific errors (Gap 5) ---

    if isinstance(e, ConnectionError) and "scale-to-zero" in str(e).lower():
        return (
            "Error: Lakebase compute is waking up from scale-to-zero. "
            "Retries exhausted. The compute should be active within 10-30 seconds. "
            "Try your request again shortly, or use lakebase_get_compute_status to check."
        )

    if isinstance(e, psycopg.OperationalError):
        msg = str(e).lower()
        if "connection refused" in msg or "could not connect" in msg:
            return (
                "Error: Cannot connect to Lakebase compute. Possible causes:\n"
                "- Compute is suspended (scale-to-zero) and waking up — retry in a few seconds\n"
                "- Compute is restarting after a configuration change\n"
                "- Autoscaling in progress\n"
                "Use lakebase_get_compute_status to check the current state."
            )
        if "terminating connection" in msg or "server closed" in msg:
            return (
                "Error: Connection was terminated. This can happen during:\n"
                "- Compute restart\n"
                "- Autoscaling adjustments (rare)\n"
                "Retry your query — the connection pool will reconnect automatically."
            )

    # --- Standard Lakebase/Postgres errors ---

    if isinstance(e, psycopg.errors.InsufficientPrivilege):
        return (
            "Error: Permission denied. Your Unity Catalog permissions do not allow this operation. "
            "Contact your workspace admin to request access."
        )

    if isinstance(e, psycopg.errors.UndefinedTable):
        table = str(e).split('"')[1] if '"' in str(e) else "unknown"
        return (
            f"Error: Table '{table}' does not exist. "
            "Use lakebase_list_tables to discover available tables, "
            "or lakebase_list_schemas to check schema names."
        )

    if isinstance(e, psycopg.errors.SyntaxError):
        return f"Error: SQL syntax error — {str(e).strip()}. Check your query and try again."

    if isinstance(e, psycopg.errors.QueryCanceled):
        return "Error: Query timed out. Try limiting rows with LIMIT or simplifying the query."

    if isinstance(e, psycopg.errors.ConnectionException):
        return (
            "Error: Lost connection to Lakebase. The compute may be scaling or restarting — "
            "retry in a few seconds. Use lakebase_get_compute_status to check."
        )

    if isinstance(e, TimeoutError):
        return (
            "Error: Connection timed out. The Lakebase compute may be starting up "
            "(scale-to-zero wake-up). Retry shortly or check compute status."
        )

    return f"Error: {type(e).__name__} — {str(e)}"
