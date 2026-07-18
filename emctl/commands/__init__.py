"""Typer sub-apps, one per command group.

Commands are thin: validate input (Typer enums reject bad flags before any DB
round-trip), open one transaction, call a repository, hand the result to
:mod:`emctl.output`. Command modules never touch SQL.
"""
