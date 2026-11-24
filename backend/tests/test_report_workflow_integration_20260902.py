from io import BytesIO

import fitz
import pytest

from app import create_app
from app.docx_pdf import add_top_right_page_numbers, image_to_pdf
from app.extensions import db
from app.models import Report, ReportAttachment
from app.report_documents import (
    _report_page_pdfs,
    _selected_other_attachment_pdfs,
    attachment_meta,
    content_dict,
)
from app.seed import seed_all
from config import Config


class WorkflowTestConfig(Config):
    TESTING = True
    PROD = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET = "workflow-test-secret-with-at-least-thirty-two-bytes"
    ADMIN_PASSWORD = "TestAdmin#2026!"
    JWT_SECRET_IS_DEFAULT = False


def pdf_page(text):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    blob = document.tobytes()
    document.close()
    return blob


@pytest.fixture()
def workflow_app(tmp_path):
    class IsolatedConfig(WorkflowTestConfig):
        STORAGE_ROOT = str(tmp_path / "storage")

    application = create_app(IsolatedConfig)
    with application.app_context():
        db.create_all()
        seed_all()
        from app.models import Department, Project, ProjectStep, User
        from app.seed_data import PROJECT_AUTHORIZATION_STEPS
        from app.security import hash_password
        admin_user = User.query.filter_by(account="admin").first()
        if admin_user is not None:
            admin_user.password_hash = hash_password("123456")
            admin_user.must_change_password = False
        dept = Department.query.filter_by(name="空调设备检测部").first()
        if dept is None:
            dept = Department(code="AC_WORKFLOW", name="空调设备检测部")
            db.session.add(dept)
            db.session.flush()
        proj = Project.query.filter_by(name="workflow", department_id=dept.id).first()
        if proj is None:
            proj = Project(code="WF01", display_code="WF01", number_code="EV", name="workflow", department_id=dept.id, active=True)
            db.session.add(proj)
            db.session.flush()
            for step_code, step_name in PROJECT_AUTHORIZATION_STEPS:
                db.session.add(ProjectStep(project_id=proj.id, step_code=step_code, step_name=step_name))
        report = Report(
            report_no="LAB-2026EV-0001",
            sample_no="2026EV-0001",
            project="workflow",
            project_name="workflow sample",
            client="client",
            status="检测录入中",
            department="空调设备检测部",
            owner="tester",
            detail={},
        )
        db.session.add(report)
        db.session.commit()
    yield application


def test_page_numbers_leave_cover_blank_and_number_following_pages():
    merged = fitz.open()
    for label in ("cover", "home", "body"):
        with fitz.open(stream=pdf_page(label), filetype="pdf") as page_pdf:
            merged.insert_pdf(page_pdf)
    raw = merged.tobytes()
    merged.close()

    numbered = add_top_right_page_numbers(raw)
    with fitz.open(stream=numbered, filetype="pdf") as document:
        text = [page.get_text().replace("\u00a0", " ") for page in document]
        assert "Page 1 of 2" not in text[0]
        assert "Page 1 of 2" in text[1]
        assert "Page 2 of 2" in text[2]


def test_page_numbers_can_start_on_first_page_when_document_has_no_cover():
    numbered = add_top_right_page_numbers(pdf_page("home"), skip_first_page=False)
    with fitz.open(stream=numbered, filetype="pdf") as document:
        assert "Page 1 of 1" in document[0].get_text().replace("\u00a0", " ")


def test_image_attachment_converts_to_single_a4_pdf():
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 2), False)
    pixmap.clear_with(220)
    png = pixmap.tobytes("png")
    converted = image_to_pdf(png)
    with fitz.open(stream=converted, filetype="pdf") as document:
        assert document.page_count == 1
        assert document[0].rect.width == pytest.approx(595.28, abs=0.2)


