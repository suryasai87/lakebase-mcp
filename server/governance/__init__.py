"""Fine-grained governance for Lakebase MCP Server.

Provides dual-layer access control:
- SQL statement governance (sqlglot-based parsing with 17 statement types)
- Tool-level access control (per-tool allow/deny with pre-built profiles)
"""
