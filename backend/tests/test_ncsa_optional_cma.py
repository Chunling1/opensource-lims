"""Exercise actual vendor rendering; only explicit NCSA CMA omission changes media."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile
import pytest
from app.document_module import render_report

def media(blob):
    with ZipFile(BytesIO(blob)) as z:
        return {sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}

@pytest.mark.parametrize('kind,language,variant',[
    (kind,language,variant) for kind in ('product','sampling','engineering')
    for language in ('CN','EN') for variant in ('Standard','Extended')
    if kind!='engineering' or variant=='Standard'])
def test_ncsa_cma_is_optional_across_templates(kind,language,variant):
    profile=dict(kind=kind,language=language,variant=variant,center='NCSA',requirements={'seal':'CMA + CNAS'})
    context={'ReportNo':'LAB-2026QA-0001','SampleNo':'2026QA-0001','SampleName':'Sample'}
    with_cma,_=render_report(profile,context)
    profile['requirements']['seal']='CNAS'
    without_cma,_=render_report(profile,context)
    assert len(media(with_cma)-media(without_cma))==1
    assert not media(without_cma)-media(with_cma)
    with ZipFile(BytesIO(without_cma)) as z:
        xml=z.read('word/document.xml').decode()
        assert 'CNAS' in xml and 'LAB-2026QA-0001' in xml
        assert '国家空调设备质量检验检测中心' in xml

@pytest.mark.parametrize('center,seal',[('NCSA',None),('LAB','CNAS')])
def test_historical_missing_choice_and_other_centers_keep_vendor_mark(center,seal):
    profile=dict(kind='product',language='CN',variant='Standard',center=center,requirements={})
    context={'ReportNo':center+'-2026QA-0001','SampleName':'Sample'}
    expected,_=render_report(profile,context)
    profile['requirements']['seal']=seal
    actual,_=render_report(profile,context)
    assert media(actual)==media(expected)


def test_sample_choice_reaches_render_profile_and_legacy_summary():
    from types import SimpleNamespace
    from app.docparser_field_only import profile_for
    r=SimpleNamespace(report_no='LAB-2026QA-0001',department='QA',detail={'rawSample':{'reportType':'产品报告','seal':'CNAS'}})
    assert profile_for(r)['requirements']['seal']=='CNAS'
    r.detail['rawSample'].pop('seal')
    r.detail['summary']=[{'title':'委托信息','fields':[['盖章要求','CMA + CNAS']]}]
    assert profile_for(r)['requirements']['seal']=='CMA + CNAS'
