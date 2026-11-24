"""Standard titles in report output, including historical saved display text."""
from testkit.forms import loaded_form
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

import pytest
from lxml import etree

from app import docparser_field_only as fields, document_module
from app.functions.report_standard_text import format_standard_titles, format_report_standards
from test_docparser_deep_integration import report
from test_admin_corrections import workspace, headers, url

pytest_plugins = ("testkit.fixtures",)


def test_display_preferences_save_reload_and_render(workspace):
    from app.models import Standard
    from app.extensions import db
    from app.report_documents import report_values
    client, actors, rows, _ = workspace
    item = rows[2]
    codes = ["GB 1-2024", "GB 2-2024", "GB 3-2024"]
    for index, code in enumerate(codes):
        db.session.add(Standard(code=code, name=f"名称{index + 1}"))
    db.session.commit()
    styles = dict(zip(codes, ["CN", "EN", "none"]))
    def save_preferences(extra):
        record = client.get(url('reports', item), headers=headers(actors[1])).get_json()['data']
        return client.put(f'/api/reports/{item.report_no}/testinfo', headers=headers(actors[1]), json=loaded_form(client, f'/api/reports/{item.report_no}/testinfo', {
            'standards': codes, 'standardShowName': True,
            'adminCorrection': {'revision': record['revision'], 'confirmed': True, 'reason': '核对报告显示'}, **extra,
        })).get_json()
    result = save_preferences({'standardTitleStyles': styles, 'standardSeparatorText': '；\n', 'equipmentSeparatorText': '\n'})
    assert result['code'] == 0, result
    db.session.refresh(item)
    check = item.detail['checkInput']
    expected = 'GB 1-2024 《名称1》；\nGB 2-2024 <名称2>；\nGB 3-2024 名称3'
    assert check['standardTitleStyles'] == styles
    assert check['standardDisplay'] == expected
    assert report_values(item)['testBasis'] == expected
    # Omitted preferences from an old client must preserve explicit choices.
    assert save_preferences({})['code'] == 0
    assert item.detail['checkInput']['standardDisplay'] == expected
    assert save_preferences({'standardSeparatorText': ''})['code'] == 0
    assert report_values(item)['testBasis'] == expected.replace('；\n', '')
    assert save_preferences({'standardSeparatorText': '<script>'})['code'] != 0
    db.session.refresh(item)
    assert item.detail['checkInput']['standardDisplay'] == expected.replace('；\n', '')


def test_equipment_separator_preserves_snapshot_order():
    from app.functions.report_instrument_text import report_instrument_text
    rows = [{'archiveNo': 'A', 'name': '温度计', 'spec': 'T1'}, {'archiveNo': 'B', 'name': '压力计', 'spec': 'P1'}]
    assert report_instrument_text(rows, separator='；\n') == 'A 温度计 T1；\nB 压力计 P1'
    assert report_instrument_text(rows, separator='') == 'A 温度计 T1B 压力计 P1'


@pytest.mark.parametrize('language', ['CN', 'EN'])
def test_explicit_styles_survive_language_and_actual_docx(isolated_app, monkeypatch, language):
    from app.blueprints import report_publication
    monkeypatch.setattr(report_publication, 'report_qr_url', lambda _: 'https://example.invalid/report/styles')
    with isolated_app.app_context():
        item = report()
        item.id = 0
        item.report_no = 'LAB-TEST-001'
        item.department = ''
        item.detail['rawSample']['reportLanguage'] = language
        codes = ['GB 1-2024', 'GB 2-2024', 'GB 3-2024']
        styles = dict(zip(codes, ['CN', 'EN', 'none']))
        display = format_report_standards(codes, dict.fromkeys(codes, 'Door'), True, styles=styles, separator_text='')
        item.detail['checkInput'] = {'standardDisplay': display, 'standardTitleStyles': styles}
        context = fields.report_context(item)
        assert context['Basis'] == 'GB 1-2024 《Door》GB 2-2024 <Door>GB 3-2024 Door'
        blob, _ = document_module.render_report(fields.profile_for(item), context)
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        assert context['Basis'] in text


