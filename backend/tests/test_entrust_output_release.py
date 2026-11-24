"""Dates, reviewer identity and read permissions at document output boundaries."""
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from io import BytesIO
from zipfile import ZipFile
import base64
from PIL import Image

import pytest

from app import docparser_field_only as fields
from app.contract_review_output import review_image, authoritative_review
from app.entrust_render import _business_values, _cn_date
from app.extensions import db
from app.models import Entrust, Report
from app.security import issue_token

pytest_plugins = ('testkit.fixtures',)
_image = BytesIO()
Image.new('RGB', (80, 20), 'black').save(_image, format='PNG')
SIGNATURE = 'data:image/png;base64,' + base64.b64encode(_image.getvalue()).decode()


def objects(kind='product'):
    e = SimpleNamespace(entrust_no='WT-TEST', contract_no='', client='虚拟客户',
        project_name='虚拟工程', project_type='工程' if kind.startswith('engineering') else '产品',
        amount='0', department='', owner='', created_at=datetime(2026, 10, 16),
        info={'entrustDate':'2026-10-16', 'expectedDate':'2026/11/02'})
    r = SimpleNamespace(report_no='TEST-R', sample_no='TEST-S', entrust_no=e.entrust_no,
        project='', project_name='虚拟样品', client=e.client, department='', owner='',
        deadline='2026-11-01', sample_pickup={}, sample_status='', detail={
        'rawSample':{'sampleName':'虚拟样品', 'produceDate':'2026-09-01',
                     'factoryNo':'BATCH-2026-09-01', 'sendDate':'2026.10.15', 'testDept':''},
        'contractReview':{'result':'通过','reviewer':'原评审人','reviewerAccount':'reviewer',
                          'signatureSource':'account-image-v1','signature':SIGNATURE}})
    return e, r


@pytest.mark.parametrize('kind', ['product','engineering','product-extended','engineering-extended'])
def test_output_dates_and_saved_reviewer_across_templates(isolated_app, monkeypatch, kind):
    with isolated_app.app_context():
        import subprocess
        original_run = subprocess.run
        def checked_run(*args, **kwargs):
            result = original_run(*args, **kwargs)
            assert result.returncode == 0, result.stderr
            return result
        monkeypatch.setattr(subprocess, 'run', checked_run)
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        e, r = objects(kind)
        r.report_no = 'LAB-TEST-R'
        before = deepcopy(r.detail)
        context = fields.entrust_context(e, r, kind, 'PROJECT-TEST')
        assert context['SampleNo'] == r.sample_no
        assert context['EntrustDate'] == '2026年10月16日'
        assert context['SubmissionDate'] == '2026年10月15日'
        assert context['ReportDate'] == '2026年11月2日'
        assert context['ManufacturingDate'] == '2026年9月1日'
        assert context['Serial'] == 'BATCH-2026-09-01'
        assert context['Signature'] == SIGNATURE
        # Exercise the actual original-package worker, including image embedding.
        blob, audit = fields.render_entrust(e, r, kind, 'PROJECT-TEST')
        with ZipFile(BytesIO(blob)) as package:
            from lxml import etree
            # EntrustDate is in the original page headers, not the body.
            parts = [name for name in package.namelist()
                     if name == 'word/document.xml' or (name.startswith('word/header') and name.endswith('.xml'))]
            rendered = ''.join(''.join(etree.fromstring(package.read(name)).xpath(
                '//*[local-name()="t"]/text()')) for name in parts)
            assert '2026年10月16日' in rendered
            assert r.sample_no in rendered
            assert 'PROJECT-TEST' not in rendered
            if kind.startswith('product'):
                assert '2026年10月15日' in rendered
                assert '2026年9月1日' in rendered
            assert '2026年11月2日' in rendered
            assert _image.getvalue() in [package.read(n) for n in package.namelist() if n.startswith('word/media/')]
        values = _business_values(e, r)
        assert values['plan_complete'] == '2026年11月1日'
        assert values['production'] == '2026年9月1日 / BATCH-2026-09-01'
        assert r.detail == before
        r.detail['contractReview']['result'] = '退回'
        assert fields.entrust_context(e,r,kind)['Signature'] == ''


