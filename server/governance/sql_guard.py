"""SQL statement governance using sqlglot AST parsing.

Replaces regex WRITE_PATTERNS with proper SQL parsing that handles:
- CTEs (WITH ... INSERT INTO)
- Subqueries
- Multi-statement SQL
- Dialect-specific syntax (Postgres)
"""
import re
import logging
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)


class SQLStatementType(str, Enum):
    """All 17 SQL statement types with governance."""

    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    CREATE = "create"
    DROP = "drop"
    ALTER = "alter"
    MERGE = "merge"
    TRUNCATE = "truncate"
    GRANT = "grant"
    REVOKE = "revoke"
    USE = "use"
    SHOW = "show"
    DESCRIBE = "describe"
    EXPLAIN = "explain"
    SET = "set"
    CALL = "call"


# Map sqlglot expression types to our statement types
# Note: sqlglot v28+ uses exp.Alter (not AlterTable), exp.TruncateTable, exp.Grant
_EXPRESSION_MAP: dict[type, SQLStatementType] = {
    exp.Select: SQLStatementType.SELECT,
    exp.Union: SQLStatementType.SELECT,
    exp.Intersect: SQLStatementType.SELECT,
    exp.Except: SQLStatementType.SELECT,
    exp.Insert: SQLStatementType.INSERT,
    exp.Update: SQLStatementType.UPDATE,
    exp.Delete: SQLStatementType.DELETE,
    exp.Create: SQLStatementType.CREATE,
    exp.Drop: SQLStatementType.DROP,
    exp.Alter: SQLStatementType.ALTER,
    exp.AlterColumn: SQLStatementType.ALTER,
    exp.Merge: SQLStatementType.MERGE,
    exp.TruncateTable: SQLStatementType.TRUNCATE,
    exp.Grant: SQLStatementType.GRANT,
}

# Pre-built profiles
PROFILES: dict[str, set[SQLStatementType]] = {
    "read_only": {
        SQLStatementType.SELECT,
        SQLStatementType.SHOW,
        SQLStatementType.DESCRIBE,
        SQLStatementType.EXPLAIN,
    },
    "analyst": {
        SQLStatementType.SELECT,
        SQLStatementType.SHOW,
        SQLStatementType.DESCRIBE,
        SQLStatementType.EXPLAIN,
        SQLStatementType.INSERT,
        SQLStatementType.SET,
    },
    "developer": {
        SQLStatementType.SELECT,
        SQLStatementType.INSERT,
        SQLStatementType.UPDATE,
        SQLStatementType.DELETE,
        SQLStatementType.CREATE,
        SQLStatementType.ALTER,
        SQLStatementType.SHOW,
        SQLStatementType.DESCRIBE,
        SQLStatementType.EXPLAIN,
        SQLStatementType.SET,
        SQLStatementType.CALL,
    },
    "admin": set(SQLStatementType),
}


@dataclass
class SQLCheckResult:
    """Result of checking a SQL statement against the policy."""

    allowed: bool
    statement_type: Optional[SQLStatementType] = None
    error_message: Optional[str] = None
    parsed_types: list[SQLStatementType] = field(default_factory=list)