@pytest.mark.parametrize("value,cn,en", [
    ("GB 12955-2024 防火门；GB/T29049-2012 整樘门 垂直荷载试验",
     "GB 12955-2024 《防火门》；GB/T29049-2012 《整樘门 垂直荷载试验》",
     "GB 12955-2024 <防火门>；GB/T29049-2012 <整樘门 垂直荷载试验>"),
    ("GB/T 10080-2001 Doors; ISO 1234:2024 Thermal performance",
     "GB/T 10080-2001 《Doors》; ISO 1234:2024 《Thermal performance》",
     "GB/T 10080-2001 <Doors>; ISO 1234:2024 <Thermal performance>"),
    ("GB 1234-2024《《名称》》\nGB 5678-2024 <Other title>",
     "GB 1234-2024《名称》\nGB 5678-2024 《Other title》",
     "GB 1234-2024<名称>\nGB 5678-2024 <Other title>"),
    ("GB 1234-2024；GB/T 5678-2024", "GB 1234-2024；GB/T 5678-2024", "GB 1234-2024；GB/T 5678-2024"),
    ("GB 1234-2024 《包括 GB 5678-2020 的要求》", "GB 1234-2024 《包括 GB 5678-2020 的要求》", "GB 1234-2024 <包括 GB 5678-2020 的要求>"),
    ("BS EN ISO 1234-2024 Test", "BS EN ISO 1234-2024 《Test》", "BS EN ISO 1234-2024 <Test>"),
    ("", "", ""), ("/", "/", "/"), ("按委托要求", "按委托要求", "按委托要求"),
])
def test_saved_text(value, cn, en):
    for language, expected in [("CN", cn), ("EN", en)]:
        assert format_standard_titles(value, language=language) == expected
        assert format_standard_titles(expected, language=language) == expected


@pytest.mark.parametrize("language,expected", [("CN", "《名称》"), ("EN", "<名称>")])
def test_structured_display_keeps_code_only_choice(language, expected):
    names = {"GB 1-2024": "《<名称>》"}
    assert format_report_standards(list(names), names, True, language=language) == "GB 1-2024 " + expected
    assert format_report_standards(list(names), names, False, language=language) == "GB 1-2024"
    assert format_report_standards(["GB 2-2024"], names, True, language=language) == "GB 2-2024"


PROFILES = [(kind, variant, language)
            for kind, variants in [("产品报告", ["Standard", "Extended"]),
                                   ("抽样报告", ["Standard", "Extended"]),
                                   ("工程报告", ["Standard"]), ("检验报告", ["Standard"])]
            for variant in variants for language in ["CN", "EN"]]
PROFILES.append(("校准报告", "Standard", "CN"))


@pytest.mark.parametrize("kind,variant,language", PROFILES)
def test_actual_report_output(isolated_app, monkeypatch, kind, variant, language):
    from app.blueprints import report_publication
    monkeypatch.setattr(report_publication, "report_qr_url", lambda _: "https://example.invalid/report/standard-title")
    with isolated_app.app_context():
        item = report(kind)
        item.id = 0
        item.report_no = "LAB-TEST-001"
        item.department = ""
        item.detail["rawSample"].update(reportLanguage=language, reportTemplateVariant=variant,
                                       standardJudge="GB 12955-2024《防火门》")
        title = "Door test" if language == "EN" else "防火门"
        value = "GB 12955-2024 " + title
        expected = "GB 12955-2024 " + ("<" + title + ">" if language == "EN" else "《" + title + "》")
        for source in ("summary", "standardDisplay", "rawSample"):
            item.detail["checkInput"] = {}
            item.detail["summary"] = []
            item.detail["rawSample"]["testBasis"] = value
            if source == "summary":
                item.detail["summary"] = [{"title": "实验信息", "fields": [["检测依据", value]]}]
            elif source == "standardDisplay":
                item.detail["checkInput"] = {"standardDisplay": value}
                item.detail["rawSample"]["testBasis"] = "GB 12955-2024"
            before = deepcopy(item.detail)
            context = fields.report_context(item)
            assert context["Basis"] == expected
            assert context["Criteria"] == ("GB 12955-2024<防火门>" if language == "EN" else "GB 12955-2024《防火门》")
            assert item.detail == before
        blob, _ = document_module.render_report(fields.profile_for(item), context)
        with ZipFile(BytesIO(blob)) as archive:
            text = "".join(etree.fromstring(archive.read("word/document.xml")).xpath('//*[local-name()="t"]/text()'))
        if kind in ("工程报告", "检验报告"):
            # These supplier templates contain a fixed cover only; the uploaded
            # body owns the basis. Do not invent a new field on that cover.
            template = document_module.VENDOR / "assets/templates" / fields.profile_for(item)["filename"]
            with ZipFile(template) as archive:
                source = archive.read("word/document.xml").decode("utf-8")
            assert "Basis" not in source and "Criteria" not in source
            assert expected not in text
        else:
            assert expected in text  # Angle brackets survive actual DOCX XML escaping.
        assert item.detail == before
