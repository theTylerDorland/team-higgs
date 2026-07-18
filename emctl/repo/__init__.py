"""Data layer. One module per table plus cross-table status queries.

Repositories receive a connection and typed args, return plain dicts/lists,
never print, and never read the environment. All SQL is parameterized: values
travel as placeholders and identifiers are composed with ``psycopg.sql`` — no
query is built by string concatenation.
"""
