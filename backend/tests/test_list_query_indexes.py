"""Index migration contracts on SQLite; real online DDL is measured separately."""
import importlib.util
from pathlib import Path
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

def migration():
    path=Path(__file__).parents[1]/'migrations/versions/d109f0112026_list_query_indexes.py'
    spec=importlib.util.spec_from_file_location('list_indexes',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_upgrade_idempotence_and_downgrade_preserve_data_and_unrelated_index():
    engine=sa.create_engine('sqlite:///:memory:');m=migration()
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE reports (id INTEGER PRIMARY KEY, department TEXT, status TEXT, owner TEXT)')
        conn.exec_driver_sql('CREATE TABLE operation_audits (id INTEGER PRIMARY KEY, object_type TEXT, object_id TEXT, action TEXT, success BOOLEAN, created_at DATETIME)')
        conn.exec_driver_sql("INSERT INTO reports VALUES (1,'D','S','O')")
        conn.exec_driver_sql('CREATE INDEX unrelated ON reports (id)')
        with Operations.context(MigrationContext.configure(conn)):
            m.upgrade();m.upgrade()
            for table,name,columns in m.INDEXES:
                found={i['name']:i for i in sa.inspect(conn).get_indexes(table)}
                assert tuple(found[name]['column_names'])==columns
            m.downgrade();m.downgrade()
        assert [i['name'] for i in sa.inspect(conn).get_indexes('reports')]==['unrelated']
        assert conn.exec_driver_sql('SELECT * FROM reports').all()==[(1,'D','S','O')]

def test_existing_name_with_wrong_definition_is_rejected():
    engine=sa.create_engine('sqlite:///:memory:');m=migration()
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE operation_audits (id INTEGER, object_type TEXT, object_id TEXT, action TEXT, success BOOLEAN, created_at DATETIME)')
        conn.exec_driver_sql('CREATE INDEX ix_oa_object_action ON operation_audits (id)')
        with Operations.context(MigrationContext.configure(conn)),pytest.raises(RuntimeError,match='definition mismatch'):
            m.upgrade()