class SQLGovernor:
    """Parses SQL and enforces statement-type permissions.

    Uses sqlglot with postgres dialect for accurate parsing.
    Falls back to regex for unparseable statements (defense-in-depth).
    """

    def __init__(self, allowed_types: set[SQLStatementType]):
        self._allowed = allowed_types

    @property
    def allowed_types(self) -> set[SQLStatementType]:
        return self._allowed.copy()

    def classify(self, sql: str) -> list[SQLStatementType]:
        """Classify a SQL string into statement types.

        Handles multi-statement SQL (semicolon-separated).
        Uses postgres dialect for accurate Lakebase parsing.
        """
        types: list[SQLStatementType] = []
        try:
            statements = sqlglot.parse(sql, dialect="postgres")
            for stmt in statements:
                if stmt is None:
                    continue
                stmt_type = self._classify_expression(stmt)
                if stmt_type:
                    types.append(stmt_type)
                else:
                    # Try regex fallback for this individual statement
                    stmt_sql = stmt.sql(dialect="postgres")
                    fallback = self._regex_fallback(stmt_sql)
                    if fallback:
                        types.append(fallback)
        except sqlglot.errors.ParseError:
            # Full fallback: use regex for unparseable SQL
            stmt_type = self._regex_fallback(sql)
            if stmt_type:
                types.append(stmt_type)
            else:
                logger.warning(f"Could not parse SQL, will deny: {sql[:100]}")
        return types

    def check(self, sql: str) -> SQLCheckResult:
        """Check if SQL is allowed by current policy."""
        types = self.classify(sql)

        if not types:
            return SQLCheckResult(
                allowed=False,
                error_message="Could not determine SQL statement type.",
            )

        for stmt_type in types:
            if stmt_type not in self._allowed:
                allowed_list = sorted(t.value for t in self._allowed)
                return SQLCheckResult(
                    allowed=False,
                    statement_type=stmt_type,
                    parsed_types=types,
                    error_message=(
                        f"Statement type '{stmt_type.value}' is not allowed. "
                        f"Permitted types: {', '.join(allowed_list)}"
                    ),
                )

        return SQLCheckResult(
            allowed=True,
            statement_type=types[0],
            parsed_types=types,
        )

    def is_write(self, sql: str) -> bool:
        """Check if SQL contains any write operations (for routing decisions)."""
        read_types = {
            SQLStatementType.SELECT,
            SQLStatementType.SHOW,
            SQLStatementType.DESCRIBE,
            SQLStatementType.EXPLAIN,
            SQLStatementType.SET,
        }
        types = self.classify(sql)
        return any(t not in read_types for t in types)

    def _classify_expression(
        self, node: exp.Expression
    ) -> Optional[SQLStatementType]:
        """Map a sqlglot expression node to a SQLStatementType."""
        for expr_type, stmt_type in _EXPRESSION_MAP.items():
            if isinstance(node, expr_type):
                return stmt_type

        # Handle Command expressions (EXPLAIN, SHOW, REVOKE, CALL, etc.)
        # In sqlglot v28+, EXPLAIN and SHOW are parsed as Command nodes.
        if isinstance(node, exp.Command):
            cmd = node.this.upper() if isinstance(node.this, str) else ""
            cmd_map = {
                "EXPLAIN": SQLStatementType.EXPLAIN,
                "REVOKE": SQLStatementType.REVOKE,
                "SHOW": SQLStatementType.SHOW,
                "SET": SQLStatementType.SET,
                "CALL": SQLStatementType.CALL,
            }
            return cmd_map.get(cmd)

        # SetItem for SET statements
        if isinstance(node, exp.SetItem) or isinstance(node, exp.Set):
            return SQLStatementType.SET

        # Describe
        if isinstance(node, exp.Describe):
            return SQLStatementType.DESCRIBE

        # Use
        if isinstance(node, exp.Use):
            return SQLStatementType.USE

        logger.debug(f"Unrecognized expression type: {type(node).__name__}")
        return None

    def _regex_fallback(self, sql: str) -> Optional[SQLStatementType]:
        """Regex fallback for statements sqlglot cannot parse."""
        stripped = sql.strip().upper()
        patterns = [
            (r"^SELECT\b", SQLStatementType.SELECT),
            (r"^INSERT\b", SQLStatementType.INSERT),
            (r"^UPDATE\b", SQLStatementType.UPDATE),
            (r"^DELETE\b", SQLStatementType.DELETE),
            (r"^CREATE\b", SQLStatementType.CREATE),
            (r"^DROP\b", SQLStatementType.DROP),
            (r"^ALTER\b", SQLStatementType.ALTER),
            (r"^MERGE\b", SQLStatementType.MERGE),
            (r"^TRUNCATE\b", SQLStatementType.TRUNCATE),
            (r"^GRANT\b", SQLStatementType.GRANT),
            (r"^REVOKE\b", SQLStatementType.REVOKE),
            (r"^EXPLAIN\b", SQLStatementType.EXPLAIN),
            (r"^SHOW\b", SQLStatementType.SHOW),
            (r"^DESCRIBE\b", SQLStatementType.DESCRIBE),
            (r"^SET\b", SQLStatementType.SET),
            (r"^CALL\b", SQLStatementType.CALL),
            (r"^USE\b", SQLStatementType.USE),
            # CTE detection
            (r"^WITH\b.*\bSELECT\b", SQLStatementType.SELECT),
            (r"^WITH\b.*\bINSERT\b", SQLStatementType.INSERT),
            (r"^WITH\b.*\bUPDATE\b", SQLStatementType.UPDATE),
            (r"^WITH\b.*\bDELETE\b", SQLStatementType.DELETE),
        ]
        for pattern, stmt_type in patterns:
            if re.match(pattern, stripped, re.DOTALL):
                return stmt_type
        return None