@pytest.mark.parametrize('kind', ['engineering', 'engineering-extended'])
@pytest.mark.parametrize('project_no', ['', 'PROJECT-TEST'])
def test_engineering_project_number_label_shows_current_sample(isolated_app, monkeypatch, kind, project_no):
    from lxml import etree
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
        e, r = objects(kind)
        r.report_no = 'LAB-TEST-R'
        r.detail['rawSample']['sampleNo'] = 'STALE-SAMPLE'
        blob, audit = fields.render_entrust(e, r, kind, project_no)
        with ZipFile(BytesIO(blob)) as package:
            headers = [name for name in package.namelist()
                       if name.startswith('word/header') and name.endswith('.xml')]
            numbered_headers = []
            for name in headers:
                text = ''.join(etree.fromstring(package.read(name)).xpath('//*[local-name()="t"]/text()'))
                if '项目编号' in text:
                    numbered_headers.append(''.join(text.split()))
            assert numbered_headers
            for text in numbered_headers:
                assert '项目编号：TEST-S' in text
                assert 'PROJECT-TEST' not in text
                assert 'STALE-SAMPLE' not in text
        assert audit['identity']['sampleNo'] == r.sample_no


@pytest.mark.parametrize('project_no', ['', 'PROJECT-TEST'])
def test_legacy_engineering_header_shows_sample_number(tmp_path, project_no):
    from docx import Document
    from lxml import etree
    from app.entrust_render import _render_package
    # Legacy binary templates are not shipped in this checkout. Exercise the
    # package renderer with their header contract in a synthetic document.
    template = tmp_path / 'legacy-engineering.docx'
    document = Document()
    document.add_paragraph('项目编号：    委托日期：')
    document.save(template)
    e, r = objects('engineering')
    blob = _render_package(template, 'engineering', _business_values(e, r, project_no))
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read('word/document.xml'))
        paragraphs = [''.join(p.xpath('.//*[local-name()="t"]/text()'))
                      for p in root.xpath('/*[local-name()="document"]/*[local-name()="body"]/*[local-name()="p"]')]
    headers = [''.join(text.split()) for text in paragraphs if '项目编号' in text]
    assert headers
    assert all('项目编号：TEST-S' in text for text in headers)


@pytest.mark.parametrize('category', ['委托', '委托（有见证送检）', '型式检验', '型式试验', '抽样检测', '抽样型式检验'])
def test_selected_inspection_category_reaches_entrust_document(isolated_app, monkeypatch, category):
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
        e, r = objects()
        r.report_no = 'LAB-TEST-R'
        r.detail['rawSample']['testCategory'] = category
        assert fields.entrust_context(e, r, 'product')['Category'] == category
        assert fields.entrust_context(e, r, 'engineering')['Category'] == category
        blob, _ = fields.render_entrust(e, r, 'product')
        with ZipFile(BytesIO(blob)) as package:
            from lxml import etree
            rendered = ''.join(etree.fromstring(package.read('word/document.xml')).xpath(
                '//*[local-name()="t"]/text()'))
            assert category in rendered
        assert r.detail['rawSample']['testCategory'] == category


@pytest.mark.parametrize('kind', ['product', 'product-extended', 'engineering', 'engineering-extended'])
@pytest.mark.parametrize('language', ['CN', 'EN', 'BI'])
def test_entrust_language_renders_selected_fields_without_changing_source(isolated_app, kind, language):
    with isolated_app.app_context():
        e, r = objects(kind)
        r.report_no = 'LAB-TEST-R'
        r.detail['rawSample']['testCategory'] = '委托（有见证送检）'
        before = deepcopy(r.detail)
        blob, _ = fields.render_entrust(e, r, kind, language=language)
        from docx import Document
        tables = Document(BytesIO(blob)).tables
        cells = [cell.text for table in tables for row in table.rows for cell in row.cells]
        category_en = 'Commission (with Witnessed Sampling)'
        category_cn = '委托（有见证送检）'
        category = {'CN': category_cn, 'EN': category_en, 'BI': category_cn + '\n' + category_en}[language]
        assert category in cells
        if kind.startswith('product'):
            production = {'CN': '2026年9月1日', 'EN': '1 Sep 2026', 'BI': '2026年9月1日 / 1 Sep 2026'}[language]
            submission = {'CN': '2026年10月15日', 'EN': '15 Oct 2026', 'BI': '2026年10月15日 / 15 Oct 2026'}[language]
            assert submission in cells
            assert production + '\nBATCH-2026-09-01' in cells
        assert r.detail == before


