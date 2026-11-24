"""Small compatibility adapters for supported database dialects."""

from sqlalchemy import Integer, String
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import operators
from sqlalchemy.sql.ddl import CreateColumn
from sqlalchemy.sql.elements import BinaryExpression, False_, True_

_installed = False


def _compile_dm_create_column(element, compiler, **kwargs):
    """Work around dmSQLAlchemy treating ``autoincrement='auto'`` as disabled."""
    column = element.element
    original = column.autoincrement
    primary_key = list(column.table.primary_key.columns)
    needs_identity = (
        original == "auto"
        and len(primary_key) == 1
        and primary_key[0] is column
        and isinstance(column.type, Integer)
    )
    if needs_identity:
        column.autoincrement = True
    try:
        return compiler.visit_create_column(element, **kwargs)
    finally:
        column.autoincrement = original


def _compile_dm_string(type_, compiler, **kwargs):
    """DM 8.1.3.162+ removed LENGTH_IN_CHAR; keep model lengths character-based."""
    if type_.length is None:
        return "VARCHAR"
    return f"VARCHAR({int(type_.length)} CHAR)"


def _compile_dm_binary(element, compiler, **kwargs):
    """DM8 rejects ``IS 0/1`` while dmSQLAlchemy emits it for booleans."""
    if isinstance(element.right, (True_, False_)):
        if element.operator is operators.is_:
            return compiler.visit_binary(element, override_operator=operators.eq, **kwargs)
        if element.operator is operators.is_not:
            return compiler.visit_binary(element, override_operator=operators.ne, **kwargs)
    return compiler.visit_binary(element, **kwargs)


def install_database_compatibility() -> None:
    global _installed
    if _installed:
        return
    compiles(CreateColumn, "dm")(_compile_dm_create_column)
    compiles(String, "dm")(_compile_dm_string)
    compiles(BinaryExpression, "dm")(_compile_dm_binary)
    _installed = True
