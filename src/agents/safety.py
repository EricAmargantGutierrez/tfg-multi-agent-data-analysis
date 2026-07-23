import re


class UnsafeSQLError(Exception):
    pass


FORBIDDEN = [
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "truncate",
    "attach",
    "detach",
    "vacuum",
    "pragma",
]


def validate_sql_readonly(sql: str) -> str:

    sql = sql.strip().rstrip(";")

    lower = sql.lower()

    if not (lower.startswith("select") or lower.startswith("with")):
        raise UnsafeSQLError("Only SELECT queries are allowed.")

    for word in FORBIDDEN:

        if re.search(rf"\b{word}\b", lower):
            raise UnsafeSQLError(f"Forbidden keyword: {word}")

    return sql