from testkit.forms import loaded_form
from datetime import datetime
from io import BytesIO

import fitz
import pytest
from docx import Document

from app import create_app
from app.extensions import db
from app.models import (
    OperationAudit,
    Report,
    ReportAttachment,
    ReportDocumentContent,
)
from app.report_documents import build_ncsa_document
from config import Config

TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAYAAAD0In+KAAAADklEQVR4nGP4z8DwH4QBEfcD/ePF9e8AAAAASUVORK5CYII="


class TestConfig(Config):
    TESTING = True
    PROD = False
    ADMIN_PASSWORD = "TestAdmin#2026!"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    REPORT_RENDER_SYNC = True
    JWT_SECRET = "test-secret-key-with-at-least-thirty-two-bytes"
    JWT_SECRET_IS_DEFAULT = False


def one_page_pdf(text="report"):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture()
def app(monkeypatch, tmp_path):
    class IsolatedTestConfig(TestConfig):
        STORAGE_ROOT = str(tmp_path / "report-storage")

    application = create_app(IsolatedTestConfig)
    monkeypatch.setattr("app.report_documents.docx_to_pdf", lambda _blob: one_page_pdf("official"))
    with application.app_context():
        db.create_all()
        from app.seed import seed_all
        from app.models import Department, Project, ProjectStep, User
        from app.seed_data import PROJECT_AUTHORIZATION_STEPS
        from app.security import hash_password
        seed_all()
        admin_user = User.query.filter_by(account="admin").first()
        admin_user.password_hash = hash_password("123456")
        admin_user.must_change_password = False
        dept = Department.query.filter_by(name="热工系统检测部").first()
        if dept is None:
            dept = Department(code="THERMAL", name="热工系统检测部")
            db.session.add(dept)
            db.session.flush()
        proj = Project.query.filter_by(name="制冷量、循环风量、能效比", department_id=dept.id).first()
        if proj is None:
            proj = Project(code="JF01", display_code="JF01", number_code="JF", name="制冷量、循环风量、能效比", department_id=dept.id, active=True)
            db.session.add(proj)
            db.session.flush()
            for step_code, step_name in PROJECT_AUTHORIZATION_STEPS:
                db.session.add(ProjectStep(project_id=proj.id, step_code=step_code, step_name=step_name))
        report = Report(
            report_no="NCSA-2026JF-0028",
            sample_no="2026JF-0028",
            project="制冷量、循环风量、能效比",
            project_name="计算机和数据处理机房用单元式空气调节机",
            client="示例精密设备有限公司",
            template="NCSA-2026JF",
            version="V0",
            status="待校核",
            department="热工系统检测部",
            owner="系统管理员",
            sample_status="已领取",
            detail={
                "trademarkImage": TINY_PNG,
                "summary": [
                    {"title": "委托信息", "fields": [
                        ["委托单位", "示例精密设备有限公司"],
                        ["委托单位地址", "深圳市南山区学苑大道1001号"],
                    ]},
                    {"title": "送样信息", "fields": [
                        ["样品名称", "计算机和数据处理机房用单元式空气调节机"],
                        ["规格型号", "CR040RC"], ["样品数量", "1台"],
                        ["商标", "测试商标"],
                        ["送样日期", "2026-03-02"], ["生产单位", "示例精密设备有限公司"],
                    ]},
                    {"title": "实验信息", "fields": [
                        ["执行标准", "GB/T 19232-2019"], ["检测项目", "制冷量、循环风量、能效比"],
                        ["试验设备", "空调及制冷设备检验装置"], ["检测日期", "2026-03-25～03-26"],
                    ]},
                    {"title": "原始记录", "fields": [["结论", "符合要求"]]},
                ],
                "checkInput": {
                    "standard": "GB/T 19232-2019",
                    "instrument": "T-KZ153",
                    "testDate": "2026-03-26",
                    "seal": "CMA",
                },
                "signatures": {"主检": "系统管理员"},
            },
        )
        db.session.add(report)
        db.session.commit()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def test_report_creation_timestamp_is_persisted(app):
    with app.app_context():
        report = Report.query.filter_by(report_no="NCSA-2026JF-0028").one()
        assert isinstance(report.created_at, datetime)