@pytest.mark.parametrize('kind', ['product', 'product-extended'])
def test_product_entrust_commission_fits_with_smaller_category_font(isolated_app, kind):
    from docx import Document
    from docx.oxml.ns import qn

    with isolated_app.app_context():
        e, r = objects(kind)
        r.report_no = 'LAB-TEST-R'
        r.detail['rawSample']['testCategory'] = '委托'
        for language, category, points in (
            ('CN', '委托', 12), ('EN', 'Commission', 10), ('BI', '委托\nCommission', 10),
        ):
            blob, _ = fields.render_entrust(e, r, kind, language=language)
            document = Document(BytesIO(blob))
            cells = [row.cells[index + 1] for table in document.tables for row in table.rows
                     for index, cell in enumerate(row.cells[:-1])
                     if ''.join(cell.text.split()) == '检验类别']
            assert len(cells) == 4
            assert {cell.text for cell in cells} == {category}
            assert {p.style.element.rPr.find(qn('w:sz')).get(qn('w:val'))
                    for cell in cells for p in cell.paragraphs} == {str(points * 2)}


def test_entrust_language_preserves_missing_dates_and_localizes_component_dates():
    from app.entrust_output_fields import localized_entrust_fields
    detail = {'rawSample': {'productionDates': [
        {'name': '室内机', 'precision': 'month', 'value': '2026-11', 'note': '批次 QA-2026-10-31'},
        {'name': '室外机', 'precision': 'day', 'value': '2026-11-02'},
        {'precision': 'custom', 'value': 'N/A'},
    ]}}
    result = localized_entrust_fields(detail, '抽样', '', 'BI')
    assert result == {
        'Category': '抽样 / Sampling',
        'ManufacturingDate': '室内机：2026年11月（批次 QA-2026-10-31） / Indoor unit: Nov 2026 (批次 QA-2026-10-31)\n室外机：2026年11月2日 / Outdoor unit: 2 Nov 2026\nN/A',
        'SubmissionDate': '',
    }


def test_legacy_product_can_render_bilingual_fields_in_place(tmp_path):
    from docx import Document
    from app.entrust_render import _render_package
    template = tmp_path / 'legacy.docx'
    document = Document()
    table = document.add_table(rows=3, cols=2)
    for row, label in zip(table.rows, ('生产日期/编号', '送样日期', '检验类别')):
        row.cells[0].text = label
    document.save(template)
    e, r = objects()
    r.detail['rawSample']['testCategory'] = '委托型式检验'
    rendered = _render_package(template, 'product', _business_values(e, r, language='BI'))
    assert [row.cells[1].text for row in Document(BytesIO(rendered)).tables[0].rows] == [
        '2026年9月1日 / 1 Sep 2026 / BATCH-2026-09-01',
        '2026年10月15日 / 15 Oct 2026',
        '委托型式检验 / Commissioned Type Inspection',
    ]


def test_dates_preserve_intervals_and_invalid_values():
    assert _cn_date('2026-10-01至2026-10-16') == '2026年10月1日至2026年10月16日'
    assert _cn_date('2026-02-30') == '2026-02-30'
    assert _cn_date('') == ''


def test_legacy_review_embeds_saved_image_without_changing_table_geometry():
    from docx import Document
    from app.contract_review_output import attach_legacy_signature
    document=Document()
    table=document.add_table(rows=1,cols=3)
    table.cell(0,0).text='合同\n评审'
    table.cell(0,1).text='技术能力 ☑'
    table.cell(0,2).text='签字：原评审人'
    stream=BytesIO();document.save(stream)
    _, report=objects()
    blob=attach_legacy_signature(stream.getvalue(),report)
    restored=Document(BytesIO(blob))
    assert len(restored.inline_shapes)==1
    assert len(restored.tables)==1 and len(restored.tables[0].columns)==3
    assert restored.tables[0].cell(0,1).text=='技术能力 ☑'
    assert restored.tables[0].cell(0,2).text=='签字：原评审人'
    report.detail['contractReview']['result']='退回'
    assert attach_legacy_signature(stream.getvalue(),report)==stream.getvalue()


