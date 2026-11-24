"""Explicit, evidence-based repair; never called by normal report reads/saves."""
from copy import deepcopy
import hashlib
import json

DATE_KEYS = {'sampleInboundAt', 'sampleAvailableAt', 'samplePickupAt'}


def state(report):
    return {'detail': report.detail or {}, 'status': report.status,
            'sampleStatus': report.sample_status, 'samplePickup': report.sample_pickup,
            'voided': bool(report.voided)}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def propose_dates(current, audits):
    """Recover a missing value only from an audit snapshot, never created_at."""
    evidence = {}
    for audit in audits:
        if not audit.success:
            continue
        for side, snapshot in (('before', audit.before_data), ('after', audit.after_data)):
            if not isinstance(snapshot, dict):
                continue
            dates = snapshot.get('workflowDates') or {}
            for key in DATE_KEYS:
                if dates.get(key):
                    evidence[key] = {'value': dates[key], 'auditId': audit.id, 'side': side,
                                     'action': audit.action, 'operationUtc': str(audit.created_at)}
    return {key: item for key, item in evidence.items() if not current.get(key)}


def repaired_state(before, plan):
    """Compare the entire reviewed state, and preserve all unlisted fields."""
    if fingerprint(before) != plan['expectedSha256']:
        raise ValueError('报告在清单生成后已被修改，跳过并重新核对')
    if before['voided']:
        raise ValueError('作废报告不自动修复')
    result = deepcopy(before)
    dates = result['detail'].setdefault('workflowDates', {})
    for key, evidence in plan.get('dates', {}).items():
        if key not in DATE_KEYS or dates.get(key) or not evidence.get('auditId'):
            raise ValueError('日期恢复项不满足缺失字段及审计证据约束')
        dates[key] = evidence['value']
    if plan.get('returnPlan'):
        result['detail']['returnPlan'] = deepcopy(plan['returnPlan'])
        if result['status'] in {'待合同评审', '委托更改中'}:
            result['detail']['requiresContractReReview'] = True
    if plan.get('resumeStatus'):
        if before['status'] not in {'待样品入库', '待样品领取'} or not plan.get('routingEvidence'):
            raise ValueError('历史返回节点缺少明确复评证据')
        result['status'] = plan['resumeStatus']
        result['sampleStatus'] = plan['resumeSampleStatus']
    if plan.get('missingTestingData'):
        result['detail']['testDataReviewRequired'] = {
            'kind': 'historical_missing', 'fields': [],
            'message': '此报告曾在委托更改时丢失检测录入内容。现有内容及附件已保留，但缺少可完整恢复的快照，请核对原始记录后补齐检测数据。',
        }
    return result
