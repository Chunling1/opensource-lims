"""Deep DocParser selection and general-rule regression (adapted to 20260911 open-source templates)."""
from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from datetime import datetime, timezone
from zipfile import ZipFile

from flask import Flask
from lxml import etree
import pytest

from app import docparser_field_only as adapter


@pytest.fixture
def application(monkeypatch):
    monkeypatch.setattr('app.blueprints.report_publication.report_qr_url', lambda *_: 'https://lab.example.com/r/qa')
    app = Flask(__name__)
    app.config.update(DOCUMENT_TEMPLATE_ENGINE=adapter.ENGINE, DUAL_SCOPE_WORKFLOW_ENABLED=False)
    with app.app_context():
        yield app


def report(kind='产品报告', pages='1p'):
    return SimpleNamespace(
        id=None,
        report_no='NCSA-2026LQ-0002-R1', sample_no='2026LQ-0002-02',
        entrust_no='WT-2026-0099', project='试验项目', project_name='字段联调样品',
        client='测试委托单位', owner='不应绘制的主检姓名', department='空调设备检测部',
        out_of_scope=False, detail={
            'rawSample': {
                'reportType': kind, 'reportTemplatePages': pages,
                'sampleName': '字段联调样品', 'spec': 'MODEL-01', 'manufacturer': '测试制造单位',
                'testCategory': '委托', 'testLocation': '示例站点B', 'testBasis': 'GB 10080-2001',
            },
            'entrustSnapshot': {
                'entrustNo': 'WT-2026-0099', 'sourceEntrustNo': 'WT-2026-0099',
                'client': '样品独立委托单位', 'info': {'entrustNo': 'WT-2026-0099'},
            },
            'summary': [{'title': '实验信息', 'fields': [['检测项目', '参数A'], ['检测依据', 'GB 10080-2001']]}],
        },
    )


def package_text(blob):
    with ZipFile(BytesIO(blob)) as z:
        return {name: ''.join(etree.fromstring(z.read(name)).xpath('//*[local-name()="t"]/text()'))
                for name in z.namelist() if name.startswith('word/') and name.endswith('.xml')}


@pytest.mark.parametrize('kind,pages', [
    ('产品报告', '1p'), ('产品报告', '2p'), ('抽样报告', '1p'),
    ('抽样报告', '2p'), ('工程报告', '1p'), ('检验报告', '1p'), ('校准报告', '1p'),
])
def test_original_fields_only_all_variants(application, kind, pages):
    r = report(kind, pages)
    if kind in ('检验报告', '校准报告'):
        r.report_no = 'LAB-2026JC-0001'
    detail = deepcopy(r.detail)
    blob, audit = adapter.render_preview(r)
    texts = package_text(blob)
    actual = ''.join(texts.values())
    assert r.report_no in actual
    assert adapter.GUIDE_MARKER in actual
    assert '样品独立委托单位' in actual
    assert '不应绘制的主检姓名' not in actual
    assert '{{' not in actual and '{%' not in actual
    assert r.detail == detail
    assert audit['identity']['sampleNo'] == '2026LQ-0002-02'
    assert audit['identity']['entrustNo'] == 'WT-2026-0099'
    assert audit['completeReport'] is False
    with pytest.raises(ValueError, match='不得作为正式报告'):
        adapter.require_complete_report(audit)


def test_numbers_are_not_derived_or_mutated(application):
    r = report()
    assert adapter.report_context(r)['ReportNo'] == r.report_no
    assert adapter.report_context(r)['SampleNo'] == r.sample_no
    assert r.sample_no != r.report_no.split('-', 1)[1]
    with pytest.raises(ValueError, match='关联数据不一致'):
        adapter.number_identity(r, SimpleNamespace(entrust_no='WT-2026-OTHER'))
    r.detail['rawSample']['sampleNo'] = '2026LQ-9999'
    with pytest.raises(ValueError, match='串号'):
        adapter.report_context(r)


@pytest.mark.parametrize('field', ['report_no', 'sample_no', 'entrust_no'])
def test_missing_persisted_identity_cannot_fallback_to_form(application, field):
    r = report()
    setattr(r, field, '')
    with pytest.raises(ValueError, match='先保存'):
        adapter.report_context(r)


def test_overlong_number_is_rejected_not_truncated(application):
    r = report()
    r.report_no = 'NCSA-' + '0' * 45
    with pytest.raises(ValueError, match='ReportNo.*截断'):
        adapter.render_preview(r)


def test_overlong_fields_do_not_trigger_layout_or_template_switch(application):
    r = report()
    r.detail['rawSample']['sampleName'] = '长样品名称' * 60
    with pytest.raises(ValueError, match='截断'):
        adapter.render_preview(r)


@pytest.mark.parametrize('field', ['Trademark', 'Conclusion'])
def test_business_text_never_opens_a_local_file(application, field, monkeypatch):
    r = report()
    context = adapter.report_context(r)
    context[field] = 'C:/private/file.docx' if field == 'Conclusion' else '/private/logo.png'
    monkeypatch.setattr(adapter, 'report_context', lambda _: context)
    with pytest.raises(ValueError, match='不接受本地文件路径'):
        adapter.render_preview(r)


