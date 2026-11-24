"""Equipment status is computed; report eligibility uses the complete test window."""
from datetime import date, datetime

import pytest

from app.models import EquipmentItem, Report, StdLibraryItem
from app.extensions import db
from app.checks import compute_report_checks
from app.edit_concurrency import test_form_version as form_version
from app.security import issue_token

pytest_plugins = ("testkit.fixtures",)
START, END = date(2026, 10, 31), date(2026, 10, 31)


def equipment(**changes):
    values = dict(archive_no="QA-METER", name="虚拟仪器", status="限制使用",
                  actual_cal_date="2025-06-18", valid_until="2027-06-16", period="1")
    return EquipmentItem(**(values | changes))


@pytest.mark.parametrize("changes,error", [
    ({}, ""),
    ({"status": "可用", "valid_until": "2026-10-30"}, "校准有效期不足，未覆盖试验区间"),
    ({"status": "可用", "actual_cal_date": "2026-11-01"}, "校准开始日晚于试验开始"),
    ({"actual_cal_date": "", "last_cal_date": ""}, "校准日期或有效期未登记完整，请设备管理员补齐台账"),
    ({"valid_until": "invalid"}, "校准日期或有效期未登记完整，请设备管理员补齐台账"),
    ({"valid_until": "", "plan_cal_date": "2027-01-01"}, ""),
    ({"period": "长期", "valid_until": "", "actual_cal_date": ""}, ""),
    ({"period": "永久", "status": "维修中"}, "维修中"),
    ({"status": "停用"}, "停用"),
    ({"status": "报废"}, "报废"),
    ({"status": "失效"}, "失效"),
    ({"deleted_at": datetime(2026, 1, 1)}, "不存在或已删除"),
])
def test_real_window_and_manual_restrictions_survive_old_labels(changes, error):
    assert equipment(**changes).test_interval_error(START, END) == error


def test_list_status_changes_with_date_without_database_rewrite():
    row = equipment(valid_until="2026-10-31", plan_cal_date="2027-12-31")
    assert row.to_row(on_date=START)["status"] == "可用"
    assert row.to_row(on_date=date(2026, 11, 1))["status"] == "限制使用"
    assert row.to_row()["validUntil"] == "2026-10-31"
    assert row.test_interval_error(START, END) == ""  # Historical valid use survives today's expiry.
    row.valid_until = "2027-10-31"
    assert row.effective_status(date(2026, 11, 1)) == "可用"
    assert row.status == "限制使用"  # No database migration or audit rewriting required.


@pytest.mark.parametrize("start,end", [(None, END), (START, None), (date(2026, 11, 1), END)])
def test_invalid_test_window_is_not_accepted_even_for_long_term(start, end):
    assert equipment(period="长期").test_interval_error(start, end)


def test_report_checks_use_full_intervals_and_current_records(isolated_app, scenario_factory):
    row = equipment(actual_cal_date="2026-10-20")
    db.session.add(row); db.session.commit()
    report = Report(report_no="QA-CHECK", project="", department="", detail={"checkInput": {
        "equipmentIds": [row.id], "testDate": "2026-10-31",
        "testIntervals": [{"start": "2026-10-10", "end": "2026-10-11"},
                          {"start": "2026-10-31", "end": "2026-10-31"}],
    }})
    check = lambda: compute_report_checks(report)[0][1]
    assert check()["status"] == "不通过"  # The end date alone would incorrectly pass.
    row.actual_cal_date = "2026-01-01"
    assert check()["status"] == "通过"
    row.status = "维修中"
    assert check()["status"] == "不通过"
    row.status = "可用"
    row.valid_until = "2026-10-30"
    assert check()["status"] == "不通过"


@pytest.mark.parametrize("stored,until,success", [
    ("限制使用", "2027-06-16", True), ("可用", "2026-10-30", False),
    ("维修中", "2027-06-16", False),
])
def test_completion_endpoint_uses_live_validity(isolated_app, scenario_factory, monkeypatch, stored, until, success):
    monkeypatch.setattr("app.preview_cache.schedule_after_save", lambda *args: None)
    identity = scenario_factory.identity_scenario(permission_codes=("testing.data_entry.view",),
                                                  granted_step_codes=("data_entry",))
    report = Report(report_no="QA-EQUIP", department=identity.department.name,
                    project=identity.project.name, owner=identity.user.name,
                    status="检测录入中", sample_status="已领取",
                    sample_pickup={"pickupTime": "2026-10-30"}, detail={})
    row = equipment(status=stored, valid_until=until, dept=identity.department.name)
    standard = StdLibraryItem(code="QA-STD", name="虚拟标准", use_depts=identity.department.name)
    db.session.add_all([report, row, standard]); db.session.commit()
    body = {"testEditVersion": form_version(report), "validateForCompletion": True,
            "standards": ["QA-STD"], "equipmentIds": [row.id], "resultStatus": "不判定",
            "testIntervals": [{"start": "2026-10-31 12:00:00", "end": "2026-10-31 20:00:00"}]}
    result = isolated_app.test_client().put("/api/reports/QA-EQUIP/testinfo", json=body,
        headers={"Authorization": "Bearer " + issue_token(identity.user)}).get_json()
    assert (result["code"] == 0) is success, result
    if success:
        db.session.refresh(report)
        assert report.detail["checkInput"]["validatedForCompletion"] is True
        assert compute_report_checks(report)[0][1]["status"] == "通过"
    else:
        assert "以下设备不覆盖全部试验区间" in result["message"]
