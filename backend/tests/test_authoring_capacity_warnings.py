"""Real immutable DocParser rendering; no database, uploads, network or PDF service."""
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import unquote
from zipfile import ZipFile
import json

from flask import Flask, g
import pytest
from app import document_module, docparser_field_only
from app.docparser_field_worker import validate_fields, FieldError

PROFILE = dict(kind='product', center='LAB', language='CN', variant='Standard')


def test_long_sample_and_client_only_warn_in_authoring_and_formal():
    context = dict(ReportNo='LAB-2026QC1-0001', SampleName='超长测试样品名称' * 30, Client='测试单位' * 30)
    before = deepcopy(context)
    _, formal_audit = document_module.render_report(PROFILE, context)
    assert {'SAMPLENAME', 'CLIENT'} <= set(formal_audit['capacityWarnings'])
    blob, audit = document_module.render_report(PROFILE, context, authoring=True)
    assert {'SAMPLENAME', 'CLIENT'} <= set(audit['capacityWarnings'])
    with ZipFile(BytesIO(blob)) as archive:
        assert 'LAB-2026QC1-0001' in archive.read('word/document.xml').decode()
    assert context == before
    assert audit['completeReport'] is False
    _, formal_audit = document_module.render_report(PROFILE, context)
    assert {'SAMPLENAME', 'CLIENT'} <= set(formal_audit['capacityWarnings'])


@pytest.mark.parametrize('field,value,profile', [
    ('TestDate', '2026-01-01~2026-12-31\n' * 100, PROFILE),
    ('Basis', '校准依据完整名称和编号' * 100, {**PROFILE, 'kind':'calibration'}),
])
def test_layout_capacity_warnings_also_allow_authoring(field, value, profile):
    context = {'ReportNo':'LAB-2026JC-0001', field:value}
    _, formal_audit = document_module.render_report(profile, context)
    assert field in formal_audit['capacityWarnings']
    blob, audit = document_module.render_report(profile, context, authoring=True)
    assert field in audit['capacityWarnings']
    assert blob.startswith(b'PK')


def test_normal_template_has_no_warning():
    _, audit = document_module.render_report(PROFILE, {'ReportNo':'LAB-2026QC1-0001','SampleName':'正常样品'}, authoring=True)
    assert audit['capacityWarnings'] == []


@pytest.mark.parametrize('kind,variant,language', [
    ('product','Extended','CN'), ('product','Standard','EN'),
    ('sampling','Standard','CN'), ('sampling','Extended','EN'),
    ('engineering','Standard','CN'), ('inspection','Standard','CN'),
    ('calibration','Standard','CN'),
])
def test_authoring_warning_works_across_report_templates(kind, variant, language):
    blob, audit = document_module.render_report(
        {**PROFILE, 'kind':kind, 'variant':variant, 'language':language},
        {'ReportNo':'LAB-2026JC-0001','SampleName':'LONG SAMPLE NAME '*40}, authoring=True)
    assert {'SAMPLENAME','SampleName'}.intersection(audit['capacityWarnings'])
    assert blob.startswith(b'PK')


def test_location_truncation_notice_is_preserved_alongside_warning():
    address = '完整检测地址不能丢失' * 80
    _, audit = document_module.render_report({**PROFILE, 'kind':'calibration'},
        {'ReportNo':'LAB-2026QC1-0001','SampleName':'长样品名'*40,'Place':address}, authoring=True)
    assert audit['noticeCodes'] == []
    assert {'SAMPLENAME','SampleName'}.intersection(audit['capacityWarnings'])
    assert {'Place', 'PLACE'}.intersection(audit['capacityWarnings'])


def test_structural_and_boolean_errors_remain_blocking():
    for context, actual in [({'CMA':True}, {'CMA':False}), ({'Instruments':'a\tb\tc\td\te\tf'}, {'INSTRUMENTS':[]})]:
        with pytest.raises(FieldError):
            validate_fields(context, actual, capacity_warnings=[])
    # A path-looking text field remains literal text, never a local file read.
    blob, _ = document_module.render_report(PROFILE, {'Conclusion':'/private/file.docx'}, authoring=True)
    with ZipFile(BytesIO(blob)) as archive:
        assert '/private/file.docx' in archive.read('word/document.xml').decode()


def test_download_route_explicitly_requests_authoring_and_emits_warning_header(monkeypatch):
    from app.blueprints import report_documents as route
    app = Flask(__name__)
    user = SimpleNamespace(action_codes=lambda: ['report.attachment.upload'])
    report = SimpleNamespace(status='检测录入中')
    monkeypatch.setattr(route, '_report_for_user', lambda _: report)
    monkeypatch.setattr(route, 'report_data_entry_step_error', lambda *_: None)
    monkeypatch.setattr(route, 'report_content_editable', lambda _: True)
    monkeypatch.setattr(docparser_field_only, 'applies_to', lambda _: True)
    def render(selected, *, authoring=False):
        assert selected is report and authoring is True
        return b'word-test', {'sha256':'a'*64, 'templateSelection':{'filename':'template.docx'}, 'capacityWarnings':['SAMPLENAME','TestDate']}
    monkeypatch.setattr(docparser_field_only, 'render_preview', render)
    with app.test_request_context():
        g.current_user = user
        response = route.continuation_template.__wrapped__('TEST-0001')
        assert response.status_code == 200 and response.data == b'word-test'
        assert 'wordprocessingml' in response.content_type
        assert json.loads(unquote(response.headers['X-Template-Capacity-Warnings'])) == ['SAMPLENAME','TestDate']
        assert 'no-store' in response.headers['Cache-Control']