@pytest.mark.parametrize('permission', ['entrust.query.view','entrust.contract_review.view'])
def test_query_and_review_can_view_download_only_their_sample(isolated_app, scenario_factory, monkeypatch, permission):
    from app import entrust_render, docx_pdf
    from app.blueprints import samples
    with isolated_app.app_context():
        dept=scenario_factory.department()
        user=scenario_factory.user(dept, permissions=[permission])
        e,r=objects()
        parent=Entrust(entrust_no=e.entrust_no, contract_no='', client=e.client,
            department=dept.name, owner=user.name, info=e.info)
        report=Report(report_no=r.report_no,sample_no=r.sample_no,entrust_no=e.entrust_no,
            project='虚拟项目',client=e.client,department=dept.name,owner=user.name,detail=r.detail)
        other=Report(report_no='OTHER',sample_no='OTHER-S',entrust_no=e.entrust_no,
            project='虚拟项目',client=e.client,department='其他部门',owner='其他用户',detail=r.detail)
        db.session.add_all([parent,report,other]);db.session.commit()
        headers={'Authorization':'Bearer '+issue_token(user)}
        client=isolated_app.test_client()
        monkeypatch.setattr(fields,'applies_to_entrust',lambda _:False)
        rendered=[]
        def build(e,r,*args):
            rendered.append((r.report_no,review_image(r)))
            stream = BytesIO()
            with ZipFile(stream, 'w') as archive:
                archive.writestr('word/document.xml', 'isolated-docx')
            return stream.getvalue()
        monkeypatch.setattr(entrust_render,'build_entrust_doc',build)
        monkeypatch.setattr(docx_pdf,'docx_to_pdf_wps',lambda _:b'%PDF-isolated')
        monkeypatch.setattr(samples,'_business_form_page_count',lambda *_:3)
        from app import document_module
        monkeypatch.setattr(document_module,'entrust_background',lambda x:x)
        for fmt in ('docx','pdf'):
            response=client.get('/api/samples/TEST-R/print?format='+fmt,headers=headers)
            assert response.status_code==200
            assert response.mimetype in ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),response.json
            assert rendered[-1]==('TEST-R',SIGNATURE)
        denied=client.get('/api/samples/OTHER/print?format=docx',headers=headers)
        assert denied.json['code']!=0
        # Parent printing must scope reports too, never use the other department.
        response=client.get(f'/api/entrust/{parent.id}/print?format=docx',headers=headers)
        assert response.mimetype=='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        assert rendered[-1]==('TEST-R',SIGNATURE)
        second=Report(report_no='SECOND',sample_no='SECOND-S',entrust_no=e.entrust_no,
            project='虚拟项目',client=e.client,department=dept.name,owner=user.name,detail={})
        db.session.add(second);db.session.commit()
        response=client.get(f'/api/entrust/{parent.id}/print?format=docx',headers=headers)
        assert '多个样品' in response.json['message']
        response=client.get(f'/api/entrust/{parent.id}/print?format=docx&reportNo=TEST-R',headers=headers)
        assert response.mimetype=='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        assert rendered[-1]==('TEST-R',SIGNATURE)
        # Client-supplied names/images cannot impersonate the reviewer.
        copied=authoritative_review({'reportNo':'TEST-R','detail':{'contractReview':{'signature':'forged'}}},user)
        assert copied['contractReview']['signature']==SIGNATURE

