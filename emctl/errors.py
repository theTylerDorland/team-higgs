"""Typed errors and their exit codes.

Every emctl error subclasses :class:`click.ClickException`, so Click prints a
clean ``Error: <message>`` to stderr and exits with the mapped code — both for
real invocations and under the test runner. Raw SQL, tracebacks, and
connection strings never reach stdout or stderr: database exceptions are
translated to these types with generic messages before they surface.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import click
import psycopg


class EmctlError(click.ClickException):
    """Base error. Generic failures exit 1."""

    exit_code = 1


class ConfigError(EmctlError):
    """Missing or invalid configuration."""

    exit_code = 5


class ValidationError(EmctlError):
    """Bad flag, enum, or input file."""

    exit_code = 2


class NotFoundError(EmctlError):
    """A referenced row does not exist."""

    exit_code = 3


class ConflictError(EmctlError):
    """A unique or foreign-key constraint was violated."""

    exit_code = 4


def _constraint_detail(exc: psycopg.Error, fallback: str) -> str:
    constraint = getattr(exc.diag, "constraint_name", None)
    if constraint:
        return f"{fallback} ({constraint})"
    return fallback


@contextmanager
def map_db_errors() -> Iterator[None]:
    """Translate psycopg errors into typed :class:`EmctlError` variants.

    Only the constraint name (safe, useful) is surfaced — never the failing
    value, the statement, or the connection string.
    """
    try:
        yield
    except psycopg.errors.UniqueViolation as exc:
        raise ConflictError(
            _constraint_detail(exc, "value violates a unique constraint")
        ) from exc
    except psycopg.errors.ForeignKeyViolation as exc:
        raise ConflictError(
            _constraint_detail(exc, "referenced row does not exist")
        ) from exc
    except psycopg.errors.CheckViolation as exc:
        raise ValidationError(
            _constraint_detail(exc, "value violates a check constraint")
        ) from exc
    except psycopg.errors.ReadOnlySqlTransaction as exc:
        raise EmctlError(
            "metric definition attempted to write inside a READ ONLY transaction"
        ) from exc
    except psycopg.Error as exc:
        raise EmctlError("database error") from exc
