import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _enforce_sqlite_integrity(dbapi_connection, _connection_record):
    """Enable the integrity guarantees declared by the SQLite schema.

    SQLite keeps foreign-key enforcement disabled for every new connection
    unless the application explicitly enables it.  Our models already declare
    the relationships and production snapshots are checked with
    ``foreign_key_check`` before release, so leaving the runtime pragma off
    would turn those constraints into documentation only.  The concrete
    ``sqlite3.Connection`` check keeps this hook a no-op for DM8 and any future
    non-SQLite validation profile.
    """

    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
    finally:
        cursor.close()


db = SQLAlchemy()
migrate = Migrate(compare_type=True)


@event.listens_for(Engine, "reset")
def _release_unfinished_sqlite_transaction(dbapi_connection, _record, _state):
    """Never return SQLite's failed COMMIT transaction to the connection pool.

    SQLITE_BUSY at COMMIT leaves the DBAPI transaction open. SQLAlchemy can
    already consider its transaction reset when Session.close() returns the
    connection, so its default reset may skip the driver rollback. That retains
    a pending write lock across unrelated requests. Only roll back a remaining
    driver transaction at pool return; do not retry or change successful commits.
    Other database drivers and SQLite runtime PRAGMAs are unchanged.
    """
    if isinstance(dbapi_connection, sqlite3.Connection) and dbapi_connection.in_transaction:
        dbapi_connection.rollback()
