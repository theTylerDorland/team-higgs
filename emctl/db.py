"""Connection and transaction lifecycle.

Owns psycopg 3 connections and the single-transaction-per-command contract.
Repositories receive a :data:`Conn` and never open their own connections or
read the environment.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from emctl.config import database_url
from emctl.errors import map_db_errors

Conn = psycopg.Connection[dict[str, Any]]


@contextmanager
def transaction(*, read_only: bool = False) -> Iterator[Conn]:
    """Yield a connection wrapped in one transaction.

    Commits on clean exit, rolls back on any exception. When ``read_only`` is
    set the transaction cannot mutate state — used by ``metric report`` so an
    operator-authored definition can only ever read.
    """
    conn: Conn = psycopg.connect(database_url(), row_factory=dict_row)
    try:
        if read_only:
            # DO NOT REMOVE: for `metric report` this READ ONLY transaction is
            # the load-bearing control that prevents a stored definition from
            # writing (incl. inside PL/pgSQL DO blocks / functions). SET LOCAL
            # ROLE in metrics.report is bypassable; this is not. See
            # docs/stack-backend.md.
            conn.read_only = True
        with conn, map_db_errors():
            yield conn
    finally:
        conn.close()
