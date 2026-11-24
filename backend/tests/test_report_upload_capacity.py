"""Real multipart/storage boundaries, synthetic files and isolated local SQLite only."""
from io import BytesIO
from pathlib import Path
import pytest
from app.extensions import db
from app.models import Report, ReportAttachment
from app.security import issue_token

pytest_plugins=('testkit.fixtures',)
LIMIT=500*1024*1024


@pytest.fixture()
def upload_context(isolated_app,scenario_factory,monkeypatch):
    from app import preview_cache
    factory=scenario_factory
    dept=factory.department()
    project,steps=factory.project(dept)
    user=factory.user(dept,role_key='admin',permissions=['report.query.view'],project_steps=steps)
    factory.grant_action(user,'report.attachment.upload')
    report=Report(report_no='QA-LARGE',sample_no='QA-LARGE',department=dept.name,
        owner=user.name,project=project.name,status='检测录入中',sample_status='已领取',
        detail={'rawSample':{'schemeCode':project.code}})
    db.session.add(report);db.session.commit()
    monkeypatch.setattr(preview_cache,'schedule_after_save',lambda _:None)
    return isolated_app.test_client(),{'Authorization':'Bearer '+issue_token(user)},isolated_app


@pytest.mark.parametrize('category',['other','raw_record'])
def test_real_500mb_multipart_stream_upload(upload_context,tmp_path,category):
    client,headers,app=upload_context
    path=tmp_path/'synthetic.pdf'
    with path.open('wb') as f: f.write(b'%PDF-1.7\n');f.truncate(LIMIT)
    with path.open('rb') as f:
        response=client.post('/api/reports/QA-LARGE/attachments',headers=headers,
            data={'category':category,'file':(f,'synthetic.pdf')},content_type='multipart/form-data')
    assert response.status_code==200,response.get_data(as_text=True)[:500]
    assert response.json['code']==0,response.json
    attachment=ReportAttachment.query.one()
    assert attachment.stored_file.size_bytes==LIMIT
    assert app.config['MAX_CONTENT_LENGTH'] < LIMIT  # endpoint override, not a global widening


def test_500mb_plus_one_rejected_without_file_or_metadata(upload_context,tmp_path):
    client,headers,app=upload_context
    path=tmp_path/'oversized.pdf'
    with path.open('wb') as f: f.truncate(LIMIT+1)
    with path.open('rb') as f:
        response=client.post('/api/reports/QA-LARGE/attachments',headers=headers,
            data={'category':'raw_record','file':(f,'oversized.pdf')},content_type='multipart/form-data')
    assert response.json['code']==1 and '500MB' in response.json['message']
    assert ReportAttachment.query.count()==0
    assert not list((Path(app.config['STORAGE_ROOT'])/'.incoming').glob('*.part'))


def test_upload_still_requires_authentication(upload_context):
    client,_,_=upload_context
    response=client.post('/api/reports/QA-LARGE/attachments',data={'file':(BytesIO(b'x'),'a.pdf')})
    assert response.status_code in (401,403) or response.json['code'] in (401,403)
    assert ReportAttachment.query.count()==0
