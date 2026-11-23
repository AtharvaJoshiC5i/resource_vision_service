from __future__ import annotations

from collections.abc import Iterator
import threading
import time
from contextlib import contextmanager
from typing import Any

import pyodbc

from app.config import Settings, get_settings


class DatabaseError(Exception):
    pass


def _rows(cursor: pyodbc.Cursor) -> list[dict[str, Any]]:
    """All rows as dicts. Column names are read once per result set, not once per row."""
    if cursor.description is None:
        return []
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Connection pool
#
# Opening an Azure SQL connection costs a TCP + TLS + login handshake (hundreds of ms). Every
# store call used to pay that. Connections are now kept open and reused; a connection that has
# been idle longer than _VALIDATE_AFTER_S is checked with a trivial query before reuse, and any
# connection that raised a driver error is discarded instead of returned.
# ---------------------------------------------------------------------------

_POOL_MAX = 8
_VALIDATE_AFTER_S = 60.0
_pool: list[tuple[pyodbc.Connection, float]] = []
_pool_lock = threading.Lock()
_pool_key: str | None = None


def _open(connection_string: str) -> pyodbc.Connection:
    try:
        return pyodbc.connect(connection_string, timeout=30)
    except pyodbc.Error as error:
        raise DatabaseError(f"Could not connect to Azure SQL: {error}") from error


def _healthy(connection: pyodbc.Connection) -> bool:
    try:
        connection.cursor().execute("SELECT 1").fetchone()
        return True
    except pyodbc.Error:
        return False


def _acquire(connection_string: str) -> pyodbc.Connection:
    global _pool_key
    with _pool_lock:
        if _pool_key != connection_string:  # settings changed: drop old connections
            for conn, _ in _pool:
                _close_quietly(conn)
            _pool.clear()
            _pool_key = connection_string
        while _pool:
            conn, last_used = _pool.pop()
            if time.monotonic() - last_used < _VALIDATE_AFTER_S:
                return conn
            if _healthy(conn):
                return conn
            _close_quietly(conn)
    return _open(connection_string)


def _release(connection: pyodbc.Connection, connection_string: str) -> None:
    try:
        connection.rollback()  # never hand an open transaction to the next caller
    except pyodbc.Error:
        _close_quietly(connection)
        return
    with _pool_lock:
        if _pool_key == connection_string and len(_pool) < _POOL_MAX:
            _pool.append((connection, time.monotonic()))
            return
    _close_quietly(connection)


def _close_quietly(connection: pyodbc.Connection) -> None:
    try:
        connection.close()
    except pyodbc.Error:
        pass


def close_pool() -> None:
    with _pool_lock:
        for conn, _ in _pool:
            _close_quietly(conn)
        _pool.clear()


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[pyodbc.Connection]:
    active_settings = settings or get_settings()

    try:
        connection_string = active_settings.build_connection_string()
    except ValueError as error:
        raise DatabaseError(str(error)) from error

    connection = _acquire(connection_string)
    healthy = True
    try:
        yield connection
    except (pyodbc.Error, DatabaseError):
        healthy = False
        raise
    finally:
        if healthy:
            _release(connection, connection_string)
        else:
            _close_quietly(connection)


def ping_database(settings: Settings | None = None) -> dict[str, str]:
    with connect(settings) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME() AS database_name, @@VERSION AS version")
        row = cursor.fetchone()
        if row is None:
            raise DatabaseError("Database ping returned no rows.")

        database_name = str(row.database_name)
        version = str(row.version).split("\n", maxsplit=1)[0]

        return {
            "database_name": database_name,
            "server_version": version,
        }


def fetch_table(
    table_name: str,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    active_settings = settings or get_settings()
    max_rows = active_settings.azure_sql_max_rows

    # Table names are fixed constants: not user input.
    allowed_tables = {
        "dbo.famstack_billable",
        "dbo.famstack_non_billable",
        "dbo.project_track_proposals_table",
    }

    if table_name not in allowed_tables:
        raise DatabaseError(f"Table access is not allowed: {table_name}")

    top_clause = f"TOP ({max_rows}) " if max_rows > 0 else ""

    query = f"SELECT {top_clause}* FROM {table_name}"

    with connect(active_settings) as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(query)
        except pyodbc.Error as error:
            raise DatabaseError(
                f"Query failed for {table_name}: {error}",
            ) from error

        return _rows(cursor)


def fetch_all(
    query: str,
    parameters: tuple[Any, ...] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    active_settings = settings or get_settings()
    max_rows = active_settings.azure_sql_max_rows

    wrapped_query = query.strip().rstrip(";")

    if max_rows > 0:
        wrapped_query = (
            f"SELECT TOP ({max_rows}) * FROM ({wrapped_query}) AS resource_vision_source"
        )

    with connect(active_settings) as connection:
        cursor = connection.cursor()
        try:
            if parameters:
                cursor.execute(wrapped_query, parameters)
            else:
                cursor.execute(wrapped_query)
        except pyodbc.Error as error:
            raise DatabaseError(f"Query failed: {error}") from error

        return _rows(cursor)


def fetch_rows(
    query: str,
    parameters: tuple[Any, ...] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Run a fixed, read-only query exactly as written (no TOP wrapper).

    Used by the Resource Vision engine, whose queries are plain SELECTs over
    the two source tables. Never pass user input as part of ``query``.
    """
    active_settings = settings or get_settings()

    with connect(active_settings) as connection:
        cursor = connection.cursor()
        try:
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)
        except pyodbc.Error as error:
            raise DatabaseError(f"Query failed: {error}") from error

        return _rows(cursor)