def test_completed_report_replaces_legacy_pages_and_other_order_is_persisted(workflow_app):
    with workflow_app.app_context():
        report = Report.query.filter_by(report_no="LAB-2026EV-0001").one()
        legacy = ReportAttachment(
            report_no=report.report_no, name="legacy.pdf", content_type="application/pdf",
            kind="PDF", source="报告后续页", status="已上传", data=pdf_page("legacy"),
        )
        superseded = ReportAttachment(
            report_no=report.report_no, name="old.pdf", content_type="application/pdf",
            kind="PDF", source="完整报告正文", status="已替代", data=pdf_page("old"),
        )
        current = ReportAttachment(
            report_no=report.report_no, name="current.pdf", content_type="application/pdf",
            kind="PDF", source="完整报告正文", status="已上传", data=pdf_page("current"),
        )
        first = ReportAttachment(
            report_no=report.report_no, name="first.pdf", content_type="application/pdf",
            kind="PDF", source="其他附件", status="已上传", data=pdf_page("first"),
        )
        second = ReportAttachment(
            report_no=report.report_no, name="second.pdf", content_type="application/pdf",
            kind="PDF", source="其他附件", status="已上传", data=pdf_page("second"),
        )
        db.session.add_all([legacy, superseded, current, first, second])
        db.session.flush()
        report.detail = {
            "reportComposition": {
                "includedOtherAttachmentIds": [second.id, first.id, second.id],
            },
        }
        db.session.commit()

        pages, warnings = _report_page_pdfs(report.report_no)
        assert warnings == []
        assert len(pages) == 1
        with fitz.open(stream=pages[0], filetype="pdf") as document:
            assert "current" in document[0].get_text()

        others = _selected_other_attachment_pdfs(report)
        assert len(others) == 2
        with fitz.open(stream=others[0], filetype="pdf") as document:
            assert "second" in document[0].get_text()
        with fitz.open(stream=others[1], filetype="pdf") as document:
            assert "first" in document[0].get_text()

        content = content_dict(report)
        assert content["compositionOptions"]["includedOtherAttachmentIds"] == [second.id, first.id]
        assert attachment_meta(current)["category"] == "completed_report"
        assert attachment_meta(superseded)["superseded"] is True
        assert attachment_meta(first, [first.id])["selectedForOfficial"] is True


def admin_headers(workflow_app):
    client = workflow_app.test_client()
    response = client.post("/api/auth/login", json={"account": "admin", "password": "123456"})
    body = response.get_json()
    assert body["code"] == 0
    return client, {"Authorization": f"Bearer {body['data']['token']}"}


def test_unsaved_entrust_preview_failure_is_json_not_flask_html(workflow_app, monkeypatch):
    client, headers = admin_headers(workflow_app)
    monkeypatch.setattr("app.docparser_field_only.enabled", lambda: True)
    monkeypatch.setattr(
        "app.docparser_field_only.render_entrust",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("模板字段不完整")),
    )
    response = client.post(
        "/api/samples/entrust-preview",
        headers=headers,
        json={"templateKind": "product", "reportNo": "LAB-2026EV-0001"},
    )
    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json()["message"] == "模板字段不完整"
    assert not response.data.lstrip().lower().startswith(b"<!doctype")


