"""Address truncation is explicit, nonblocking, and never creates an appendix."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
import pytest
from app import document_module
pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('language', ['CN','EN'])
@pytest.mark.parametrize('authoring',[False,True])
def test_platform_passes_full_address_to_vendor(language,authoring):
    address=('Very long customer address building 123; ' if language=='EN' else '完整检测地点地址甲乙丙丁')*100
    context={'ReportNo':'LAB-2026-QA-0001','Place':address}
    before=deepcopy(context)
    blob,audit=document_module.render_report(dict(kind='product',center='LAB',language=language,variant='Standard'),context,authoring=authoring)
    assert audit['noticeCodes']==[] and context==before
    with ZipFile(BytesIO(blob)) as z:
        text=''.join(etree.fromstring(z.read('word/document.xml')).xpath('//*[local-name()="t"]/text()'))
    assert address in text


def test_no_appendix_module_or_calls_remain():
    from pathlib import Path
    root=Path(document_module.__file__).parent
    assert not (root/'location_appendix.py').exists()
    assert 'location_appendix' not in (root/'report_documents.py').read_text()

def test_only_typed_location_notice_is_nonblocking():
    from app.report_generation_notices import LocationTruncatedNotice, split_generation_warnings
    note=LocationTruncatedNotice()
    blocking,notices=split_generation_warnings([note,'附件转换失败',str(note)])
    assert blocking==['附件转换失败',str(note)]
    assert notices==[str(note)]


@pytest.mark.parametrize('blocking',[False,True])
def test_preview_notice_does_not_hide_conversion_failure(isolated_app,monkeypatch,blocking):
    from app import preview_cache as cache
    from app.extensions import db
    from app.models import Report
    from app.report_generation_notices import LocationTruncatedNotice
    with isolated_app.app_context():
        r=Report(report_no='QA-NOTICE',status='检测录入中',detail={})
        db.session.add(r);db.session.commit()
        monkeypatch.setattr(cache,'source_key',lambda _: 'key')
        monkeypatch.setattr(cache,'_locked',lambda _:False)
        notes=[LocationTruncatedNotice()]+(['附件转换失败'] if blocking else [])
        monkeypatch.setattr(cache,'build_complete_report_pdf',lambda _: (b'%PDF-fixture',notes))
        path=cache._entry(r.report_no,'key');claim=cache._claim(path)
        cache._execute(isolated_app,r.report_no,'key',path,claim)
        state=cache._state(path)
        assert state['status']==('failed' if blocking else 'ready')
        if not blocking:assert state['notices']==[str(LocationTruncatedNotice())]
