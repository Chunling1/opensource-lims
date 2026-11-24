"""One physical sample, several independently numbered reports."""
from copy import deepcopy
from types import SimpleNamespace
from io import BytesIO
from zipfile import ZipFile
import pytest
from app.sample_identity import sample_number
from app.models import Report
from app.extensions import db
from app.entrust_render import _business_values
from app import docparser_field_only as fields
from test_sample_pricing import business, detail
from test_entrust_output_release import objects

pytest_plugins = ('testkit.fixtures',)
ROOT = 'LAB-2026HR-0053'
SAMPLE = '2026HR-0053'

@pytest.mark.parametrize('suffix', ['-1', '-part-A', 'BC', 'GZ', '(E)', 'EN'])
def test_legacy_projection_uses_explicit_lineage_without_mutation(suffix):
    r = Report(report_no=ROOT+suffix, sample_no=SAMPLE+suffix,
               main_report_no=ROOT, detail={'rawSample': {'sampleNo': SAMPLE+suffix}})
    before = deepcopy(r.detail)
    assert sample_number(r) == SAMPLE
    assert r.to_row()['sampleNo'] == SAMPLE
    assert r.to_row()['reportNo'] == ROOT+suffix
    assert r.sample_no == SAMPLE+suffix and r.detail == before

@pytest.mark.parametrize('value', ['2026ZX-JH-0329', 'CUSTOM-1', 'CUSTOM-BC', 'CUSTOM-EN', '  invalid '])
def test_never_strip_unrelated_real_sample_codes(value):
    r = SimpleNamespace(report_no=ROOT+'-1', sample_no=value, main_report_no=ROOT, detail={})
    assert sample_number(r) == value
    r.sample_no = SAMPLE+'-1'; r.main_report_no = ''
    assert sample_number(r) == SAMPLE+'-1'  # no evidence of lineage

@pytest.mark.parametrize('category,suffix', [('分项','-1'), ('补充','BC'), ('英文','(E)')])
def test_registration_persists_source_sample_even_when_client_sends_report_suffix(business, category, suffix):
    client, headers, parents = business
    main = Report(report_no=ROOT, sample_no=SAMPLE, entrust_no=parents[0].entrust_no,
        department='虚拟部门', detail=detail(), status='待校核', sample_reg_state='登记完成')
    db.session.add(main); db.session.commit()
    payload = client.post('/api/reports/create', headers=headers, json={
        'reportCategory':category, 'baseReportNo':ROOT, 'reportNo':ROOT+suffix,
        'sampleNo':SAMPLE+suffix, 'entrustNo':parents[0].entrust_no,
        'regState':'登记中', 'detail':detail(), 'department':'虚拟部门', 'project':'虚拟检测'}).get_json()
    assert payload['code'] == 0, payload
    r = Report.query.filter_by(report_no=ROOT+suffix).one()
    assert r.sample_no == SAMPLE
    assert r.detail['rawSample']['sampleNo'] == SAMPLE
    assert payload['data']['sampleNo'] == SAMPLE
    assert r.report_no == ROOT+suffix

@pytest.mark.parametrize('kind,suffix', [('itemized','1'),('supplement','BC'),('english','(E)'),('correction','GZ')])
def test_clone_path_inherits_sample(business, kind, suffix):
    from app.blueprints.reports import _clone_derived_report
    _, _, parents = business
    main = Report(report_no=ROOT, sample_no=SAMPLE, entrust_no=parents[0].entrust_no,
        department='虚拟部门', detail=detail(), status='待打印', sample_status='已领取')
    target = _clone_derived_report(main, ROOT+('-' if kind=='itemized' else '')+suffix,
        kind, suffix, SimpleNamespace(name='虚拟主检',account='qa'), return_mode='entrust_and_data')
    assert target.sample_no == SAMPLE

@pytest.mark.parametrize('kind', ['product','product-extended','engineering','engineering-extended'])
def test_actual_entrust_docx_contains_base_sample_not_report_suffix(isolated_app, monkeypatch, kind):
    from lxml import etree
    with isolated_app.app_context():
        monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName':'虚拟机构'})
        e, r = objects(kind)
        r.report_no=ROOT+'-1';r.sample_no=SAMPLE+'-1';r.main_report_no=ROOT
        assert _business_values(e,r)['sample_identifier'] == SAMPLE
        context = fields.entrust_context(e,r,kind)
        assert context['SampleNo'] == SAMPLE
        blob, audit = fields.render_entrust(e,r,kind)
        with ZipFile(BytesIO(blob)) as z:
            text=''.join(''.join(etree.fromstring(z.read(n)).xpath('//*[local-name()="t"]/text()'))
                for n in z.namelist() if n=='word/document.xml' or (n.startswith('word/header') and n.endswith('.xml')))
        assert SAMPLE in text and SAMPLE+'-1' not in text
        assert audit['identity']['sampleNo'] == SAMPLE


@pytest.mark.parametrize('stored_sample', [SAMPLE, SAMPLE+'-1'])
def test_title_change_keeps_report_suffix_and_sample(business, stored_sample):
    from app.blueprints.reports import _apply_report_prefix_change
    _,_,parents=business
    r=Report(report_no=ROOT+'-1',sample_no=stored_sample,main_report_no=ROOT,
             detail={'rawSample':{'centerPrefix':'LAB','schemeCode':'HR'}})
    db.session.add(r);db.session.commit()
    edited={'rawSample':{'centerPrefix':'NCSA','schemeCode':'HR'}}
    assert _apply_report_prefix_change(r,edited) is None
    assert r.report_no == 'NCSA-2026HR-0053-1'
    assert r.sample_no == stored_sample
    assert sample_number(r) == SAMPLE
    assert edited['rawSample']['sampleNo'] == SAMPLE


def test_document_identity_keeps_report_and_entrust_with_clean_sample():
    r=SimpleNamespace(report_no=ROOT+'(E)', sample_no=SAMPLE+'(E)', main_report_no=ROOT,
                      entrust_no='WT-2026-TEST',detail={})
    assert fields.number_identity(r) == {'reportNo':ROOT+'(E)', 'sampleNo':SAMPLE, 'entrustNo':'WT-2026-TEST'}
    r.sample_no='  invalid '
    with pytest.raises(ValueError,match='sampleNo'):
        fields.number_identity(r)


@pytest.mark.parametrize('projection', ['sample_form', 'sample_form_text'])
@pytest.mark.parametrize('suffix', ['-1', 'BC', 'GZ', '(E)'])
def test_registration_form_projection_preserves_canonical_sample_identity(business, projection, suffix):
    client, headers, parents = business
    snapshot = {'rawSample': {'sampleNo': SAMPLE+suffix, 'sampleName': 'QA sample'}}
    r = Report(report_no=ROOT+suffix, sample_no=SAMPLE+suffix, main_report_no=ROOT,
               entrust_no=parents[0].entrust_no, department='虚拟部门',
               detail=deepcopy(snapshot), status='待合同评审', sample_reg_state='登记中')
    db.session.add(r); db.session.commit()
    response = client.get('/api/reports/'+r.report_no, headers=headers,
                          query_string={'view': 'sample_register', 'projection': projection})
    payload = response.get_json()
    assert payload['code'] == 0, payload
    assert payload['data']['sampleNo'] == SAMPLE
    assert payload['data']['reportNo'] == ROOT+suffix
    db.session.expire_all()
    assert r.sample_no == SAMPLE+suffix and r.detail == snapshot
