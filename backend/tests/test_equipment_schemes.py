import json
from datetime import datetime

import pytest
from app.extensions import db
from app.models import EquipmentScheme, OperationAudit
from test_equipment_department_authorization import case, headers

pytest_plugins = ("testkit.fixtures",)


def create(case, **changes):
    client, user, admin, own, other, rows, report, *_ = case
    body = dict(departmentId=own.id, name="日常仪器组合", equipmentIds=[rows[0].id, rows[1].id], projectIds=[], enabled=True)
    body.update(changes)
    return client.post('/api/equipment-schemes', headers=headers(admin), json=body).get_json()


def resolve(case, scheme, actor=None, intervals=None):
    client, user, admin, own, other, rows, report, *_ = case
    return client.get(f'/api/equipment-schemes/{scheme["id"]}/resolve', headers=headers(actor or user),
        query_string=dict(reportNo=report.report_no, intervals=json.dumps(intervals if intervals is not None else [dict(start="2026-10-01", end="2026-10-02")]))).get_json()


def test_partial_live_resolution_never_mutates_report_or_scheme(case):
    scheme = create(case)["data"]
    result = resolve(case, scheme)["data"]
    assert [r["id"] for r in result["rows"]] == [case[5][0].id]
    assert result["skipped"][0]["reason"] == "仪器所属部门未授权使用"
    assert result["skipped"][0]["name"] == "不可用仪器"
    assert db.session.get(EquipmentScheme, scheme["id"]).equipment_ids == scheme["equipmentIds"]
    assert case[6].detail == {}
    case[8]([case[4].id])
    case[5][1].status = "维修中"; db.session.commit()
    result = resolve(case, scheme)["data"]
    assert len(result["rows"]) == 1 and result["skipped"][0]["reason"] == "维修中"
    case[5][0].deleted_at = datetime.utcnow(); db.session.commit()
    result = resolve(case, scheme)["data"]
    assert len(result["rows"]) == 0 and len(result["skipped"]) == 2


def test_permissions_and_department_isolation(case, scenario_factory):
    client, user, admin, own, other, rows, report, *_ = case
    body = dict(departmentId=own.id, name="组合", equipmentIds=[rows[0].id])
    assert client.post('/api/equipment-schemes', headers=headers(user), json=body).get_json()["code"] == 403
    manager = scenario_factory.user(own, permissions=["quality.equipment_ledger_department.view"])
    db.session.commit()
    assert client.post('/api/equipment-schemes', headers=headers(manager), json=body).get_json()["code"] == 0
    body["departmentId"] = other.id
    assert client.post('/api/equipment-schemes', headers=headers(manager), json=body).get_json()["code"] == 403
    result = client.get('/api/equipment-schemes', headers=headers(user), query_string={"reportNo": report.report_no}).get_json()
    assert result["data"]["canManage"] is False
    assert result["data"]["equipment"] == []
    assert client.get('/api/equipment-schemes', headers=headers(user), query_string={"reportNo": "QA-HIDDEN"}).get_json()["code"] == 403
    assert client.get('/api/equipment-schemes', headers=headers(manager), query_string={"departmentId": other.id}).get_json()["code"] == 403


def test_version_duplicate_disable_and_audit(case):
    client, user, admin, *_ = case
    scheme = create(case)["data"]
    assert create(case)["code"] == 1
    url = f'/api/equipment-schemes/{scheme["id"]}'
    assert client.put(url, headers=headers(admin), json=dict(scheme, enabled=False)).get_json()["code"] == 0
    assert resolve(case, scheme)["code"] == 404
    assert client.put(url, headers=headers(admin), json=dict(scheme, name="过期覆盖")).get_json()["code"] == 409
    assert db.session.get(EquipmentScheme, scheme["id"]).name == scheme["name"]
    assert OperationAudit.query.filter_by(action="equipment.scheme.save").count() == 2


@pytest.mark.parametrize("ids", [[], [True], ["1"], [999999], "1"])
def test_bad_selection_atomic(case, ids):
    assert create(case, equipmentIds=ids)["code"] == 1
    assert EquipmentScheme.query.count() == 0


