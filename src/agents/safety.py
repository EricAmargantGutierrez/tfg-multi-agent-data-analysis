"""
src/agents/safety.py

Read-only SQL guard shared by every agent that lets an LLM write raw SQL
(SQL agent, Viz agent). The Analysis agent doesn't need this -- it never
lets the LLM write raw SQL text; see src/core/db.py::build_select.
"""
import re


class UnsafeSQLError(Exception):
    pass


FORBIDDEN = [
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "truncate", "attach", "detach", "vacuum", "pragma",
]


def validate_sql_readonly(sql: str) -> str:
    sql = sql.strip().rstrip(";")
    lower = sql.lower()

    if not (lower.startswith("select") or lower.startswith("with")):
        raise UnsafeSQLError("Only SELECT queries are allowed.")

    # Reject stacked statements by structure, not just by hoping the
    # second statement happens to contain a forbidden keyword.
    if ";" in sql:
        raise UnsafeSQLError("Multiple statements are not allowed.")

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", lower):
            raise UnsafeSQLError(f"Forbidden keyword: {word}")

    return sql
