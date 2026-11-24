"""Excel equipment identity: blank ID creates; explicit ID updates exactly one row."""
from datetime import datetime
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from app.extensions import db
from app.models import EquipmentItem, EquipmentCalibrationRecord, OperationAudit
from test_admin_corrections import workspace, headers

pytest_plugins = ("testkit.fixtures",)


def excel(columns, rows):
    book = Workbook()
    book.active.append(columns)
    for row in rows:
        book.active.append(row)
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


def upload(workspace, stream):
    client, actors, *_ = workspace
    return client.post("/api/quality/equipment/import", headers=headers(actors[0]),
                       data={"file": (stream, "equipment.xlsx")}).get_json()


def seed_pair():
    rows = [EquipmentItem(archive_no="GN26", name=name, maker="原厂家", dept="测试本部门")
            for name in ("电子天平", "Electronic balance")]
    db.session.add_all(rows)
    db.session.commit()
    return rows


@pytest.mark.parametrize("with_id_column", [False, True])
def test_blank_or_legacy_id_creates_same_number_variants_without_overwrite(workspace, with_id_column):
    original, english = seed_pair()
    columns = ["档案号", "仪器设备名称"]
    rows = [["GN26", "中文新增"], ["GN26", "English new"]]
    if with_id_column:
        columns.insert(0, "记录ID")
        rows = [[None, *row] for row in rows]
    result = upload(workspace, excel(columns, rows))
    assert result["code"] == 0, result
    assert result["data"]["createdCount"] == 2 and result["data"]["updatedCount"] == 0
    saved = EquipmentItem.query.filter_by(archive_no="GN26").order_by(EquipmentItem.id).all()
    assert [row.name for row in saved] == ["电子天平", "Electronic balance", "中文新增", "English new"]
    assert len({row.id for row in saved}) == 4
    audits = OperationAudit.query.filter_by(action="quality.equipment.import").all()
    assert {audit.object_id for audit in audits} == {str(row.id) for row in saved[2:]}
    assert all(not audit.before_data for audit in audits)


def test_explicit_id_updates_one_variant_and_preserves_omitted_columns(workspace):
    chinese, english = seed_pair()
    result = upload(workspace, excel(["记录ID", "档案号", "仪器设备名称", "证书编号"],
                                    [[english.id, "GN26", "English updated", "CERT-EN"]]))
    assert result["code"] == 0, result
    assert result["data"]["createdCount"] == 0 and result["data"]["updatedCount"] == 1
    db.session.refresh(chinese)
    db.session.refresh(english)
    assert chinese.name == "电子天平" and not chinese.certificate_no
    assert english.name == "English updated" and english.maker == "原厂家"
    audit = OperationAudit.query.filter_by(action="quality.equipment.import").one()
    assert audit.object_id == str(english.id)
    assert audit.before_data["name"] == "Electronic balance"
    assert audit.after_data["name"] == "English updated"
    record = EquipmentCalibrationRecord.query.one()
    assert record.equipment_id == english.id


@pytest.mark.parametrize("selected_only", [False, True])
def test_export_roundtrip_contains_ids_and_updates_correct_record(workspace, selected_only):
    chinese, english = seed_pair()
    client, actors, *_ = workspace
    url = "/api/quality/equipment/export" + (f"?ids={english.id}" if selected_only else "")
    response = client.get(url, headers=headers(actors[0]))
    book = load_workbook(BytesIO(response.data))
    sheet = book.active
    columns = {cell.value: cell.column for cell in sheet[1]}
    assert "记录ID" in columns and "导入说明" in book.sheetnames
    rows = list(sheet.iter_rows(min_row=2))
    assert {row[columns["记录ID"] - 1].value for row in rows} == ({english.id} if selected_only else {chinese.id, english.id})
    for row in rows:
        if row[columns["记录ID"] - 1].value == english.id:
            row[columns["仪器设备名称"] - 1].value = "Balance revised"
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    result = upload(workspace, stream)
    assert result["code"] == 0, result
    assert result["data"]["updatedCount"] == 1
    assert result["data"]["unchangedCount"] == len(rows) - 1
    db.session.refresh(chinese)
    db.session.refresh(english)
    assert chinese.name == "电子天平" and english.name == "Balance revised"
    assert EquipmentItem.query.count() == 2


@pytest.mark.parametrize("bad_id", ["GN26", "1.5", "0", "-1", "999999"])
def test_invalid_or_missing_id_rolls_back_entire_batch_without_number_fallback(workspace, bad_id):
    chinese, english = seed_pair()
    result = upload(workspace, excel(["记录ID", "档案号", "仪器设备名称"], [
        [chinese.id, "GN26", "不应保存"], [None, "NEW", "不应新增"], [bad_id, "GN26", "错误目标"],
    ]))
    assert result["code"] != 0 and "第 4 行" in result["message"], result
    db.session.refresh(chinese)
    assert chinese.name == "电子天平"
    assert EquipmentItem.query.count() == 2
    assert OperationAudit.query.filter_by(action="quality.equipment.import").count() == 0


def test_deleted_id_does_not_update_other_same_number_record(workspace):
    chinese, english = seed_pair()
    english.deleted_at = datetime(2026, 1, 1)
    db.session.commit()
    result = upload(workspace, excel(["记录ID", "档案号", "仪器设备名称"], [[english.id, "GN26", "错误恢复"]]))
    assert result["code"] != 0 and "已删除" in result["message"]
    db.session.refresh(chinese)
    db.session.refresh(english)
    assert chinese.name == "电子天平" and english.deleted_at is not None


def test_repeated_id_rejects_batch_even_with_different_numbers(workspace):
    chinese, _ = seed_pair()
    result = upload(workspace, excel(["记录ID", "档案号", "仪器设备名称"], [
        [chinese.id, "GN26", "第一次"], [chinese.id, "GN99", "第二次"],
    ]))
    assert result["code"] != 0 and "记录ID重复" in result["message"]
    db.session.refresh(chinese)
    assert chinese.archive_no == "GN26" and chinese.name == "电子天平"


def test_template_documents_new_and_update_identity(workspace):
    client, actors, *_ = workspace
    response = client.get("/api/quality/equipment/template", headers=headers(actors[0]))
    book = load_workbook(BytesIO(response.data))
    assert book.active.title == "仪器设备台账"
    assert book.active.cell(1, 1).value == "记录ID"
    assert book.active.max_row == 1
    instructions = " ".join(row[0] for row in book["导入说明"].values)
    assert "留空" in instructions and "旧表" in instructions and "保留" in instructions


def test_manual_create_keeps_same_number_as_independent_records(workspace):
    client, actors, *_ = workspace
    ids = []
    for name in ("电子天平", "Electronic balance"):
        result = client.post("/api/quality/equipment", headers=headers(actors[0]),
                             json={"archiveNo": "GN26", "name": name}).get_json()
        assert result["code"] == 0, result
        ids.append(result["data"]["id"])
    assert ids[0] != ids[1] and EquipmentItem.query.count() == 2


def test_import_permission_is_still_required(workspace):
    client, actors, *_ = workspace
    response = client.post("/api/quality/equipment/import", headers=headers(actors[2]),
                           data={"file": (excel(["档案号", "仪器设备名称"], [["GN26", "English"]]), "e.xlsx")})
    assert response.get_json()["code"] == 403, response.get_json()
    assert EquipmentItem.query.count() == 0
