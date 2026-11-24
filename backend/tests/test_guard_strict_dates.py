"""No implicit administrator or legacy grant escape from date ordering."""
from datetime import date
from types import SimpleNamespace
import pytest
from app.workflow_dates import validate_after_previous, can_override_workflow_date
from app.platform.identity.access import can_override_workflow_date as identity_override

@pytest.mark.parametrize('role,actions', [('admin',[]),('operator',['workflow.date.override']),('operator',[])])
def test_date_order_is_mandatory_for_every_identity(role,actions):
    user=SimpleNamespace(role_key=role,account='admin' if role=='admin' else 'qa',action_codes=lambda:actions)
    assert not can_override_workflow_date(user)
    assert not identity_override(user)
    assert '不得早于' in validate_after_previous(user,'2026-10-01',date(2026,10,2),'检测日期','领取日期')
    assert '尚未完成' in validate_after_previous(user,'2026-10-01',None,'检测日期','领取日期')
    assert validate_after_previous(user,'2026-10-02',date(2026,10,2),'检测日期','领取日期') is None
    assert '有效日期' in validate_after_previous(user,'broken',date(2026,10,2),'检测日期','领取日期')
