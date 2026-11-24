from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from app.functions.esign_service import EsignServiceError, _resolve_sign_positions


@pytest.fixture(autouse=True)
def isolate_pdf_extraction(monkeypatch):
    """These are layout-selection unit tests; real PDF coverage is separate."""
    monkeypatch.setattr("app.functions.esign_service._flow_source_pdf", lambda flow: flow)
    monkeypatch.setattr("app.functions.calibration_layout.calibration_positions", lambda pdf: None)
    monkeypatch.setattr("app.functions.report_signature_layout.keyword_positions",
                        lambda flow, words: flow.client.keyword_positions("file", words))


class _KeywordClient:
    def __init__(self, rows):
        self.rows = rows
        self.requested_keywords = []

    def keyword_positions(self, _file_id, _keywords):
        self.requested_keywords = list(_keywords)
        return [row for row in self.rows if row["keyword"] in _keywords]


def _row(keyword, *positions):
    return {
        "keyword": keyword,
        "searchResult": True,
        "positions": [
            {
                "pageNum": page,
                "coordinates": [{"positionX": x, "positionY": y,
                                 "pdfBounds": [x, 842-y-10, x+40, 842-y],
                                 "pageSize": [0, 0, 595, 842], "pageRotation": 0}],
            }
            for page, x, y in positions
        ],
    }


def _flow(client):
    return SimpleNamespace(positioning_json="{}", source_sha256="a" * 64, client=client)


def _resolve(rows):
    app = Flask(__name__)
    app.config.update(ESIGN_ORG_AUTOSIGN_ENABLED=False)
    with app.app_context():
        client = _KeywordClient(rows)
        return _resolve_sign_positions(client, _flow(client), "provider-file")


def test_joint_layout_selects_homepage_and_rejects_later_repeated_words():
    rows = [
        _row("主检", (2, 404.64, 45.387), (4, 172.198, 615.65)),
        _row("审核", (2, 230.4, 45.387), (4, 208.318, 615.65)),
        _row("批准", (2, 56.64, 45.387), (4, 244.437, 615.65)),
        _row("检验检测专用章", (2, 405.959, 117.268), (4, 256.559, 662.45)),
        _row("报告日期", (2, 415.559, 105.268)),
        _row("Chief Tester", (2, 404.64, 31.652)),
        _row("Verification", (2, 230.4, 31.652)),
        _row("Approval", (2, 56.64, 31.652)),
        _row("Seal", (2, 482.04, 115.533), (4, 443.52, 676.178)),
        _row("Date", (2, 460.2, 103.533), (2, 366.12, 482.493)),
    ]

    resolved, snapshot = _resolve(rows)

    assert {item["positionPage"] for item in resolved.values()} == {"2"}
    assert snapshot["requiredPage"] == 2
    assert snapshot["layoutLanguage"] == "zh"
    assert resolved["chief"]["positionX"] == 499.64
    assert resolved["reviewer"]["positionX"] == 325.4
    assert resolved["approver"]["positionX"] == 151.64
    assert snapshot["evidence"]["chief"]["offset"]["offsetX"] == 95
    assert all("keyword" not in item for item in resolved.values())


def test_pure_english_report_is_located_without_a_fixed_page_number():
    rows = [
        _row("Chief Tester", (3, 404.64, 31.652)),
        _row("Verification", (3, 230.4, 31.652)),
        _row("Approval", (3, 56.64, 31.652)),
        _row("Seal", (3, 482.04, 115.533)),
        _row("Date", (3, 460.2, 103.533), (3, 366.12, 482.493)),
    ]

    resolved, snapshot = _resolve(rows)

    assert snapshot["requiredPage"] == 3
    assert snapshot["layoutLanguage"] == "en"
    assert {item["positionPage"] for item in resolved.values()} == {"3"}
    assert resolved["chief"]["positionX"] == 499.64
    assert resolved["reviewer"]["positionX"] == 325.4
    assert resolved["approver"]["positionX"] == 151.64


def test_legacy_thirty_point_override_is_clamped_after_bilingual_signature_labels():
    app = Flask(__name__)
    app.config.update(
        ESIGN_ORG_AUTOSIGN_ENABLED=False,
        ESIGN_POSITION_OFFSETS={
            "chief": {"offsetX": 30},
            "reviewer": {"offsetX": 30},
            "approver": {"offsetX": 30},
        },
    )
    rows = [
        _row("主检", (2, 404.64, 45.387)),
        _row("审核", (2, 230.4, 45.387)),
        _row("批准", (2, 56.64, 45.387)),
        _row("检验检测专用章", (2, 405.959, 117.268)),
        _row("报告日期", (2, 415.559, 105.268)),
    ]

    with app.app_context():
        client = _KeywordClient(rows)
        resolved, snapshot = _resolve_sign_positions(client, _flow(client), "provider-file")

    assert resolved["chief"]["positionX"] == 499.64
    assert snapshot["evidence"]["chief"]["configuredOffset"]["offsetX"] == 30
    assert snapshot["evidence"]["chief"]["offset"]["offsetX"] == 95


def test_reversed_signature_order_is_not_a_report_homepage():
    rows = [
        _row("主检", (4, 172.198, 615.65)),
        _row("审核", (4, 208.318, 615.65)),
        _row("批准", (4, 244.437, 615.65)),
        _row("检验检测专用章", (4, 256.559, 662.45)),
        _row("报告日期", (4, 266.559, 650.45)),
    ]

    with pytest.raises(EsignServiceError) as raised:
        _resolve(rows)

    assert raised.value.code == "keyword_position_layout_missing"


def test_two_complete_layout_pages_fail_closed():
    rows = [
        _row("主检", (2, 405, 45), (5, 405, 45)),
        _row("审核", (2, 230, 45), (5, 230, 45)),
        _row("批准", (2, 56, 45), (5, 56, 45)),
        _row("检验检测专用章", (2, 406, 117), (5, 406, 117)),
        _row("报告日期", (2, 416, 105), (5, 416, 105)),
    ]

    with pytest.raises(EsignServiceError) as raised:
        _resolve(rows)

    assert raised.value.code == "keyword_position_layout_ambiguous"
    assert raised.value.details == {"candidatePages": [2, 5]}


def test_legacy_keyword_override_cannot_remove_required_layout_anchors():
    app = Flask(__name__)
    app.config.update(
        ESIGN_ORG_AUTOSIGN_ENABLED=False,
        ESIGN_POSITION_KEYWORDS={
            "chief": ["主检"], "reviewer": ["审核"], "approver": ["批准"],
            "cover": ["旧企业名称"], "date": ["日期"],
        },
    )
    rows = [
        _row("主检", (2, 405, 45)), _row("审核", (2, 230, 45)),
        _row("批准", (2, 56, 45)), _row("检验检测专用章", (2, 406, 117)),
        _row("报告日期", (2, 416, 105)),
    ]
    client = _KeywordClient(rows)

    with app.app_context():
        resolved, snapshot = _resolve_sign_positions(client, _flow(client), "provider-file")

    assert snapshot["requiredPage"] == 2
    assert "检验检测专用章" in client.requested_keywords
    assert "报告日期" in client.requested_keywords
    assert {item["positionPage"] for item in resolved.values()} == {"2"}
