from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace as NS
import pytest
from app.return_data_recovery import propose_dates, repaired_state, fingerprint


def test_evidence_uses_snapshot_business_date_not_operation_date():
    event = NS(id=7, success=True, action='sample.inbound.confirm', created_at=datetime(2026,10,27),
               before_data={}, after_data={'workflowDates': {'sampleInboundAt': '2026-10-22'}})
    evidence = propose_dates({}, [event])
    assert evidence['sampleInboundAt']['value'] == '2026-10-22'
    assert propose_dates({'sampleInboundAt': '2026-10-23'}, [event]) == {}
    event.after_data = {}
    assert propose_dates({}, [event]) == {}


def test_repair_preserves_testing_and_recently_filled_values_and_rejects_changed_state():
    before = {'detail': {'checkInput': {'result': '用户最新补填'}, 'attachments': [1], 'workflowDates': {}},
              'status': '检测录入中', 'sampleStatus': '已领取', 'samplePickup': {'signed': True}, 'voided': False}
    plan = {'expectedSha256': fingerprint(before), 'dates': {'sampleInboundAt': {'auditId': 7, 'value': '2026-10-22'}}}
    result = repaired_state(before, plan)
    assert result['detail']['checkInput'] == before['detail']['checkInput']
    assert result['detail']['attachments'] == [1]
    assert before['detail']['workflowDates'] == {}
    changed = deepcopy(before); changed['detail']['checkInput']['result'] = '保存了更新内容'
    with pytest.raises(ValueError, match='已被修改'):
        repaired_state(changed, plan)


def test_repair_cannot_overwrite_present_business_date():
    before = {'detail': {'workflowDates': {'sampleInboundAt': '2026-10-23'}}, 'status': '检测录入中',
              'sampleStatus': '已领取', 'samplePickup': None, 'voided': False}
    with pytest.raises(ValueError, match='缺失字段'):
        repaired_state(before, {'expectedSha256': fingerprint(before),
            'dates': {'sampleInboundAt': {'auditId': 7, 'value': '2026-10-22'}}})


def test_no_snapshot_never_fabricates_testing_content():
    before = {'detail': {'checkInput': {'seal': 'CNAS'}}, 'status': '检测录入中',
              'sampleStatus': '已领取', 'samplePickup': None, 'voided': False}
    result = repaired_state(before, {'expectedSha256': fingerprint(before), 'missingTestingData': True})
    assert result['detail']['checkInput'] == {'seal': 'CNAS'}
    assert result['detail']['testDataReviewRequired']['kind'] == 'historical_missing'