@pytest.fixture()
def auth_headers(client):
    response = client.post("/api/auth/login", json={"account": "admin", "password": "123456"})
    payload = response.get_json()
    assert payload["code"] == 0
    return {"Authorization": f"Bearer {payload['data']['token']}"}


def structured_content():
    return {
        "profileCode": "NCSA-2026JF",
        "resultGroups": [{
            "name": "制冷量",
            "items": [
                {"name": "制冷量", "condition": "额定工况", "unit": "W", "value": "46111"},
                {"name": "制冷量", "condition": "高速工况", "unit": "W", "value": "52144"},
            ],
        }],
        "remarks": "额定工况机外静压10Pa。",
        "photos": [],
        "extraPages": [],
    }


def test_attachment_name_is_portably_bounded_before_database_flush(
    client,
    auth_headers,
):
    filename = f"{'a' * 220}.pdf"
    response = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={"file": (BytesIO(b"%PDF-1.4 portable"), filename)},
        content_type="multipart/form-data",
    ).get_json()
    assert response["code"] == 0
    assert len(response["data"]["name"]) <= 200
    assert response["data"]["name"].endswith(".pdf")


def test_complete_report_preview_appends_report_pages_but_excludes_raw_records(
    client,
    auth_headers,
):
    continuation = one_page_pdf("uploaded report continuation")
    raw_record = one_page_pdf("raw record")
    report_upload = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={
            "category": "report_page",
            "file": (BytesIO(continuation), "报告后续页.pdf"),
        },
        content_type="multipart/form-data",
    ).get_json()
    assert report_upload["code"] == 0
    assert report_upload["data"]["source"] == "报告后续页"

    raw_upload = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={
            "category": "raw_record",
            "file": (BytesIO(raw_record), "原始记录.pdf"),
        },
        content_type="multipart/form-data",
    ).get_json()
    assert raw_upload["code"] == 0
    assert raw_upload["data"]["source"] == "原始记录"

    response = client.get(
        "/api/reports/NCSA-2026JF-0028/complete-preview?view=query",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.content_type == "application/pdf"
    merged = fitz.open(stream=response.data, filetype="pdf")
    assert merged.page_count == 2
    assert "uploaded report continuation" in merged[1].get_text()
    assert all("raw record" not in page.get_text() for page in merged)
    merged.close()


def test_uploaded_pages_replace_generated_result_body_for_standard_report(
    client,
    auth_headers,
    app,
    monkeypatch,
):
    """A continuation upload follows cover/home, not a generated result page."""
    with app.app_context():
        report = Report.query.filter_by(report_no="NCSA-2026JF-0028").one()
        report.report_no = "LAB-2026AC-0001"
        report.template = "STANDARD-COVER-HOME"
        report.project = "净化能效"
        db.session.commit()

    monkeypatch.setattr(
        "app.report_documents.build_cover_parts",
        lambda _report: [b"cover-part", b"homepage-part"],
    )
    monkeypatch.setattr(
        "app.report_documents.cover_templates_are_combined",
        lambda _report: False,
    )
    monkeypatch.setattr(
        "app.report_documents.docx_to_pdf",
        lambda blob: one_page_pdf(blob.decode("utf-8")),
    )

    continuation = one_page_pdf("uploaded authoritative result page")
    uploaded = client.post(
        "/api/reports/LAB-2026AC-0001/attachments",
        headers=auth_headers,
        data={
            "category": "report_page",
            "file": (BytesIO(continuation), "报告后续页.pdf"),
        },
        content_type="multipart/form-data",
    ).get_json()
    assert uploaded["code"] == 0

    response = client.get(
        "/api/reports/LAB-2026AC-0001/complete-preview?view=query",
        headers=auth_headers,
    )
    assert response.status_code == 200
    merged = fitz.open(stream=response.data, filetype="pdf")
    assert merged.page_count == 3
    assert "cover-part" in merged[0].get_text()
    assert "homepage-part" in merged[1].get_text()
    assert "uploaded authoritative result page" in merged[2].get_text()
    assert all("generated result" not in page.get_text() for page in merged)
    merged.close()


def test_uploaded_pages_keep_only_ncsa_home_before_continuation(
    client,
    auth_headers,
    monkeypatch,
):
    generated = fitz.open()
    for label in ("generated home", "generated result", "generated photos"):
        page = generated.new_page()
        page.insert_text((72, 72), label)
    generated_pdf = generated.tobytes()
    generated.close()
    monkeypatch.setattr("app.report_documents.docx_to_pdf", lambda _blob: generated_pdf)

    continuation = one_page_pdf("uploaded continuation")
    uploaded = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={
            "category": "report_page",
            "file": (BytesIO(continuation), "报告后续页.pdf"),
        },
        content_type="multipart/form-data",
    ).get_json()
    assert uploaded["code"] == 0

    response = client.get(
        "/api/reports/NCSA-2026JF-0028/complete-preview?view=query",
        headers=auth_headers,
    )
    merged = fitz.open(stream=response.data, filetype="pdf")
    assert merged.page_count == 2
    assert "generated home" in merged[0].get_text()
    assert "uploaded continuation" in merged[1].get_text()
    assert all("generated result" not in page.get_text() for page in merged)
    assert all("generated photos" not in page.get_text() for page in merged)
    merged.close()