def test_unsaved_entrust_preview_uses_latest_template_adapter(workflow_app, monkeypatch):
    from zipfile import ZipFile
    client, headers = admin_headers(workflow_app)
    calls = []
    valid_zip = BytesIO()
    with ZipFile(valid_zip, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
    sample_docx = valid_zip.getvalue()
    monkeypatch.setattr("app.docparser_field_only.enabled", lambda: True)
    monkeypatch.setattr(
        "app.docparser_field_only.render_entrust",
        lambda _entrust, _report, kind, *_extra: (
            calls.append(kind) or sample_docx,
            {"templateSelection": {"filename": "LAB-Entrust-4204g-202601_tpl.docx"}},
        ),
    )
    monkeypatch.setattr("app.docx_pdf.docx_to_pdf_wps", lambda _blob: pdf_page("entrust"))
    monkeypatch.setattr("app.blueprints.samples._business_form_page_count", lambda _pdf, _kind: 3)
    response = client.post(
        "/api/samples/entrust-preview",
        headers=headers,
        json={"templateKind": "engineering", "reportNo": "LAB-2026EV-0001"},
    )
    assert response.status_code == 200 and response.content_type == "application/pdf"
    assert calls == ["engineering"]
    assert response.headers["X-Template-Selection"] == "LAB-Entrust-4204g-202601_tpl.docx"


def test_completed_report_upload_supersedes_previous_source(workflow_app, monkeypatch):
    client, headers = admin_headers(workflow_app)
    monkeypatch.setattr("app.docparser_field_only.applies_to", lambda _report: False)
    first = client.post(
        "/api/reports/LAB-2026EV-0001/attachments",
        headers=headers,
        data={"category": "completed_report", "file": (BytesIO(pdf_page("first")), "first.pdf")},
        content_type="multipart/form-data",
    ).get_json()
    second = client.post(
        "/api/reports/LAB-2026EV-0001/attachments",
        headers=headers,
        data={"category": "completed_report", "file": (BytesIO(pdf_page("second")), "second.pdf")},
        content_type="multipart/form-data",
    ).get_json()
    assert first["code"] == 0 and second["code"] == 0
    listing = client.get(
        "/api/reports/LAB-2026EV-0001/attachments?view=query", headers=headers,
    ).get_json()["data"]["rows"]
    assert [row["category"] for row in listing] == ["completed_report", "completed_report"]
    assert listing[0]["superseded"] is True and listing[0]["active"] is False
    assert listing[1]["superseded"] is False and listing[1]["active"] is True


def test_authoring_template_alias_returns_full_word_download(workflow_app, monkeypatch):
    client, headers = admin_headers(workflow_app)
    monkeypatch.setattr("app.blueprints.report_documents.report_data_entry_step_error", lambda *_: None)
    monkeypatch.setattr("app.blueprints.report_documents.report_content_editable", lambda _report: True)
    monkeypatch.setattr("app.docparser_field_only.applies_to", lambda _report: True)
    monkeypatch.setattr(
        "app.docparser_field_only.render_preview",
        lambda _report, **_kw: (b"PK-full-report-template", {
            "sha256": "0" * 64,
            "templateSelection": {"filename": "LAB-Report-Product-CN-Standard-202609_tpl.docx"},
        }),
    )
    response = client.get(
        "/api/reports/LAB-2026EV-0001/authoring-template", headers=headers,
    )
    assert response.status_code == 200
    assert "wordprocessingml" in response.content_type
    assert response.data == b"PK-full-report-template"
    assert response.headers["X-Template-Selection"].endswith("_tpl.docx")


def test_document_content_persists_selected_other_attachment_order(workflow_app, monkeypatch):
    client, headers = admin_headers(workflow_app)
    monkeypatch.setattr("app.docparser_field_only.applies_to", lambda _report: False)
    uploads = []
    for name in ("first.pdf", "second.pdf"):
        uploads.append(client.post(
            "/api/reports/LAB-2026EV-0001/attachments",
            headers=headers,
            data={"category": "other", "file": (BytesIO(pdf_page(name)), name)},
            content_type="multipart/form-data",
        ).get_json()["data"])
    content = client.get(
        "/api/reports/LAB-2026EV-0001/document-content?view=query", headers=headers,
    ).get_json()["data"]
    content["compositionOptions"] = {
        "includedOtherAttachmentIds": [uploads[1]["id"], uploads[0]["id"]],
    }
    saved = client.put(
        "/api/reports/LAB-2026EV-0001/document-content",
        headers=headers,
        json=content,
    ).get_json()
    assert saved["code"] == 0
    assert saved["data"]["content"]["compositionOptions"]["includedOtherAttachmentIds"] == [
        uploads[1]["id"], uploads[0]["id"],
    ]