@pytest.mark.parametrize('kind', ['product','product-extended','engineering','engineering-extended'])
def test_mixed_parameter_and_basis_order_reaches_original_templates(isolated_app, monkeypatch, kind):
    from app.document_field_projection import test_items
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        e,r=objects(kind)
        r.report_no='LAB-TEST-R'
        r.detail['rawSample'].update(project='旧摘要',testBases=['QA-BASIS-B','QA-BASIS-A'],
            capabilityEntryIds=[22,11],manualCapabilityItems=['库外温差'],
            capabilitySnapshots=[{'id':11,'itemName':'温度'},{'id':22,'itemName':'湿度'}],
            testItemOrder=[{'kind':'library','id':22},{'kind':'manual','name':'库外温差'},{'kind':'library','id':11}])
        assert test_items(r.detail,'旧摘要') == '湿度、库外温差、温度'
        assert _business_values(e,r)['test_project'] == '湿度、库外温差、温度'
        blob,_=fields.render_entrust(e,r,kind)
        with ZipFile(BytesIO(blob)) as package:
            from lxml import etree
            text=''.join(etree.fromstring(package.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
            assert '湿度、库外温差、温度' in text
            assert text.index('QA-BASIS-B') < text.index('QA-BASIS-A')

def test_order_references_cannot_add_unselected_parameters_and_preserve_old_records():
    from app.document_field_projection import test_items
    raw={'capabilityEntryIds':[1,2],'capabilitySnapshots':[{'id':1,'itemName':'甲'},{'id':2,'itemName':'乙'}],
         'manualCapabilityItems':['丙'], 'testItemOrder':[{'kind':'library','id':2},{'kind':'manual','name':'未选择'},{'kind':'library','id':2}]}
    assert test_items({'rawSample':raw},'旧摘要') == '乙、甲、丙'
    assert test_items({'rawSample':{'manualCapabilityItems':['丙']}},'甲、乙') == '甲、乙、丙'


_REVIEW_LABELS = ['技术能力', '仪器设备', '环境设施条件', '方法', '人员', '样品',
                  '检验依据授权', '加盖CMA章', '加盖CNAS章']


@pytest.mark.parametrize('kind', ['product', 'engineering', 'product-extended', 'engineering-extended'])
@pytest.mark.parametrize('result', [None, '草稿', '退回', '通过'])
def test_review_boxes_distinguish_pending_from_unselected(isolated_app, monkeypatch, kind, result):
    from lxml import etree
    from app.contract_review_output import review_flags
    from app.entrust_render import _following_cells, _element_text
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
        e, r = objects(kind)
        r.report_no = 'LAB-TEST-R'
        r.detail.pop('contractReview')
        if result is not None:
            r.detail['contractReview'] = {
                'result': result, 'items': {'tech': True, 'instrument': False, 'env': True,
                'method': False, 'personnel': True, 'sample': False, 'basisAuth': True},
                'cma': False, 'cnas': True,
                'signatureSource': 'account-image-v1', 'signature': '',
            }
        before = deepcopy(r.detail)
        flags = review_flags(r)
        if result not in ('通过', '退回'):
            assert all(value is None for value in flags.values())
        else:
            assert flags['TECHNIQUE'] is True and flags['CMA'] is False
        blob, audit = fields.render_entrust(e, r, kind)
        with ZipFile(BytesIO(blob)) as package:
            root = etree.fromstring(package.read('word/document.xml'))
            cells = _following_cells(root, '合同评审')
            assert cells
            text = ''.join(''.join(_element_text(cell).split()) for cell in cells)
            expected = ['☑', '☒', '☑', '☒', '☑', '☒', '☑', '☒', '☑'] if result in ('通过', '退回') else ['□'] * 9
            for mark, label in zip(expected, _REVIEW_LABELS):
                # Supplier engineering templates contain eight review fields;
                # only product templates include the sample-condition checkbox.
                if kind.startswith('engineering') and label == '样品':
                    assert label not in text
                    continue
                assert text.count(mark + label) == text.count('技术能力') > 0, (kind, result, label, text)
            if result not in ('通过', '退回'):
                assert '☒' not in text and '☑' not in text
        assert r.detail == before


@pytest.mark.parametrize('completed', [False, True])
def test_legacy_review_boxes_preserve_runs_layout_and_other_checkboxes(tmp_path, completed):
    from docx import Document
    from lxml import etree
    from app.entrust_render import _render_package, _following_cells, _element_text
    document = Document()
    document.add_paragraph('其他选项：☑自取 ☒邮寄')
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = '合同评审'
    p = table.cell(0, 1).paragraphs[0]
    for label in _REVIEW_LABELS:
        p.add_run('☒')
        p.add_run(label.replace('CMA', ' CMA ').replace('CNAS', ' CNAS ') + ' ')
    template = tmp_path / 'review.docx'; document.save(template)
    e, r = objects()
    r.detail['contractReview'] = {'result': '通过' if completed else '', 'items': {'tech': True}, 'cma': True}
    blob = _render_package(template, 'product', _business_values(e, r))
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read('word/document.xml'))
        text = ''.join(''.join(_element_text(cell).split()) for cell in _following_cells(root, '合同评审'))
        for label in _REVIEW_LABELS:
            mark = ('☑' if label in ('技术能力', '加盖CMA章') else '☒') if completed else '□'
            assert mark + label in text
        assert '其他选项：☑自取 ☒邮寄' in _element_text(root)
        assert len(root.xpath('//*[local-name()="tbl"]')) == 1
        assert len(root.xpath('//*[local-name()="tc"]')) == 2


@pytest.mark.parametrize('kind', ['product','product-extended','engineering','engineering-extended'])
def test_commission_text_preserves_preview_separators_in_all_templates(isolated_app, monkeypatch, kind):
    from docx import Document
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        e,r=objects(kind);r.report_no='LAB-TEST-R'
        expected={'basis':'QA-B 乙标准； \nQA-A 甲标准','items':'湿度， 库外温差、\n温度'}
        r.detail['rawSample']['commissionText']=expected
        values=_business_values(e,r)
        assert values['basis']==expected['basis']
        assert values['test_project']==expected['items']
        blob,_=fields.render_entrust(e,r,kind)
        document=Document(BytesIO(blob))
        cells=[cell.text for table in document.tables for row in table.rows for cell in row.cells]
        assert any(expected['basis'] in text for text in cells), cells
        assert any(expected['items'] in text for text in cells), cells