def test_current_test_dates_and_missing_intervals(case):
    row = case[5][0]
    row.period = "一年"; row.actual_cal_date = "2026-01-01"; row.valid_until = "2026-10-01"
    db.session.commit()
    scheme = create(case, equipmentIds=[row.id])["data"]
    result = resolve(case, scheme)["data"]
    assert result["rows"] == [] and "校准有效期不足" in result["skipped"][0]["reason"]
    assert len(resolve(case, scheme, intervals=[dict(start="2026-09-30", end="2026-10-01")])["data"]["rows"]) == 1
    assert resolve(case, scheme, intervals=[])["code"] == 1
    assert resolve(case, scheme, intervals=[{}])["code"] == 1
    assert resolve(case, scheme, intervals=[dict(start="2026-02-30", end="2026-03-01")])["code"] == 1


def test_project_recommendations_are_department_scoped(case, scenario_factory):
    from app.authorization_scope import project_for_report
    own_project = project_for_report(case[6])
    scheme = create(case, projectIds=[own_project.id])["data"]
    data = case[0].get('/api/equipment-schemes', headers=headers(case[1]), query_string={"reportNo": case[6].report_no}).get_json()["data"]
    assert data["schemes"][0]["recommended"] is True
    other_project, _ = scenario_factory.project(case[4])
    db.session.commit()
    assert create(case, name="越权", projectIds=[other_project.id])["code"] == 1


def test_new_invalid_equipment_is_rejected_on_draft_save(case):
    row = case[5][0]
    row.status = "停用"; db.session.commit()
    assert case[10]([row.id])["code"] == 1
    assert case[6].detail == {}


def test_state_changed_after_applying_is_rechecked_on_draft_save(case):
    scheme = create(case, equipmentIds=[case[5][0].id])["data"]
    assert len(resolve(case, scheme)["data"]["rows"]) == 1
    assert case[10]([case[5][0].id])["code"] == 0
    case[5][0].status = "维修中"; db.session.commit()
    assert case[10]([case[5][0].id])["code"] == 1


@pytest.mark.parametrize("end,eligible", [("2026-12-10", True), ("2026-11-10", False)])
def test_retained_calibration_coverage_and_gaps(case, end, eligible):
    from test_equipment_calibration_periods import seed, renew
    row = seed(case, end)
    assert renew(case, row)["code"] == 0
    scheme = create(case, equipmentIds=[row.id])["data"]
    value = resolve(case, scheme, intervals=[dict(start="2026-11-01", end="2026-11-13")])["data"]
    assert bool(value["rows"]) == eligible
    if not eligible:
        assert "无有效校准覆盖" in value["skipped"][0]["reason"]


def test_duplicate_rename_rolls_back_and_retains_missing_references(case):
    first = create(case)["data"]
    second = create(case, name="第二方案")["data"]
    client, _, admin = case[:3]
    response = client.put(f'/api/equipment-schemes/{second["id"]}', headers=headers(admin), json=dict(second, name=first["name"])).get_json()
    assert response["code"] == 1
    assert db.session.get(EquipmentScheme, second["id"]).version == 1
    case[5][0].deleted_at = datetime.utcnow(); db.session.commit()
    response = client.put(f'/api/equipment-schemes/{second["id"]}', headers=headers(admin), json=dict(second, name="保留组合")).get_json()
    assert response["code"] == 0
    assert response["data"]["equipmentIds"] == second["equipmentIds"]


def test_migration_adds_only_scheme_table_and_can_roundtrip(isolated_app):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    path = Path(__file__).parents[1] / 'migrations/versions/e112f0112026_equipment_schemes.py'
    spec = importlib.util.spec_from_file_location('scheme_migration', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with isolated_app.app_context(), db.engine.begin() as connection:
        EquipmentScheme.__table__.drop(connection)
        before = set(inspect(connection).get_table_names())
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert set(inspect(connection).get_table_names()) - before == {"equipment_schemes"}
            assert {c['name'] for c in inspect(connection).get_columns('equipment_schemes')} == set(EquipmentScheme.__table__.columns.keys())
            module.downgrade()
            assert set(inspect(connection).get_table_names()) == before
            module.upgrade()
