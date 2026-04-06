"""Replication and WAL monitoring tools (GAP-7, GAP-10).

GAP-7: pg_stat_replication and pg_stat_wal monitoring.
GAP-10: WAL-based CDC (wal2delta) monitoring via replication slots.
"""
from mcp.server.fastmcp import FastMCP
from server.db import pool
from server.utils.errors import handle_error
from server.utils.formatting import format_query_results


def register_monitoring_tools(mcp: FastMCP):

    @mcp.tool(
        name="lakebase_replication_status",
        annotations={
            "title": "Replication Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_replication_status() -> str:
        """Query pg_stat_replication for streaming replication status.

        Returns replication lag, connection state, and LSN positions
        (sent, write, flush, replay) for each connected standby.
        Useful for monitoring replication health and diagnosing lag.
        """
        try:
            sql = """
                SELECT
                    pid,
                    usename,
                    application_name,
                    client_addr::text,
                    state,
                    sent_lsn::text,
                    write_lsn::text,
                    flush_lsn::text,
                    replay_lsn::text,
                    COALESCE(
                        pg_wal_lsn_diff(sent_lsn, replay_lsn)::bigint, 0
                    ) AS replay_lag_bytes,
                    COALESCE(
                        pg_wal_lsn_diff(sent_lsn, write_lsn)::bigint, 0
                    ) AS write_lag_bytes,
                    pg_size_pretty(
                        COALESCE(pg_wal_lsn_diff(sent_lsn, replay_lsn), 0)
                    ) AS replay_lag_pretty,
                    sync_state,
                    reply_time::text
                FROM pg_stat_replication
                ORDER BY application_name
            """
            rows = await pool.execute_readonly(
                sql, tool_name="lakebase_replication_status"
            )
            if not rows:
                return (
                    "_No active replication connections found._ "
                    "This is expected if no standbys or read replicas are configured."
                )
            return "## Replication Status\n\n" + format_query_results(rows)
        except Exception as e:
            return handle_error(e)

    @mcp.tool(
        name="lakebase_wal_statistics",
        annotations={
            "title": "WAL Statistics",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_wal_statistics() -> str:
        """Query pg_stat_wal for WAL generation rate, buffer usage, and sync stats.

        Returns cumulative WAL statistics including records generated, bytes
        written, number of full-page images, buffer hits/misses, and sync
        timing. Useful for understanding write throughput and I/O pressure.
        """
        try:
            sql = """
                SELECT
                    wal_records,
                    wal_fpi,
                    wal_bytes,
                    pg_size_pretty(wal_bytes) AS wal_bytes_pretty,
                    wal_buffers_full,
                    wal_write,
                    wal_sync,
                    wal_write_time,
                    wal_sync_time,
                    stats_reset::text
                FROM pg_stat_wal
            """
            rows = await pool.execute_readonly(
                sql, tool_name="lakebase_wal_statistics"
            )
            if not rows:
                return (
                    "_No WAL statistics available._ "
                    "The pg_stat_wal view may not be supported on this PostgreSQL version (requires 14+)."
                )
            return "## WAL Statistics\n\n" + format_query_results(rows)
        except Exception as e:
            # pg_stat_wal is PG14+; older versions will raise UndefinedTable
            error_msg = str(e).lower()
            if "undefined_table" in error_msg or "does not exist" in error_msg:
                return (
                    "_pg_stat_wal is not available._ "
                    "This view requires PostgreSQL 14 or later."
                )
            return handle_error(e)

    @mcp.tool(
        name="lakebase_cdc_monitor",
        annotations={
            "title": "CDC / wal2delta Monitor",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def lakebase_cdc_monitor() -> str:
        """Monitor WAL-based CDC (wal2delta) activity on Lakebase.

        Checks replication slots for CDC consumers, WAL retention,
        estimated lag in bytes, and active wal2delta worker processes.
        Useful for verifying CDC pipelines are consuming changes and
        not falling behind.
        """
        try:
            sections: list[str] = []

            # 1. Replication slots (CDC consumers)
            slots_sql = """
                SELECT
                    slot_name,
                    plugin,
                    slot_type,
                    active,
                    restart_lsn::text,
                    confirmed_flush_lsn::text,
                    pg_size_pretty(
                        pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
                    ) AS retained_wal,
                    pg_wal_lsn_diff(
                        pg_current_wal_lsn(), restart_lsn
                    )::bigint AS retained_wal_bytes,
                    wal_status
                FROM pg_replication_slots
                ORDER BY slot_name
            """
            slots = await pool.execute_readonly(
                slots_sql, tool_name="lakebase_cdc_monitor"
            )
            if slots:
                sections.append(
                    "### Replication Slots\n\n" + format_query_results(slots)
                )
            else:
                sections.append(
                    "### Replication Slots\n\n"
                    "_No replication slots found._ "
                    "CDC (wal2delta) does not appear to be configured."
                )

            # 2. Active wal2delta worker processes
            workers_sql = """
                SELECT
                    pid,
                    application_name,
                    backend_type,
                    state,
                    query,
                    backend_start::text,
                    state_change::text
                FROM pg_stat_activity
                WHERE application_name ILIKE '%wal2delta%'
                   OR application_name ILIKE '%cdc%'
                   OR backend_type = 'walsender'
                ORDER BY backend_start
            """
            workers = await pool.execute_readonly(
                workers_sql, tool_name="lakebase_cdc_monitor"
            )
            if workers:
                sections.append(
                    "### CDC Worker Processes\n\n" + format_query_results(workers)
                )
            else:
                sections.append(
                    "### CDC Worker Processes\n\n"
                    "_No active wal2delta or CDC worker processes found._"
                )

            # 3. Current WAL position for reference
            wal_pos_sql = """
                SELECT
                    pg_current_wal_lsn()::text AS current_wal_lsn,
                    pg_walfile_name(pg_current_wal_lsn()) AS current_wal_file
            """
            wal_pos = await pool.execute_readonly(
                wal_pos_sql, tool_name="lakebase_cdc_monitor"
            )
            if wal_pos:
                sections.append(
                    "### Current WAL Position\n\n" + format_query_results(wal_pos)
                )

            return "## CDC / wal2delta Monitor\n\n" + "\n\n".join(sections)
        except Exception as e:
            return handle_error(e)
