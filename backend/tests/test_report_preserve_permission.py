"""Exercise the real content-save handler with isolated persistence collaborators."""
from types import SimpleNamespace
from unittest.mock import Mock
import importlib
import pytest
from flask import Flask, g


@pytest.fixture
def handler(monkeypatch):
    module = importlib.import_module('app.blueprints.report_documents')
    report = SimpleNamespace(id=1, report_no='AUDIT-ONLY', detail={})
    user = SimpleNamespace(enabled=True, role_key='admin', account='qa-admin', name='QA',
                           department=SimpleNamespace(code='ROOT'),
                           action_codes=lambda: {'report.attachment.upload'})
    row = SimpleNamespace()
    monkeypatch.setattr(module, '_report_for_user', lambda _: report)
    monkeypatch.setattr(module, 'Report', SimpleNamespace(query=SimpleNamespace(
        filter_by=lambda **_: SimpleNamespace(with_for_update=lambda: SimpleNamespace(
            populate_existing=lambda: SimpleNamespace(one=lambda: report))))))
    monkeypatch.setattr(module, 'report_data_entry_step_error', lambda *_: None)
    monkeypatch.setattr(module, 'report_content_editable', lambda _: True)
    monkeypatch.setattr(module, 'ReportDocumentContent', SimpleNamespace(query=SimpleNamespace(
        filter_by=lambda **_: SimpleNamespace(first=lambda: row))))
    attachment = Mock()
    attachment.query.filter.return_value.all.return_value = []
    monkeypatch.setattr(module, 'ReportAttachment', attachment)
    monkeypatch.setattr(module, 'select_profile', lambda _: None)
    monkeypatch.setattr(module, 'content_dict', lambda report, row=None: {
        'compositionOptions': module.composition_options(report)})
    monkeypatch.setattr(module, 'document_preflight', lambda report: {
        'content': {'compositionOptions': module.composition_options(report)}})
    monkeypatch.setattr(module, 'db', SimpleNamespace(session=SimpleNamespace(flush=Mock(), commit=Mock())))
    audit = Mock()
    monkeypatch.setattr(module, 'add_operation_audit', audit)
    monkeypatch.setattr('app.preview_cache.schedule_after_save', lambda _: None)
    monkeypatch.setattr('app.docparser_field_only.applies_to', lambda _: True)
    monkeypatch.setattr('app.docparser_field_only.profile_for', lambda *_, **__: {})
    app = Flask(__name__)
    @app.before_request
    def identity():
        g.current_user = user
    app.add_url_rule('/content', view_func=module.save_content.__wrapped__, defaults={'report_no':'AUDIT-ONLY'}, methods=['PUT'])
    return app.test_client(), report, user, audit


@pytest.mark.parametrize('account,role', [('qa-admin','admin'),('admin','tester')])
def test_administrator_enable_disable_is_persisted_and_audited(handler,account,role):
    client, report, user, audit = handler
    user.account, user.role_key = account, role
    for value in [True, False]:
        response = client.put('/content', json={'compositionOptions':{'preserveUploadedReport':value}})
        assert response.status_code == 200
        assert response.json['code'] == 0
        assert report.detail['reportComposition']['preserveUploadedReport'] is value
        assert audit.call_args.kwargs['after']['compositionOptions']['preserveUploadedReport'] is value


@pytest.mark.parametrize('role,account,enabled', [('tester','ordinary',True),('tester','qa-user2',True),('admin','disabled',False)])
@pytest.mark.parametrize('previous', [False, True])
def test_non_administrator_cannot_change_either_direction_even_at_company_root(handler,role,account,enabled,previous):
    client, report, user, audit = handler
    user.role_key, user.account, user.enabled = role,account,enabled
    report.detail={'reportComposition':{'preserveUploadedReport':previous}}
    response=client.put('/content',json={'compositionOptions':{'preserveUploadedReport':not previous}})
    assert response.json['code']==403  # Existing API returns business codes in a 200 envelope.
    assert '仅管理员' in response.json['message']
    assert report.detail['reportComposition']['preserveUploadedReport'] is previous
    audit.assert_not_called()


def test_ordinary_content_save_preserves_existing_administrator_decision(handler):
    client,report,user,audit=handler
    user.role_key='tester'
    report.detail={'reportComposition':{'preserveUploadedReport':True}}
    response=client.put('/content',json={'compositionOptions':{}})
    assert response.json['code']==0
    assert report.detail['reportComposition']['preserveUploadedReport'] is True
