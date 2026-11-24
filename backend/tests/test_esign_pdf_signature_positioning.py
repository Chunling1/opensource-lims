"""Synthetic, anonymous PDF fixtures; no provider/network/signature images."""
import hashlib
import json
from types import SimpleNamespace

import fitz
import pytest
from flask import Flask

from app.functions import esign_service as service
from app.functions.dual_chief_layout import dual_chief_positions
from app.functions.report_seal_layout import organization_positions

pytest_plugins = ("testkit.fixtures",)


def report_pdf(top=740, signature_page=2, bilingual=True, date_label="签发日期",
               rotation=0, extra_layout=False, chief_x=405):
    doc = fitz.open()
    for _ in range(signature_page):
        doc.new_page(width=595, height=842)
    doc[0].insert_text((170, 700), "Example Testing Lab Co., Ltd.", fontsize=14)
    page = doc[signature_page-1]

    def label(x, y, text, chinese=False):
        page.insert_text((x, y), text, fontsize=10, fontname="china-s" if chinese else "helv")

    def layout(y):
        if bilingual:
            label(406, y-65, "检验检测专用章", True)
            label(490, y-65, "Seal")
            label(416, y-50, date_label, True)
            label(465, y-50, "Date:")
        else:
            label(406, y-65, "Seal")
            label(416, y-50, "Date:")
        for x, zh, en in [(56, "批  准", "Approval"), (230, "审  核", "Verification"),
                          (chief_x, "主  检", "Chief Tester")]:
            if bilingual:
                label(x, y, zh + ":", True)
                label(x, y+14, en)
            else:
                label(x, y, en)

    layout(top)
    if extra_layout:
        other = doc.new_page(width=595, height=842)
        other.show_pdf_page(other.rect, fitz.open(stream=doc.tobytes(), filetype="pdf"), signature_page-1)
        page = doc[signature_page-1]
    # Repeated signature/seal words in a notice must never become field anchors.
    if top < 600:
        label(60, top+110, "NOTICE")
        label(60, top+130, "Chief Tester, Verification, Approval; Inspection and Testing Special Seal")
        if bilingual:
            label(60, top+150, "检测报告无主检、审核、批准签字无效", True)
    page.set_rotation(rotation)
    result = doc.tobytes()
    doc.close()
    return result


class NoProviderCoordinates:
    def keyword_positions(self, *_args):
        pytest.fail("Automatic positions must come from the locked PDF")


def resolve_pdf(monkeypatch, pdf, *, manual=None, autosign=False):
    app = Flask(__name__)
    app.config["ESIGN_ORG_AUTOSIGN_ENABLED"] = autosign
    flow = SimpleNamespace(source_sha256=hashlib.sha256(pdf).hexdigest(),
                           positioning_json=json.dumps(manual or {}))
    monkeypatch.setattr(service, "_flow_source_pdf", lambda _flow: pdf)
    with app.app_context():
        return service._resolve_sign_positions(NoProviderCoordinates(), flow, "locked-file")


@pytest.mark.parametrize("bilingual", [True, False])
@pytest.mark.parametrize("page_no,top", [(2, 780), (2, 450), (3, 320)])
def test_positions_follow_actual_page_and_moving_label_block(monkeypatch, bilingual, page_no, top):
    pdf = report_pdf(top=top, signature_page=page_no, bilingual=bilingual)
    positions, snapshot = resolve_pdf(monkeypatch, pdf)
    assert snapshot["sourceSha256"] == hashlib.sha256(pdf).hexdigest()
    assert snapshot["layoutLanguage"] == ("zh" if bilingual else "en")
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        page = doc[page_no-1]
        for role, en in [("approver", "Approval"), ("reviewer", "Verification"), ("chief", "Chief Tester")]:
            pos = positions[role]
            assert pos["positionPage"] == str(page_no)
            # Independent text search and rendering coordinates: field is on
            # the visible label row, safely to its right, not at a fixed footer.
            label = page.search_for(en)[0]
            cy = page.rect.height-pos["positionY"]
            assert top-6 < cy < top+12
            assert pos["positionX"]-36 >= label.x1+4.9
            assert not any(fitz.Rect(word[:4]).intersects(fitz.Rect(
                pos["positionX"]-28.8, cy-28.8, pos["positionX"]+28.8, cy+28.8
            )) for word in page.get_text("words"))
            field = service._sign_field("locked-file", "TEST", SimpleNamespace(role_code=role), pos)
            assert field["normalSignFieldConfig"]["signFieldPosition"] == pos


def test_vertical_translation_is_exact(monkeypatch):
    bottom, _ = resolve_pdf(monkeypatch, report_pdf(top=780))
    moved, _ = resolve_pdf(monkeypatch, report_pdf(top=420))
    for role in bottom:
        assert moved[role]["positionY"]-bottom[role]["positionY"] == pytest.approx(360, abs=.001)


