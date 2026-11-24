"""Automatic notifications retain sequencing, provider ownership and deduplication."""
from datetime import date
import json
from types import SimpleNamespace

import pytest
from app.extensions import db
from app.functions import esign_service as service
from app.models import ReportEsignFlow, ReportEsignSigner, EsignReminderLog
from test_esign_workflow import _approved_report, _binding

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('mode', ['ordinary', 'provider-native-v1'])
def test_automatic_sms_current_turn_only_and_no_duplicate(isolated_app, scenario_factory, monkeypatch, mode):
    with isolated_app.app_context():
        identity = scenario_factory.identity_scenario()
        user = identity.user
        next_user = scenario_factory.user(identity.department, account='next_sms', name='后序人员')
        report = _approved_report('TEST-SMS-CLEANUP', identity.department.name, user.name)
        _binding(user, '13500000001')
        _binding(next_user, '13500000002')
        flow = ReportEsignFlow(report_id=report.id, report_no=report.report_no,
            report_document_version_id=report.approved_document_version_id,
            status='signing', source_sha256='test', provider_flow_id='local-only',
            positioning_json=json.dumps({'notificationMode': mode}))
        db.session.add(flow)
        db.session.flush()
        for order, signer in enumerate((user, next_user), 1):
            db.session.add(ReportEsignSigner(flow_id=flow.id, role_code=f'role{order}',
                role_name='测试', user_id=signer.id, legal_name_snapshot=signer.name, sign_order=order))
        db.session.add(EsignReminderLog(user_id=user.id, reminder_date=date.today().isoformat(),
            channel='sms', pending_count=1, status='sent'))
        db.session.commit()
        isolated_app.config.update(ESIGN_INITIAL_SMS_ENABLED=True, ESIGN_PRODUCTION_READY=True,
                                   ESIGN_PROVIDER_FLOW_MIN_ID=0)
        monkeypatch.setattr(service, 'flow_state_error', lambda flow: '')
        calls = []
        client = SimpleNamespace(request=lambda *args: calls.append(args))
        monkeypatch.setattr(service, '_ordinary_sms_preflight', lambda *args: (client, {'noticeTypes': '1'}))
        first = service.send_initial_sms_notifications(flow.id)
        second = service.send_initial_sms_notifications(flow.id)
        assert first['eligible'] == 1 and first['deferred'] == 1
        assert first['failed'] == second['failed'] == []
        assert second['sent'] == 0 and second['skipped'] == 1
        assert len(calls) == (1 if mode == 'ordinary' else 0)
        assert first['sent'] == (1 if mode == 'ordinary' else 0)
        assert first['providerManaged'] == (1 if mode == 'provider-native-v1' else 0)
        assert EsignReminderLog.query.filter_by(channel='sms', status='sent').count() == 1