def test_report_page_upload_rejects_non_word_or_pdf(client, auth_headers):
    response = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={
            "category": "report_page",
            "file": (BytesIO(b"not a report page"), "photo.png"),
        },
        content_type="multipart/form-data",
    ).get_json()
    assert response["code"] == 1
    assert "仅支持 Word 或 PDF" in response["message"]


def test_ncsa_document_has_three_fixed_pages(app):
    with app.app_context():
        report = Report.query.filter_by(report_no="NCSA-2026JF-0028").one()
        blob = build_ncsa_document(report, structured_content())
    document = Document(BytesIO(blob))
    page_breaks = sum(
        1
        for paragraph in document.paragraphs
        for run in paragraph.runs
        for node in run._r.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br")
        if node.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type") == "page"
    )
    assert len(document.tables) == 4
    assert page_breaks == 2
    assert len(document.inline_shapes) == 1
    assert document.inline_shapes[0].width / document.inline_shapes[0].height == pytest.approx(2, rel=0.02)
    assert "检 验 检 测 报 告" in "\n".join(p.text for p in document.paragraphs)


def test_generate_version_and_bind_to_workflow(client, auth_headers, app):
    response = client.put(
        "/api/reports/NCSA-2026JF-0028/document-content?view=query",
        headers=auth_headers,
        json=structured_content(),
    ).get_json()
    assert response["code"] == 0
    assert response["data"]["ready"] is True

    job = client.post(
        "/api/reports/NCSA-2026JF-0028/document-jobs",
        headers=auth_headers,
        json={"outputKind": "official"},
    ).get_json()
    assert job["code"] == 0
    status = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-jobs/{job['data']['id']}?view=query",
        headers=auth_headers,
    ).get_json()["data"]
    assert status["status"] == "completed"
    assert status["versionId"]

    versions = client.get(
        "/api/reports/NCSA-2026JF-0028/document-versions?view=query", headers=auth_headers,
    ).get_json()["data"]
    assert len(versions["rows"]) == 1
    assert versions["currentVersionId"] == status["versionId"]
    assert versions["rows"][0]["stale"] is False

    file_response = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-versions/{status['versionId']}/file?format=pdf&view=query",
        headers=auth_headers,
    )
    assert file_response.data.startswith(b"%PDF-")
    word_response = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-versions/{status['versionId']}/file?format=docx&view=query",
        headers=auth_headers,
    )
    assert len(Document(BytesIO(word_response.data)).inline_shapes) == 1

    with app.app_context():
        assert OperationAudit.query.filter_by(
            object_id="NCSA-2026JF-0028", action="report.document.generate",
        ).count() == 1


