"""Parameterized CRUD helpers shared by the table repositories.

Column and table names are supplied by the repo modules as fixed literals and
composed with :mod:`psycopg.sql` identifiers; every value travels as a bound
placeholder. No SQL is assembled from user input by string concatenation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg import sql

from emctl.db import Conn
from emctl.errors import NotFoundError

Row = dict[str, Any]


def insert(conn: Conn, table: str, values: dict[str, Any]) -> Row:
    columns = list(values)
    query = sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES ({vals}) RETURNING *"
    ).format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    row = conn.execute(query, list(values.values())).fetchone()
    assert row is not None  # RETURNING on a successful INSERT always yields a row
    return row


def get(conn: Conn, table: str, entity: str, id_: int) -> Row:
    query = sql.SQL("SELECT * FROM {} WHERE id = %s").format(sql.Identifier(table))
    row = conn.execute(query, (id_,)).fetchone()
    if row is None:
        raise NotFoundError(f"{entity} {id_} not found")
    return row


def update(
    conn: Conn,
    table: str,
    entity: str,
    id_: int,
    values: dict[str, Any],
    *,
    extra: Sequence[sql.Composable] | None = None,
) -> Row:
    """Update by id and return the new row. ``extra`` carries assignments that
    take no bound value (e.g. ``updated_at = now()``)."""
    assignments: list[sql.Composable] = [
        sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
        for col in values
    ]
    if extra:
        assignments.extend(extra)
    if not assignments:
        return get(conn, table, entity, id_)
    query = sql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING *").format(
        sql.Identifier(table),
        sql.SQL(", ").join(assignments),
    )
    row = conn.execute(query, [*values.values(), id_]).fetchone()
    if row is None:
        raise NotFoundError(f"{entity} {id_} not found")
    return row


def select(
    conn: Conn,
    table: str,
    *,
    where: dict[str, Any] | None = None,
    order_by: str = "id",
) -> list[Row]:
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table))
    params: list[Any] = []
    if where:
        conditions = [
            sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
            for col in where
        ]
        query = query + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
        params.extend(where.values())
    query = query + sql.SQL(" ORDER BY {}").format(sql.Identifier(order_by))
    return list(conn.execute(query, params).fetchall())
