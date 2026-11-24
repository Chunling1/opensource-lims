from io import BytesIO
from zipfile import ZipFile
from lxml import etree
import pytest
from app import document_module
from app.report_generation_notices import notices_from_audit, split_generation_warnings, TemplateFieldNotice
pytest_plugins = ('testkit.fixtures',)

@pytest.mark.parametrize('variant',['Standard','Extended'])
@pytest.mark.parametrize('kind',['product','sampling'])
def test_long_conclusion_text_and_line_breaks_are_preserved(kind,variant):
    value='合成测试结论甲乙丙丁'*30+'\n峰值效率为0.78，额定效率为0.53。\n峰值功率为1466W，额定功率为996W。\n检验数据详见后页。'
    blob,audit=document_module.render_report(dict(kind=kind,center='LAB',language='CN',variant=variant),{'Conclusion':value})
    with ZipFile(BytesIO(blob)) as z:
        xml=etree.fromstring(z.read('word/document.xml'))
    texts=''.join(xml.xpath('//*[local-name()="t"]/text()'))
    assert all(line in texts for line in value.splitlines())
    assert 'Conclusion' not in audit['capacityWarnings']

@pytest.mark.parametrize('blocking',[False,True])
def test_template_difference_notice_is_nonblocking_but_conversion_error_is_not(isolated_app,monkeypatch,blocking):
    from app import preview_cache as cache
    from app.extensions import db
    from app.models import Report
    with isolated_app.app_context():
        report=Report(report_no='QA-TEXT-NOTICE',status='检测录入中',detail={})
        db.session.add(report);db.session.commit()
        monkeypatch.setattr(cache,'source_key',lambda _: 'key')
        monkeypatch.setattr(cache,'_locked',lambda _:False)
        notices=notices_from_audit({'capacityWarnings':['Conclusion','TestDate']})
        warnings=notices+(['附件转换失败'] if blocking else [])
        monkeypatch.setattr(cache,'build_complete_report_pdf',lambda _: (b'%PDF-fixture',warnings))
        path=cache._entry(report.report_no,'key');claim=cache._claim(path)
        cache._execute(isolated_app,report.report_no,'key',path,claim)
        state=cache._state(path)
        assert state['status']==('failed' if blocking else 'ready')
        if not blocking:assert state['notices']==list(map(str,notices))

def test_plain_warning_strings_are_not_silently_demoted():
    note=TemplateFieldNotice(['Conclusion'])
    blocking, notices=split_generation_warnings([note,str(note),'附件转换失败'])
    assert blocking==[str(note),'附件转换失败']
    assert notices==[str(note)]