def test_review_and_approval_nodes_lock_report_content_and_attachments(client, auth_headers, app):
    with app.app_context():
        report = Report.query.filter_by(report_no="NCSA-2026JF-0028").one()
        report.status = "待审核"
        db.session.commit()

    content_response = client.put(
        "/api/reports/NCSA-2026JF-0028/document-content",
        headers=auth_headers,
        json=structured_content(),
    ).get_json()
    assert content_response["code"] == 1
    assert "正文已锁定" in content_response["message"]

    page_response = client.put(
        "/api/reports/NCSA-2026JF-0028/report-pages",
        headers=auth_headers,
        json={"pages": [{"title": "不应保存", "content": "审核环节禁止修改"}]},
    ).get_json()
    assert page_response["code"] == 1
    assert "内容已锁定" in page_response["message"]

    attachment_response = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={"file": (BytesIO(b"%PDF-1.4 locked"), "locked.pdf")},
        content_type="multipart/form-data",
    ).get_json()
    assert attachment_response["code"] == 1
    assert "附件已锁定" in attachment_response["message"]

    testinfo_response = client.put(
        "/api/reports/NCSA-2026JF-0028/testinfo",
        headers=auth_headers,
        json=loaded_form(client, "/api/reports/NCSA-2026JF-0028/testinfo", {
            "standard": "GB/T 19232-2019",
            "instrument": "不应修改的设备",
            "testStartDate": "2026-03-25",
            "testEndDate": "2026-03-26",
        }),
    ).get_json()
    assert testinfo_response["code"] == 1
    assert "不在检测数据录入节点" in testinfo_response["message"]

    preflight = client.get(
        "/api/reports/NCSA-2026JF-0028/document-preflight?view=query",
        headers=auth_headers,
    ).get_json()
    assert preflight["code"] == 0


def test_audit_bundle_appends_raw_record_and_content_change_expires_version(client, auth_headers, app):
    client.put(
        "/api/reports/NCSA-2026JF-0028/document-content",
        headers=auth_headers,
        json=structured_content(),
    )
    with app.app_context():
        db.session.add(ReportAttachment(
            report_no="NCSA-2026JF-0028",
            name="2026JF-0028原始记录.pdf",
            content_type="application/pdf",
            kind="PDF",
            source="原始记录",
            status="已上传",
            data=one_page_pdf("raw record"),
            uploaded_by="系统管理员",
        ))
        db.session.commit()

    job = client.post(
        "/api/reports/NCSA-2026JF-0028/document-jobs",
        headers=auth_headers,
        json={"outputKind": "audit"},
    ).get_json()["data"]
    status = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-jobs/{job['id']}?view=query", headers=auth_headers,
    ).get_json()["data"]
    assert status["status"] == "completed"
    response = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-versions/{status['versionId']}/file?format=pdf&view=query",
        headers=auth_headers,
    )
    merged = fitz.open(stream=response.data, filetype="pdf")
    assert merged.page_count == 2
    merged.close()

    official = client.post(
        "/api/reports/NCSA-2026JF-0028/document-jobs",
        headers=auth_headers,
        json={"outputKind": "official"},
    ).get_json()["data"]
    assert client.get(
        f"/api/reports/NCSA-2026JF-0028/document-jobs/{official['id']}?view=query", headers=auth_headers,
    ).get_json()["data"]["status"] == "completed"
    changed = structured_content()
    changed["remarks"] = "数据修改后应要求重新生成正式报告。"
    client.put(
        "/api/reports/NCSA-2026JF-0028/document-content", headers=auth_headers, json=changed,
    )
    preflight = client.get(
        "/api/reports/NCSA-2026JF-0028/document-preflight?view=query", headers=auth_headers,
    ).get_json()["data"]
    assert preflight["currentVersionStale"] is True
    with app.app_context():
        report = Report.query.filter_by(report_no="NCSA-2026JF-0028").one()
        report.status = "待审核"
        db.session.commit()
    blocked = client.post(
        "/api/reports/NCSA-2026JF-0028/action",
        headers=auth_headers,
        json={"action": "report.review.pass"},
    ).get_json()
    assert blocked["code"] == 1
    assert "重新生成" in blocked["message"]


