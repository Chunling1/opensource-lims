"""Content must survive reporting projections without narrower storage fields."""
import importlib.util
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.dialects import mysql

from app.extensions import db
from app.models import Report, EquipmentItem, EquipmentUsageRecord, OperationAudit
from app.audit import add_operation_audit
from app.edit_concurrency import test_form_version as form_version
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)


def migration():
    path = Path(__file__).parents[1] / 'migrations/versions/b186f0112026_workflow_text_capacity.py'
    spec = importlib.util.spec_from_file_location('capacity_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mysql_storage_has_no_old_short_varchar_limits():
    # SQLite accepts overlong VARCHARs, so checking the production SQL type is
    # essential; a SQLite roundtrip alone would falsely pass the old model.
    for table, fields in migration().FIELDS.items():
        for field in fields:
            column = db.metadata.tables[table].c[field]
            assert column.type.compile(dialect=mysql.dialect()) == 'TEXT'


def test_existing_data_survives_upgrade_and_repeat(tmp_path):
    engine = sa.create_engine('sqlite:///' + str(tmp_path/'migration.db'))
    module = migration()
    with engine.begin() as connection:
        for table, names in module.FIELDS.items():
            columns = ', '.join(f'{name} VARCHAR(120)' for name in names)
            connection.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, {columns})')
            connection.execute(sa.text(f'INSERT INTO {table} (id, {names[0]}) VALUES (1, :value)'), {'value':'Existing 原数据'})
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.upgrade()
        for table, names in module.FIELDS.items():
            actual = {c['name']:c for c in sa.inspect(connection).get_columns(table)}
            assert all(isinstance(actual[n]['type'], sa.Text) for n in names)
            assert connection.execute(sa.text(f'SELECT {names[0]} FROM {table}')).scalar() == 'Existing 原数据'
        with pytest.raises(RuntimeError, match='narrowing'):
            module.downgrade()


def test_mysql_upgrade_emits_widening_ddl(monkeypatch):
    module = migration()
    class Inspector:
        def get_columns(self, table):
            return [{'name': name, 'type': sa.String(120), 'nullable': False}
                    for name in module.FIELDS[table]]
    monkeypatch.setattr(module.sa, 'inspect', lambda bind: Inspector())
    output = StringIO()
    context = MigrationContext.configure(dialect_name='mysql',
                                        opts={'as_sql': True, 'output_buffer': output})
    with Operations.context(context):
        module.upgrade()
    sql = output.getvalue()
    for table, names in module.FIELDS.items():
        for name in names:
            assert f'ALTER TABLE {table} MODIFY {name} TEXT NOT NULL' in sql


@pytest.mark.parametrize('length', [147, 200, 1200])
def test_completed_test_save_keeps_long_project_and_all_equipment(isolated_app, scenario_factory, monkeypatch, length):
    monkeypatch.setattr('app.preview_cache.schedule_after_save', lambda *args: None)
    identity = scenario_factory.identity_scenario(permission_codes=('testing.data_entry.view',),
                                                  granted_step_codes=('data_entry',))
    project = 'Resistance 耐水性能 ' + 'x' * (length-len('Resistance 耐水性能 '))
    report = Report(report_no='QA-LONG(E)', project=project, department=identity.department.name,
                    owner=identity.user.name, status='检测录入中', sample_status='已领取',
                    sample_pickup={'pickupTime':'2026-10-30'},
                    detail={'rawSample': {'schemeCode': identity.project.code,
                                          'schemeName': identity.project.name}})
    equipment = [EquipmentItem(archive_no=f'QA-LONG-{i}', name=f'虚拟仪器{i}',
                   dept=identity.department.name, status='可用', period='长期') for i in range(4)]
    from app.models import StdLibraryItem
    standard = StdLibraryItem(code='QA-STD', name='测试标准', use_depts=identity.department.name)
    db.session.add_all([report, standard, *equipment]); db.session.commit()
    client = isolated_app.test_client()
    headers = {'Authorization':'Bearer '+issue_token(identity.user)}
    for _ in range(2):
        body = {'testEditVersion':form_version(report), 'validateForCompletion':True,
                'standards':['QA-STD'], 'equipmentIds':[e.id for e in equipment],
                'resultStatus':'不判定', 'conclusion':'Refer to pages 2 ~ 4 for the detailed test results.',
                'testIntervals':[{'start':'2026-10-31 12:00:00','end':'2026-10-31 20:00:00'}]}
        response = client.put('/api/reports/QA-LONG(E)/testinfo', json=body, headers=headers)
        assert response.status_code == 200
        assert response.get_json()['code'] == 0, response.get_json()
        db.session.refresh(report)
        rows = EquipmentUsageRecord.query.filter_by(report_no=report.report_no).all()
        assert len(rows) == 4 and {r.equipment_id for r in rows} == {e.id for e in equipment}
        assert all(r.project == project for r in rows)
        assert report.detail['checkInput']['validatedForCompletion'] is True


def test_long_description_and_audit_not_truncated(isolated_app, scenario_factory):
    actor = scenario_factory.identity_scenario().user
    value = '委托工程名称及客户说明 English ' * 50
    report = Report(report_no='QA-CONTENT', project_name=value, client=value, out_of_scope_note=value)
    db.session.add(report)
    audit = add_operation_audit('qa.description', 'report', report.report_no, actor=actor, message=value)
    db.session.commit(); db.session.expire_all()
    assert db.session.get(Report, report.id).project_name == value
    assert db.session.get(Report, report.id).client == value
    assert db.session.get(Report, report.id).out_of_scope_note == value
    assert db.session.get(OperationAudit, audit.id).message == value


def test_long_attachment_name_kept_in_both_records(isolated_app, scenario_factory):
    from app.applications.report_lifecycle.commands import persist_report_attachment
    report = Report(report_no='QA-LONG-FILE')
    db.session.add(report)
    name = '英文检测附表 English ' * 16 + '.txt'
    content_type = 'application/' + 'x' * 113
    attachment = persist_report_attachment(
        report, b'isolated attachment', category='report_attachment', name=name,
        content_type=content_type, kind='Word', source='附件', status='已上传',
        uploaded_by='QA', created_by='QA')
    db.session.commit(); db.session.expire_all()
    assert attachment.name == attachment.stored_file.original_name == name
    assert attachment.content_type == attachment.stored_file.content_type == content_type