@pytest.mark.parametrize("date_label", ["签发日期", "报告日期"])
def test_chinese_date_alias_and_organization_seals(monkeypatch, date_label):
    pdf = report_pdf(top=420, signature_page=3, date_label=date_label)
    positions, snapshot = resolve_pdf(monkeypatch, pdf, autosign=True)
    assert snapshot["layoutLanguage"] == "zh"
    anchor = snapshot["evidence"]["cover"]["providerPosition"]
    seals, _ = organization_positions(pdf, anchor)
    assert seals["cover"]["positionPage"] == "3"
    assert seals["titleCover"]["positionPage"] == "1"
    assert positions["date"]["positionPage"] == "3"


def test_dual_chief_uses_the_same_moving_row(monkeypatch):
    pdf = report_pdf(top=420, signature_page=3, chief_x=395)
    positions, _ = resolve_pdf(monkeypatch, pdf)
    result, sizes, _ = dual_chief_positions(pdf, positions)
    assert result["chief2"]["positionY"] == result["chief"]["positionY"]
    assert result["chief2"]["positionPage"] == "3"
    assert sizes == {"chief": 72, "chief2": 72}


@pytest.mark.parametrize("kwargs,code", [
    ({"rotation": 90}, "report_signature_layout_invalid"),
    ({"top": 830}, "report_signature_layout_invalid"),
    ({"extra_layout": True}, "keyword_position_layout_ambiguous"),
])
def test_unsafe_or_ambiguous_layout_does_not_dispatch(monkeypatch, kwargs, code):
    with pytest.raises(service.EsignServiceError) as error:
        resolve_pdf(monkeypatch, report_pdf(**kwargs))
    assert error.value.code == code


def test_valid_manual_positions_remain_authoritative(monkeypatch):
    pdf = report_pdf(top=420)
    positions = {role: {"positionPage": "2", "positionX": x, "positionY": 400}
                 for role, x in [("chief", 500), ("reviewer", 325), ("approver", 151)]}
    manual = {"mode": "manual", "sourceSha256": hashlib.sha256(pdf).hexdigest(),
              "providerFileId": "locked-file", "positions": positions}
    result, snapshot = resolve_pdf(monkeypatch, pdf, manual=manual)
    assert result == positions
    assert snapshot["mode"] == "manual"


def test_old_manual_snapshot_cannot_override_a_new_pdf(monkeypatch):
    pdf = report_pdf(top=420, signature_page=3)
    manual = {"mode": "manual", "sourceSha256": "old", "providerFileId": "locked-file",
              "positions": {role: {"positionPage": "2", "positionX": 100, "positionY": 45}
                            for role in ("chief", "reviewer", "approver")}}
    positions, snapshot = resolve_pdf(monkeypatch, pdf, manual=manual)
    assert snapshot["mode"] == "keyword"
    assert all(p["positionPage"] == "3" and p["positionY"] > 400 for p in positions.values())


def test_resolution_reads_locked_version_and_checks_hash(isolated_app):
    from app.extensions import db
    from app.models import ReportDocumentVersion
    pdf = report_pdf(top=420, signature_page=3)
    with isolated_app.app_context():
        version = ReportDocumentVersion(
            report_no="TEST-POSITION", output_kind="official", version_no=1,
            status="approved", profile_code="TEST", composition=[], snapshot={}, warnings=[],
            source_hash="test", sha256=hashlib.sha256(pdf).hexdigest(), pdf_data=pdf,
            created_by="testkit",
        )
        db.session.add(version)
        db.session.flush()
        flow = SimpleNamespace(report_document_version_id=version.id,
                               source_sha256=version.sha256, positioning_json="{}")
        positions, _ = service._resolve_sign_positions(NoProviderCoordinates(), flow, "locked-file")
        assert positions["reviewer"]["positionPage"] == "3"
        version.pdf_data = report_pdf(top=780)
        with pytest.raises(service.EsignServiceError) as error:
            service._resolve_sign_positions(NoProviderCoordinates(), flow, "locked-file")
        assert error.value.code == "source_hash_mismatch"


def test_calibration_layout_remains_separate(monkeypatch):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 70), "Calibration Certificate")
        for x, text in [(56, "批准人"), (230, "审核员"), (405, "校准员")]:
            page.insert_text((x, 700), text, fontname="china-s", fontsize=10)
        page.insert_text((405, 650), "签发日期", fontname="china-s", fontsize=10)
        page.draw_line((50, 780), (545, 780))
        pdf = doc.tobytes()
    positions, snapshot = resolve_pdf(monkeypatch, pdf)
    assert snapshot["layoutKind"] == "calibration"
    assert snapshot["mode"] == "pdf-layout"
    assert positions["chief"]["positionPage"] == "1"
