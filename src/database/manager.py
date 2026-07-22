"""
Database manager.

Provides a single interface for interacting with the SQLite database.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.core.paths import DATA_DIR


class DatabaseManager:
    """Simple SQLite database manager."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (DATA_DIR / "superstore.db")

    def execute(self, query: str, parameters: tuple = ()) -> list[dict[str, Any]]:
        """Execute a SELECT query and return rows as dictionaries."""

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row

        try:
            cursor = connection.execute(query, parameters)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        finally:
            connection.close()

    def execute_non_query(self, query: str, parameters: tuple = ()) -> None:
        """Execute INSERT/UPDATE/DELETE statements."""

        connection = sqlite3.connect(self.db_path)

        try:
            connection.execute(query, parameters)
            connection.commit()

        finally:
            connection.close()

    def table_exists(self, table_name: str) -> bool:

        query = """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name=?
        """

        rows = self.execute(query, (table_name,))
        return len(rows) > 0