def test_source_snapshot_binds_numbers_and_filled_fields(application):
    r = report()
    first = adapter.template_snapshot(r)
    assert first['identity'] == adapter.number_identity(r)
    assert first['fieldValues']['ReportNo'] == r.report_no
    r.detail['entrustSnapshot']['client'] = '变更后的委托单位'
    second = adapter.template_snapshot(r)
    assert first['fieldValues'] != second['fieldValues']
    assert first['files'] == second['files']


def test_unknown_prefix_is_not_silently_assigned_another_center(application):
    r = report()
    r.report_no = 'UNKNOWN-2026LQ-0001'
    with pytest.raises(ValueError, match='中心前缀未配置'):
        adapter.report_context(r)


def test_company_fields_escape_xml_without_changing_template(application):
    r = report()
    r.detail['entrustSnapshot']['client'] = 'A&B <Company>'
    blob, _ = adapter.render_preview(r)
    assert 'A&B <Company>' in ''.join(package_text(blob).values())


def test_department_rule_and_report_requirements_are_audited(application):
    r = report()
    r.detail['rawSample'].update({'seal': 'CMA章', 'reportFormat': '双页', 'reportTemplatePages': '',
                                  'reportIssuingDepartment': '空调设备检测部'})
    selected = adapter.profile_for(r)
    assert selected['filename'] == 'LAB-Report-Product-CN-Extended-202609_tpl.docx'
    assert selected['requirements']['seal'] == 'CMA章'
    assert selected['selectionEvidence']['departmentMatches'][0]['center'] == 'NCSA'


def test_entrust_mode_selects_original_4204_templates(application):
    r = report('工程报告')
    entrust = SimpleNamespace(
        entrust_no='WT-2026-0099', created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        project_type='工程检测', project_name='工程项目', department='空调设备检测部', info={},
    )
    selected = adapter.entrust_profile_for(entrust, r)
    assert selected['kind'] == 'engineering'
    assert selected['filename'].startswith('LAB-Entrust-4204g-')
    r.detail['rawSample']['entrustTemplateMode'] = '产品'
    with pytest.raises(ValueError, match='显式委托模式与打印请求'):
        adapter.entrust_profile_for(entrust, r, 'engineering')


@pytest.mark.parametrize('mode', ['cnas', 'cnas_cma'])
def test_scope_mark_text_preserves_original_format_with_reviewed_number(mode):
    evidence = [dict(kind='CNAS', certificate='L0000', institution='测试机构', category='检测')]
    if mode == 'cnas_cma':
        evidence.append(dict(kind='CMA', certificate='000000000000', institution='测试机构', category='检测'))
    cma, cnas = adapter.scope_mark_fields(mode, evidence, '测试机构')
    assert cma == ('000000000000' if mode == 'cnas_cma' else '')
    assert cnas == '中国认可\n国际互认\n检测\nTESTING\nCNAS L0000'
    with pytest.raises(ValueError, match='机构名称'):
        adapter.scope_mark_fields(mode, evidence, '其他机构')


def test_inspection_cannot_silently_reuse_original_laboratory_mark():
    evidence = [dict(kind='CNAS', certificate='IB0000', institution='测试机构', category='检验')]
    with pytest.raises(ValueError, match='不能自动套用'):
        adapter.scope_mark_fields('cnas', evidence, '测试机构')


def _pdf(*pages):
    import fitz
    document = fitz.open()
    for value in pages:
        page = document.new_page()
        page.insert_text((48, 72), value, fontname='china-s', fontsize=10)
    blob = document.tobytes()
    document.close()
    return blob


def test_completed_template_pdf_keeps_server_fixed_pages_and_uploaded_body(application):
    number = 'NCSA-2026LQ-0002-R1'
    base = _pdf(
        f'服务器封面 {number}',
        f'{number}\nChief Tester\nVerification\nApproval',
        f'{number} 内容编写说明 请删除本说明',
        f'{number} 注意事项 NOTICE 固定声明',
    )
    completed = _pdf(
        f'被忽略的上传封面 {number}',
        f'被忽略的上传首页 {number} 主检 审核 批准',
        f'{number} 正文检测结果 第一页',
        f'{number} 正文检测结果 第二页',
        f'{number} 注意事项 NOTICE 被忽略的上传声明',
    )
    final, audit = adapter.compose_completed_pdf(base, [completed], number)
    document, texts = adapter._pdf_texts(final)
    try:
        text_value = ''.join(texts)
    finally:
        document.close()
    assert '服务器封面' in text_value
    assert '正文检测结果第一页' in text_value
    assert '正文检测结果第二页' in text_value
    assert '被忽略的上传封面' not in text_value
    assert '被忽略的上传声明' not in text_value
    assert adapter.GUIDE_MARKER not in text_value
    assert audit == {**audit, 'frontPages': 2, 'bodyPages': 2, 'noticePages': 1}


