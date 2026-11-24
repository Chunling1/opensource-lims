from copy import deepcopy
import pytest
from app.production_dates import canonical_detail, normalize_rows, display_rows
from app.report_date_policy import sample_date_values, report_date_error
from app.report_date_rules import validate_date_order
from app.report_date_display import production_date_text
from app.models import Report
from test_sample_pricing import business, create, detail
from test_compliance_review_round import case
from test_return_form_preservation import form_case

pytest_plugins = ('testkit.fixtures',)
ROWS = [dict(name='室外机', precision='day', value='2026-10-20', note='以铭牌为准'),
        dict(name='室内机', precision='month', value='2026-09', note='')]

def test_all_components_are_checked_and_summary_is_a_display_mirror():
    source = {'rawSample': {'productionDates': deepcopy(ROWS), 'produceDate':'/', 'sendDate':'2026-10-19'},
              'summary':[{'title':'送样信息','fields':[['生产日期','/']]}]}
    normalized = canonical_detail(source)
    assert normalized['rawSample']['produceDate'] == display_rows(ROWS)
    assert normalized['summary'][0]['fields'][0][1] == display_rows(ROWS)
    assert source['rawSample']['produceDate'] == '/'
    dates = sample_date_values(normalized, '2026-11-01')
    assert '室外机：送样日期不得早于生产日期' in validate_date_order(dates)
    assert validate_date_order({**dates,'send':'2026-10-20'}) is None
    assert normalize_rows(ROWS)[1]['value'] == '2026-09'
    assert production_date_text(normalized,language='EN') == 'Outdoor unit: 20 Oct 2026 (以铭牌为准)\nIndoor unit: Sep 2026'

@pytest.mark.parametrize('precision,value', [('day','2026-02-30'),('day','2026-10'),('month','2026-13'),('month','2026-10-01'),('custom','生产于2026-10-20')])
def test_invalid_dates_cannot_hide_in_text(precision,value):
    with pytest.raises(ValueError,match='室内机'):
        normalize_rows([dict(name='室内机',precision=precision,value=value)])

@pytest.mark.parametrize('state',['登记中','登记完成'])
def test_actual_save_roundtrip_and_later_workflow_checks(business,state):
    client,headers,parents=business
    value=detail()
    value['rawSample'].update(productionDates=deepcopy(ROWS),produceDate='/')
    result=create(client,headers,parents[0],'COMPONENT-QA',value,state)
    assert result['code']==0,result
    saved=Report.query.filter_by(report_no='COMPONENT-QA').one()
    assert saved.detail['rawSample']['productionDates']==ROWS
    assert saved.detail['rawSample']['produceDate']==display_rows(ROWS)
    # Review/approval use the same structured dates, not the derived display string.
    assert report_date_error(saved,'review','2026-10-19')
    assert report_date_error(saved,'approval','2027-01-01') is None

def test_legacy_marker_and_empty_structured_list_remain_intact():
    for marker in ('/', '—', 'N/A','2026-09'):
        item={'rawSample':{'produceDate':marker,'productionDates':[]}}
        assert canonical_detail(item)==item
        assert production_date_text(item)==marker

@pytest.mark.parametrize('kind,variant,language', [('产品报告','Standard','CN'),('产品报告','Extended','CN'),('产品报告','Standard','EN'),('产品报告','Extended','EN')])
def test_real_report_fields_and_word_preserve_each_date(isolated_app,monkeypatch,kind,variant,language):
    from test_docparser_deep_integration import report
    from app import docparser_field_only as fields, document_module
    from app.blueprints import report_publication
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    original_run = document_module.subprocess.run
    def checked_run(*args, **kwargs):
        result = original_run(*args, **kwargs)
        assert result.returncode in (0, 2), result.stderr
        return result
    monkeypatch.setattr(document_module.subprocess, 'run', checked_run)
    with isolated_app.app_context():
        item=report(kind);item.id=0;item.report_no='LAB-TEST-001';item.department=''
        item.detail['rawSample'].update(productionDates=deepcopy(ROWS),reportLanguage=language,reportTemplateVariant=variant)
        monkeypatch.setattr(report_publication,'report_qr_url',lambda _:'https://example.invalid/report/component')
        context=fields.report_context(item)
        assert ('Sep 2026' if language=='EN' else '2026年9月') in context['ManufacturingDate']
        blob,_=document_module.render_report(fields.profile_for(item),context)
        with ZipFile(BytesIO(blob)) as archive:
            text=''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        for line in context['ManufacturingDate'].splitlines():
            assert line in text