def test_soft_deleted_attachment_cannot_download_or_enter_audit_bundle(
    client,
    auth_headers,
    app,
):
    with app.app_context():
        attachment = ReportAttachment(
            report_no="NCSA-2026JF-0028",
            name="已删除原始记录.pdf",
            content_type="application/pdf",
            kind="PDF",
            source="原始记录",
            status="已移除",
            data=one_page_pdf("deleted raw record"),
            uploaded_by="系统管理员",
            deleted_at=datetime.utcnow(),
        )
        db.session.add(attachment)
        db.session.commit()
        attachment_id = attachment.id

    missing = client.get(
        f"/api/attachments/{attachment_id}?view=query",
        headers=auth_headers,
    ).get_json()
    assert missing["code"] == 1

    client.put(
        "/api/reports/NCSA-2026JF-0028/document-content",
        headers=auth_headers,
        json=structured_content(),
    )
    job = client.post(
        "/api/reports/NCSA-2026JF-0028/document-jobs",
        headers=auth_headers,
        json={"outputKind": "audit"},
    ).get_json()["data"]
    status = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-jobs/{job['id']}?view=query",
        headers=auth_headers,
    ).get_json()["data"]
    response = client.get(
        f"/api/reports/NCSA-2026JF-0028/document-versions/{status['versionId']}/file?format=pdf&view=query",
        headers=auth_headers,
    )
    merged = fitz.open(stream=response.data, filetype="pdf")
    assert merged.page_count == 1
    merged.close()


def test_report_content_and_attachment_writes_recheck_data_entry_step(
    client,
    auth_headers,
    app,
    monkeypatch,
):
    step_message = "当前账号未授权本项目的数据录入步骤"
    monkeypatch.setattr(
        "app.blueprints.report_documents.report_data_entry_step_error",
        lambda _user, _report: step_message,
    )

    content_response = client.put(
        "/api/reports/NCSA-2026JF-0028/document-content",
        headers=auth_headers,
        json=structured_content(),
    ).get_json()
    assert content_response["code"] == 403
    assert content_response["message"] == step_message

    uploaded = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={"file": (BytesIO(b"%PDF-1.4 existing"), "existing.pdf")},
        content_type="multipart/form-data",
    ).get_json()
    assert uploaded["code"] == 0

    monkeypatch.setattr(
        "app.blueprints.attachments.report_data_entry_step_error",
        lambda _user, _report: step_message,
    )
    blocked_upload = client.post(
        "/api/reports/NCSA-2026JF-0028/attachments",
        headers=auth_headers,
        data={"file": (BytesIO(b"%PDF-1.4 blocked"), "blocked.pdf")},
        content_type="multipart/form-data",
    ).get_json()
    assert blocked_upload["code"] == 403
    assert blocked_upload["message"] == step_message

    blocked_delete = client.delete(
        f"/api/attachments/{uploaded['data']['id']}?view=query",
        headers=auth_headers,
    ).get_json()
    assert blocked_delete["code"] == 403
    assert blocked_delete["message"] == step_message

    with app.app_context():
        assert ReportDocumentContent.query.filter_by(
            report_no="NCSA-2026JF-0028",
        ).count() == 0
        rows = ReportAttachment.query.filter_by(
            report_no="NCSA-2026JF-0028",
        ).all()
        assert len(rows) == 1
        assert rows[0].deleted_at is None


def test_report_file_reads_delegate_exact_view_to_application_boundary(
    client,
    auth_headers,
    monkeypatch,
):
    document_scope_calls = []
    attachment_scope_calls = []

    monkeypatch.setattr(
        "app.blueprints.report_documents.get_authorized_report_for_view",
        lambda _user, report_no, view: (
            document_scope_calls.append((report_no, view)) or
            (None, None, "无当前业务模块查看权限")
        ),
    )
    document_response = client.get(
        "/api/reports/NCSA-2026JF-0028/document-preflight?view=review",
        headers=auth_headers,
    ).get_json()
    assert document_response["code"] == 403
    assert document_scope_calls == [("NCSA-2026JF-0028", "review")]

    monkeypatch.setattr(
        "app.blueprints.attachments.get_authorized_report_for_view",
        lambda _user, report_no, view: (
            attachment_scope_calls.append((report_no, view)) or
            (None, None, "无当前业务模块查看权限")
        ),
    )
    attachment_response = client.get(
        "/api/reports/NCSA-2026JF-0028/attachments?view=review",
        headers=auth_headers,
    ).get_json()
    assert attachment_response["code"] == 403
    assert attachment_scope_calls == [("NCSA-2026JF-0028", "review")]
