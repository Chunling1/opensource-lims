"""Isolated public-contract checks for the quality_resources module.

The pack uses only virtual SQLite records supplied by the shared testkit.  It
protects standards, capability lookup and equipment boundaries without relying
on the seeded demo/production quality libraries.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.extensions import db
from app.models import (
    CapabilityEntry,
    CapabilityImportBatch,
    EquipmentItem,
    OperationAudit,
    Standard,
    StdLibraryItem,
)

from testkit.factories import ScenarioFactory, login_headers


pytest_plugins = ("testkit.fixtures",)


def _headers(client, account: str):
    return login_headers(client, account)


def _quality_user(factory: ScenarioFactory, department, *, account: str, pages=(), actions=()):
    user = factory.user(
        department,
        account=account,
        name=f"{account}-虚拟人员",
        permissions=pages,
    )
    for action in actions:
        factory.grant_action(user, action)
    db.session.commit()
    return user


def _standard(*, code: str, department, suffix: str) -> StdLibraryItem:
    row = StdLibraryItem(
        controlled_no=f"VIRTUAL-CONTROL-{suffix}",
        code=code,
        name=f"虚拟受控标准{suffix}",
        auth_kind="一单一库+CNAS+CMA",
        use_depts=department.name,
    )
    db.session.add(row)
    db.session.flush()
    return row


def _equipment(*, department, suffix: str) -> EquipmentItem:
    row = EquipmentItem(
        archive_no=f"VIRTUAL-EQ-{suffix}",
        name=f"虚拟设备{suffix}",
        dept=department.name,
        status="可用",
    )
    db.session.add(row)
    db.session.flush()
    return row


def _workbook_with_rollback_case() -> BytesIO:
    book = Workbook()
    sheet = book.active
    sheet.append(["受控号", "标准编号", "标准名称"])
    sheet.append(["VIRTUAL-IMPORT-1", "VIRTUAL/IMPORT-1", "虚拟导入标准一"])
    # The second row is invalid after the first has been staged.  The endpoint
    # must roll the transaction back rather than keep a partial import.
    sheet.append(["VIRTUAL-IMPORT-2", "", "虚拟导入标准二"])
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


def test_controlled_standard_search_covers_all_fields_and_capability_details(
    isolated_app, isolated_client, scenario_factory,
):
    with isolated_app.app_context():
        root = scenario_factory.department(name="虚拟全文检索中心")
        department = scenario_factory.department(name="虚拟全文检索部门", parent=root)
        reader = _quality_user(
            scenario_factory,
            department,
            account="quality-full-field-reader",
            pages=("quality.standard_library.view",),
        )
        master = Standard(
            code="VIRTUAL/MASTER-SEARCH",
            name="虚拟主表全文标准",
            auth_kind="CNAS+CMA",
            department="虚拟归口全文部门",
            category="虚拟主表类别",
            status="现行",
        )
        db.session.add(master)
        db.session.flush()
        standard = StdLibraryItem(
            standard_id=master.id,
            controlled_no="VIRTUAL-CONTROL-FULLTEXT",
            code="VIRTUAL/FULLTEXT-2026",
            name="虚拟全字段受控标准",
            auth_kind="CNAS+CMA+一单一库",
            category="虚拟检验检测类别",
            location="虚拟全文地点",
            issue_count="SEARCH-COUNT-37",
            issuer="虚拟全文发放人",
            use_depts=department.name,
            impl_date="2020-03-17",
            delay_days="137",
            replace_no="REPLACED-BY-FULLTEXT",
            remark="虚拟全文备注内容",
            is_english=True,
        )
        db.session.add(standard)
        db.session.flush()
        batch = CapabilityImportBatch(
            source_name="virtual-fulltext-capability.pdf",
            source_sha256="f" * 64,
            status="active",
        )
        db.session.add(batch)
        db.session.flush()
        capability = CapabilityEntry(
            batch_id=batch.id,
            standard_item_id=standard.id,
            capability_type="检测",
            certificate_no="VIRTUAL-CERT-FULLTEXT",
            site="虚拟能力全文场所",
            section_path="虚拟章节全文路径",
            object_name="虚拟检测对象全文",
            item_name="虚拟检测参数全文",
            standard_code=standard.code,
            standard_name=standard.name,
            method_clause="虚拟方法条款全文",
            restriction="虚拟限制全文",
            source_file="virtual-fulltext-source.pdf",
            source_page=1,
            source_row=1,
            source_sha256="e" * 64,
            mapping_status="confirmed",
            active=True,
        )
        capability.departments = [department]
        db.session.add(capability)
        db.session.commit()
        account = reader.account
        standard_id = standard.id

    headers = _headers(isolated_client, account)
    for keyword in (
        "虚拟检验检测类别",
        "虚拟全文地点",
        "SEARCH-COUNT-37",
        "虚拟全文发放人",
        "虚拟全文检索部门",
        "2020-03-17",
        "REPLACED-BY-FULLTEXT",
        "虚拟全文备注内容",
        "虚拟归口全文部门",
        "虚拟检测对象全文",
        "虚拟检测参数全文",
        "虚拟方法条款全文",
        "虚拟限制全文",
        "英文标准",
        "现行",
    ):
        payload = isolated_client.get(
            "/api/quality/std-library",
            query_string={"keyword": keyword, "size": 100},
            headers=headers,
        ).get_json()
        assert payload["code"] == 0
        assert standard_id in [row["id"] for row in payload["data"]["rows"]], keyword

    selector = isolated_client.get(
        "/api/quality/std-library/search",
        query_string={"keyword": "虚拟检测参数全文", "size": 100},
        headers=headers,
    ).get_json()
    assert selector["code"] == 0
    assert standard_id in [row["id"] for row in selector["data"]["rows"]]


def test_department_quality_readers_only_see_own_standards_and_equipment(
    isolated_app, isolated_client, scenario_factory,
):
    with isolated_app.app_context():
        root = scenario_factory.department(name="虚拟质量资源中心")
        department_a = scenario_factory.department(name="虚拟质量部门A", parent=root)
        department_b = scenario_factory.department(name="虚拟质量部门B", parent=root)
        reader = _quality_user(
            scenario_factory,
            department_a,
            account="quality-department-reader",
            pages=(
                "quality.standard_library_department.view",
                "quality.equipment_ledger_department.view",
            ),
        )
        reader_account = reader.account
        own_standard = _standard(code="VIRTUAL/STD-A", department=department_a, suffix="A")
        other_standard = _standard(code="VIRTUAL/STD-B", department=department_b, suffix="B")
        own_equipment = _equipment(department=department_a, suffix="A")
        other_equipment = _equipment(department=department_b, suffix="B")
        db.session.commit()
        own_standard_id = own_standard.id
        other_standard_id = other_standard.id
        own_equipment_id = own_equipment.id
        other_equipment_id = other_equipment.id

    headers = _headers(isolated_client, reader_account)
    standard_list = isolated_client.get("/api/quality/std-library", headers=headers).get_json()
    assert standard_list["code"] == 0
    assert [row["id"] for row in standard_list["data"]["rows"]] == [own_standard_id]
    hidden_standard = isolated_client.get(
        f"/api/quality/std-library/{other_standard_id}", headers=headers,
    ).get_json()
    assert hidden_standard["code"] == 1

    equipment_list = isolated_client.get("/api/quality/equipment?full=1", headers=headers).get_json()
    assert equipment_list["code"] == 0
    assert [row["id"] for row in equipment_list["data"]["rows"]] == [own_equipment_id]
    hidden_equipment = isolated_client.get(
        f"/api/quality/equipment/{other_equipment_id}", headers=headers,
    ).get_json()
    assert hidden_equipment["code"] == 1


def test_controlled_standard_write_requires_full_library_and_action_and_is_audited(
    isolated_app, isolated_client, scenario_factory,
):
    with isolated_app.app_context():
        department = scenario_factory.department(name="虚拟标准维护部门")
        department_reader = _quality_user(
            scenario_factory,
            department,
            account="quality-read-only-writer",
            pages=("quality.standard_library_department.view",),
            actions=("quality.standard.create",),
        )
        maintainer = _quality_user(
            scenario_factory,
            department,
            account="quality-standard-maintainer",
            pages=("quality.standard_library.view",),
            actions=("quality.standard.create", "quality.standard.delete"),
        )
        department_reader_account = department_reader.account
        maintainer_account = maintainer.account
        department_name = department.name

    request_body = {
        "controlledNo": "VIRTUAL-WRITE-001",
        "code": "VIRTUAL/WRITE-001",
        "name": "虚拟标准维护记录",
        "useDepts": [department_name],
    }
    denied = isolated_client.post(
        "/api/quality/std-library", headers=_headers(isolated_client, department_reader_account), json=request_body,
    ).get_json()
    assert denied["code"] == 403

    created = isolated_client.post(
        "/api/quality/std-library", headers=_headers(isolated_client, maintainer_account), json=request_body,
    ).get_json()
    assert created["code"] == 0
    standard_id = created["data"]["id"]
    removed = isolated_client.delete(
        f"/api/quality/std-library/{standard_id}", headers=_headers(isolated_client, maintainer_account),
    ).get_json()
    assert removed["code"] == 0
    with isolated_app.app_context():
        row = db.session.get(StdLibraryItem, standard_id)
        assert row.deleted_at is not None
        assert OperationAudit.query.filter_by(
            action="quality.standard.delete", object_type="controlled_standard", object_id=str(standard_id),
        ).count() == 1


def test_quality_import_failure_rolls_back_all_staged_standard_rows(
    isolated_app, isolated_client, scenario_factory,
):
    with isolated_app.app_context():
        department = scenario_factory.department(name="虚拟质量导入部门")
        importer = _quality_user(
            scenario_factory,
            department,
            account="quality-standard-importer",
            pages=("quality.standard_library.view",),
            actions=("quality.standard.create", "quality.standard.update", "quality.standard.authorize"),
        )
        importer_account = importer.account

    result = isolated_client.post(
        "/api/quality/std-library/import",
        headers=_headers(isolated_client, importer_account),
        data={"file": (_workbook_with_rollback_case(), "virtual-standards.xlsx")},
        content_type="multipart/form-data",
    ).get_json()
    assert result["code"] == 1
    assert "第 3 行" in result["message"]
    with isolated_app.app_context():
        assert StdLibraryItem.query.filter(StdLibraryItem.code.like("VIRTUAL/IMPORT-%")).count() == 0
        assert OperationAudit.query.filter_by(action="quality.standard.import").count() == 0


def test_equipment_delete_requires_master_scope_and_empty_batch_is_safe(
    isolated_app, isolated_client, scenario_factory,
):
    with isolated_app.app_context():
        department = scenario_factory.department(name="虚拟设备维护部门")
        restricted = _quality_user(
            scenario_factory,
            department,
            account="quality-equipment-dept-user",
            pages=("quality.equipment_ledger_department.view",),
            actions=("quality.equipment.delete",),
        )
        maintainer = _quality_user(
            scenario_factory,
            department,
            account="quality-equipment-maintainer",
            pages=("quality.equipment_ledger.view",),
            actions=("quality.equipment.delete",),
        )
        equipment = _equipment(department=department, suffix="DELETE")
        restricted_account = restricted.account
        maintainer_account = maintainer.account
        db.session.commit()
        equipment_id = equipment.id

    blocked = isolated_client.delete(
        f"/api/quality/equipment/{equipment_id}", headers=_headers(isolated_client, restricted_account),
    ).get_json()
    assert blocked["code"] == 403
    empty = isolated_client.post(
        "/api/quality/equipment/batch-delete", headers=_headers(isolated_client, maintainer_account), json={"ids": []},
    ).get_json()
    assert empty["code"] == 1
    with isolated_app.app_context():
        assert db.session.get(EquipmentItem, equipment_id).deleted_at is None

    removed = isolated_client.delete(
        f"/api/quality/equipment/{equipment_id}", headers=_headers(isolated_client, maintainer_account),
    ).get_json()
    assert removed["code"] == 0
    with isolated_app.app_context():
        row = db.session.get(EquipmentItem, equipment_id)
        assert row.deleted_at is not None
        assert row.status == "停用/报废"


def test_capability_lookup_is_department_filtered_and_requires_current_active_mapping(
    isolated_app, isolated_client, scenario_factory,
):
    with isolated_app.app_context():
        department_a = scenario_factory.department(name="虚拟能力部门A")
        department_b = scenario_factory.department(name="虚拟能力部门B")
        reader = _quality_user(
            scenario_factory,
            department_a,
            account="quality-capability-reader",
        )
        reader_account = reader.account
        standard_a = _standard(code="VIRTUAL/CAP-A", department=department_a, suffix="CAP-A")
        standard_b = _standard(code="VIRTUAL/CAP-B", department=department_b, suffix="CAP-B")
        batch = CapabilityImportBatch(
            source_name="virtual-capability-source.pdf",
            source_sha256="a" * 64,
            status="active",
            attachment_count=1,
        )
        db.session.add(batch)
        db.session.flush()
        entry_a = CapabilityEntry(
            batch_id=batch.id,
            standard_item_id=standard_a.id,
            capability_type="检测",
            certificate_no="VIRTUAL-CERT-A",
            site="虚拟场所A",
            object_name="虚拟试验对象A",
            item_name="虚拟检测参数A",
            standard_code=standard_a.code,
            source_file="virtual-capability-source.pdf",
            source_page=1,
            source_row=1,
            source_sha256="b" * 64,
            mapping_status="confirmed",
            active=True,
            effective_date=date(2020, 1, 1),
            expires_on=date(2030, 1, 1),
        )
        entry_a.departments = [department_a]
        entry_b = CapabilityEntry(
            batch_id=batch.id,
            standard_item_id=standard_b.id,
            capability_type="检测",
            certificate_no="VIRTUAL-CERT-B",
            site="虚拟场所B",
            object_name="虚拟试验对象B",
            item_name="虚拟检测参数B",
            standard_code=standard_b.code,
            source_file="virtual-capability-source.pdf",
            source_page=2,
            source_row=2,
            source_sha256="c" * 64,
            mapping_status="confirmed",
            active=True,
            effective_date=date(2020, 1, 1),
            expires_on=date(2030, 1, 1),
        )
        entry_b.departments = [department_b]
        db.session.add_all([entry_a, entry_b])
        db.session.commit()

    result = isolated_client.get(
        "/api/quality/std-library/search?keyword=VIRTUAL/CAP&capabilityOnly=1&date=2026-08-18",
        headers=_headers(isolated_client, reader_account),
    ).get_json()
    assert result["code"] == 0
    assert [row["code"] for row in result["data"]["rows"]] == ["VIRTUAL/CAP-A"]
    assert result["data"]["rows"][0]["capabilityTypes"] == ["检测"]

def test_all_standard_capability_catalog_keeps_department_and_authorization_scope(isolated_app, isolated_client, scenario_factory):
    from app.security import issue_token
    with isolated_app.app_context():
        dept=scenario_factory.department(name='虚拟项目排序部门')
        other=scenario_factory.department(name='另一虚拟部门')
        user=_quality_user(scenario_factory,dept,account='ordered-parameter-reader',pages=('entrust.sample_register.view',))
        batch=CapabilityImportBatch(source_name='ordered-virtual.pdf',source_sha256='c'*64,status='active')
        db.session.add(batch);db.session.flush()
        allowed=[]
        for index,target in enumerate([dept,dept,other]):
            standard=_standard(code=f'GB/QA-{index}',department=target,suffix=f'ORDER-{index}')
            entry=CapabilityEntry(batch_id=batch.id,standard_item_id=standard.id,capability_type='检测',standard_code=standard.code,
                certificate_no='VIRTUAL-ORDER',site='虚拟场所',object_name='虚拟对象',standard_name=standard.name,item_name=f'参数{index}',mapping_status='confirmed',active=True,source_file='virtual.pdf',source_page=1,source_row=index,source_sha256=str(index)*64)
            entry.departments=[target];db.session.add(entry);db.session.flush()
            if target==dept:allowed.append(entry.id)
        db.session.commit();headers={'Authorization':'Bearer '+issue_token(user)};other_name=other.name
    path='/api/reports/lib/capability-items'
    assert isolated_client.post(path,json={},headers=headers).get_json()['data']['rows']==[]
    rows=isolated_client.post(path,json={'allStandards':True,'department':other_name},headers=headers).get_json()['data']['rows']
    assert {row['id'] for row in rows}==set(allowed)
    rows=isolated_client.post(path,json={'allStandards':True,'keyword':'参数1'},headers=headers).get_json()['data']['rows']
    assert [row['id'] for row in rows]==[allowed[1]]
    assert isolated_client.post(path,json={'allStandards':True}).status_code==401


def test_catalog_pages_filter_before_count_and_load_details_only_for_page(isolated_app, isolated_client, scenario_factory):
    """A large source summary is read once; hidden rows never decode raw_cells."""
    import time
    from sqlalchemy import event
    from app.security import issue_token
    from app.models import user_standard_denials
    with isolated_app.app_context():
        dept = scenario_factory.department(name='虚拟分页检测部')
        other = scenario_factory.department(name='另一分页检测部')
        reader = _quality_user(scenario_factory, dept, account='catalog-paging', pages=('entrust.sample_register.view',))
        standards = [_standard(code=f'GB/PAGE-{i:03}', department=dept, suffix=f'PAGE-{i}') for i in range(30)]
        denied_id = standards[-1].id
        db.session.execute(user_standard_denials.insert().values(user_id=reader.id, standard_item_id=denied_id))
        batch = CapabilityImportBatch(source_name='virtual-page.pdf', source_sha256='f'*64, status='active', summary={
            'schema': 'lims.scope-workbook-import.v2', 'createdItemIds': [s.id for s in standards],
            'standardPolicies': {}, 'syntheticPadding': 'x' * 5_000_000,
        })
        db.session.add(batch); db.session.flush()
        allowed, hidden = [], []
        for index in range(600):
            standard = standards[index % len(standards)]
            expired = index % 17 == 0
            wrong_dept = index % 19 == 0
            entry = CapabilityEntry(batch_id=batch.id, standard_item_id=standard.id, standard_code=standard.code,
                standard_name='分页搜索标准', capability_type='检测', certificate_no='VIRTUAL-PAGE', site='虚拟场所', object_name='虚拟样品',
                object_seq='1', item_seq=f'{index:04}', item_name=f'参数 {index:04}', mapping_status='confirmed', active=True,
                expires_on=date(2020,1,1) if expired else None, source_file='virtual.pdf', source_page=1, source_row=index,
                source_sha256=f'{index:064x}', raw_cells={'synthetic': 'x' * 2048})
            entry.departments = [other if wrong_dept else dept]
            db.session.add(entry); db.session.flush()
            (hidden if standard.id == denied_id else allowed).append(entry.id)
        db.session.commit()
        headers = {'Authorization':'Bearer '+issue_token(reader)}
        engine = db.engine
        db.session.remove()
    statements, loaded = [], []
    def query_log(conn, cursor, statement, parameters, context, executemany): statements.append(statement.lower())
    def load_log(target, context): loaded.append(target.id)
    event.listen(engine, 'before_cursor_execute', query_log)
    event.listen(CapabilityEntry, 'load', load_log)
    path = '/api/reports/lib/capability-items'
    try:
        start = time.perf_counter()
        response = isolated_client.post(path, json={'allStandards':True,'page':2,'size':20,'date':'2026-10-20'}, headers=headers)
        elapsed = time.perf_counter()-start
        result = response.get_json()['data']
        assert result['total'] == len(allowed)
        assert [r['id'] for r in result['rows']] == allowed[20:40]
        assert set(loaded) == set(allowed[20:40])
        summary_reads = [sql for sql in statements if 'capability_import_batches.summary' in sql]
        assert len(summary_reads) == 1
        assert len(statements) < 25
        print(f'catalog fixture: 600 entries, 5MB source, {len(statements)} SQL, {len(summary_reads)} summary read, {len(loaded)} full rows, {elapsed:.3f}s')
        # Selected-ID hydration observes exactly the same standard authorization gates.
        result = isolated_client.post(path, json={'allStandards':True,'ids':[allowed[-1],*hidden[:3]],'date':'2026-10-20'}, headers=headers).get_json()['data']
        assert [r['id'] for r in result['rows']] == [allowed[-1]]
        # Multi-term search uses fields across a record, and empty scopes stay empty.
        result = isolated_client.post(path, json={'allStandards':True,'page':1,'keyword':'参数 001','date':'2026-10-20'}, headers=headers).get_json()['data']
        assert result['total'] > 0
        assert all('001' in row['itemName'] + row['standardCode'] for row in result['rows'])
        result = isolated_client.post(path, json={'allStandards':True,'page':1,'standardCodes':[]}, headers=headers).get_json()['data']
        assert result['total'] == 0 and result['rows'] == []
        assert isolated_client.post(path,json={'allStandards':True,'page':0},headers=headers).status_code == 400
        assert isolated_client.post(path,json={'allStandards':True,'page':1,'size':1000},headers=headers).status_code == 400
        normalized = isolated_client.post(path, json={'allStandards':True,'page':1,'standardCodes':['GB /PAGE-001']}, headers=headers).get_json()['data']
        assert normalized['total'] > 0 and all(row['standardCode'] == 'GB/PAGE-001' for row in normalized['rows'])
        # Standard default search also loads capabilities for only its visible standards.
        loaded.clear(); statements.clear()
        result = isolated_client.get('/api/quality/std-library/search?page=1&size=2',headers=headers).get_json()['data']
        assert result['total'] == 29 and len(result['rows']) == 2
        assert len(loaded) <= 40
        assert len([sql for sql in statements if 'capability_import_batches.summary' in sql]) == 1
    finally:
        event.remove(engine, 'before_cursor_execute', query_log)
        event.remove(CapabilityEntry, 'load', load_log)