@pytest.mark.parametrize('kind', ['product', 'product-extended'])
def test_real_entrust_keeps_both_component_dates(isolated_app, monkeypatch, kind):
    from test_entrust_output_release import objects
    from app import docparser_field_only as fields
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
        entrust, item = objects(kind)
        item.report_no = 'LAB-TEST-R'
        item.detail['rawSample'].update(productionDates=deepcopy(ROWS))
        blob, _ = fields.render_entrust(entrust, item, kind)
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        for line in production_date_text(item.detail).splitlines():
            assert line in text


@pytest.mark.parametrize('entry', ['change-save', 'change-resubmit', 'edit'])
def test_full_return_form_preserves_and_checks_components(form_case, entry):
    from app.extensions import db
    from testkit.forms import loaded_form
    from app.applications.report_lifecycle import apply_return_plan
    client, headers, user, item, full = form_case
    item.detail = canonical_detail({**item.detail, 'rawSample': {**item.detail['rawSample'], 'productionDates': deepcopy(ROWS)}})
    full['rawSample'].update(productionDates=deepcopy(ROWS), produceDate=display_rows(ROWS))
    if entry == 'edit':
        item.sample_reg_state = '登记中'
    else:
        apply_return_plan(item, user, 'testing.data_entry.return', '委托信息更正')
    db.session.commit()
    path = f'/api/reports/{item.report_no}/{entry}'
    method = client.put if entry == 'edit' else client.post
    bad = deepcopy(full)
    bad['rawSample']['productionDates'][1].update(precision='day', value='2026-12-01')
    rejected = method(path, headers=headers, json=loaded_form(client, path, {'fullDetail': bad})).get_json()
    assert rejected['code'] != 0 and '室内机' in rejected['message'], rejected
    result = method(path, headers=headers, json=loaded_form(client, path, {'fullDetail': full})).get_json()
    assert result['code'] == 0, result
    db.session.refresh(item)
    assert item.detail['rawSample']['productionDates'] == ROWS
    assert item.detail['checkInput']['result'] == '原始结果'
    assert item.detail['workflowDates']['sampleInboundAt'] == '2026-10-22'


def test_report_preserves_oversized_component_dates_with_notice(isolated_app, monkeypatch):
    from test_docparser_deep_integration import report
    from app import docparser_field_only as fields, document_module
    from app.blueprints import report_publication
    with isolated_app.app_context():
        item = report('产品报告')
        item.id = 0
        item.report_no = 'LAB-TEST-OVERFLOW'
        item.department = ''
        item.detail['rawSample'].update(productionDates=[
            dict(name=f'室内机{i}', precision='day', value='2026-10-20', note='')
            for i in range(20)
        ])
        monkeypatch.setattr(report_publication, 'report_qr_url', lambda _: 'https://example.invalid/report/component')
        context = fields.report_context(item)
        blob, audit = document_module.render_report(fields.profile_for(item), context)
        assert 'ManufacturingDate' in audit['capacityWarnings']
        from io import BytesIO
        from zipfile import ZipFile
        from lxml import etree
        with ZipFile(BytesIO(blob)) as archive:
            text = ''.join(etree.fromstring(archive.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
        for line in context['ManufacturingDate'].splitlines():
            assert line in text