def test_completed_template_pdf_accepts_single_cover_variant(application):
    number = 'NCSA-2026JF-9901'
    base = _pdf(
        f'服务器封面 {number}',
        f'{number} 内容编写说明 请删除本说明 Chief Tester Verification Approval',
        f'{number} 注意事项 NOTICE 固定声明',
    )
    completed = _pdf(
        f'被忽略的上传封面 {number}',
        f'{number} 正文检测结果 Chief Tester Verification Approval',
        f'{number} 注意事项 NOTICE 被忽略的上传声明',
    )
    final, audit = adapter.compose_completed_pdf(base, [completed], number)
    document, texts = adapter._pdf_texts(final)
    try:
        text_value = ''.join(texts)
    finally:
        document.close()
    assert '服务器封面' in text_value
    assert '正文检测结果' in text_value
    assert '被忽略的上传封面' not in text_value
    assert audit == {**audit, 'frontPages': 1, 'bodyPages': 1, 'noticePages': 1}


def test_completed_template_pdf_rejects_missing_number_or_guide(application):
    number = 'NCSA-2026LQ-0002-R1'
    base = _pdf('封面', f'{number}\nChief Tester\nVerification\nApproval',
                f'{number} 内容编写说明', f'{number} 注意事项 NOTICE')
    missing_number = _pdf('封面', '首页', '另一份报告的正文', '注意事项 NOTICE')
    with pytest.raises(ValueError, match='缺少当前报告编号'):
        adapter.compose_completed_pdf(base, [missing_number], number)
    guide_retained = _pdf('封面', '首页', f'{number} 内容编写说明', '注意事项 NOTICE')
    with pytest.raises(ValueError, match='编写说明|没有正文'):
        adapter.compose_completed_pdf(base, [guide_retained], number)


def test_upload_validation_rejects_unfilled_issued_template(application):
    r = report()
    blob, _ = adapter.render_preview(r)
    with pytest.raises(ValueError, match='删除.*编写说明'):
        adapter.validate_completed_template_source(blob, 'filled.docx', r.report_no)
    with pytest.raises(ValueError, match='旧版'):
        adapter.validate_completed_template_source(b'legacy', 'filled.doc', r.report_no)


def linked_test_document():
    from docx import Document
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    doc = Document()
    doc.add_paragraph(report().report_no)
    doc.add_paragraph('注意事项 NOTICE')
    doc.part.relate_to('https://example.com', RT.HYPERLINK, is_external=True)
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def test_upload_validation_accepts_user_added_external_hyperlink(application):
    blob = linked_test_document()
    output = BytesIO()
    with ZipFile(BytesIO(blob)) as source, ZipFile(output, 'w') as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.endswith('.rels'):
                data = data.replace(b'https://example.com', b'https://example.invalid')
            target.writestr(item, data)
    adapter.validate_completed_template_source(output.getvalue(), 'filled.docx', report().report_no)
    from app.document_module import validate_docx
    validate_docx(output.getvalue())


def test_server_owned_rollout_cutoff_preserves_historical_reports(application):
    application.config['DOCPARSER_ROLLOUT_STARTED_AT'] = '2026-09-01T00:00:00Z'
    old = report()
    old.created_at = datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc)
    new = report()
    new.created_at = datetime(2026, 9, 1, 0, 1, tzinfo=timezone.utc)
    assert adapter.applies_to(old) is False
    assert adapter.applies_to(new) is True


@pytest.mark.parametrize('kind', ['image', 'attachedTemplate', 'oleObject', 'aFChunk'])
def test_upload_still_requires_embedded_rendering_resources(application, kind):
    r = report()
    blob = linked_test_document()
    output = BytesIO()
    with ZipFile(BytesIO(blob)) as source, ZipFile(output, 'w') as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == 'word/_rels/document.xml.rels':
                root = etree.fromstring(data)
                etree.SubElement(
                    root, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
                    Id='rIdExternalQA', Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/' + kind,
                    Target='https://example.invalid/resource', TargetMode='External',
                )
                data = etree.tostring(root)
            target.writestr(item, data)
    with pytest.raises(ValueError, match='外部|嵌入'):
        adapter.validate_completed_template_source(output.getvalue(), 'filled.docx', r.report_no, allow_guide_pages=True)


def test_hyperlink_and_internal_reference_keep_renderable_text(application):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    r = report()
    doc = Document()
    doc.add_paragraph(r.report_no)
    doc.add_paragraph('注意事项 NOTICE')
    paragraph = doc.add_paragraph()
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), paragraph.part.relate_to('https://example.invalid/no-network', RT.HYPERLINK, is_external=True))
    run = OxmlElement('w:r'); text = OxmlElement('w:t'); text.text = 'Reference website'
    run.append(text); hyperlink.append(run); paragraph._p.append(hyperlink)
    field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'REF TestBookmark')
    run = OxmlElement('w:r'); text = OxmlElement('w:t'); text.text = 'Table 1'
    run.append(text); field.append(run); paragraph._p.append(field)
    stream = BytesIO(); doc.save(stream); blob = stream.getvalue()
    adapter.validate_completed_template_source(blob, 'filled.docx', r.report_no)
    from app.document_module import validate_docx
    validate_docx(blob)
    assert 'Reference website' in package_text(blob)['word/document.xml']
    assert 'Table 1' in package_text(blob)['word/document.xml']
