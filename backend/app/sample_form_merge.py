"""Registration forms own sample fields, never saved testing/workflow data."""
from copy import deepcopy

FORM_FIELDS = ('summary', 'rawSample', 'entrustSnapshot', 'projectName', 'trademark', 'trademarkImage')
TEST_INPUT_FIELDS = ('sampleName', 'spec', 'manufacturer', 'project', 'projectList',
                     'testBases', 'standardItemIds', 'judgeBases', 'judgmentEntries', 'testDept', 'reportType', 'standardJudge',
                     'capabilitySnapshots', 'detectionSubprojects', 'sampleAmount',
                     'factoryNo', 'testPlan', 'schemeCode', 'testLocation')
SAMPLE_SECTIONS = {'委托信息', '送样信息', '样品信息', '项目信息', '抽样信息', '结算信息',
                   '子项目信息', '检测子项目信息', '报告发送', '实验信息'}
RUNTIME_LABELS = {'流转状态', '检测设备', '检测日期', '检测起始日期', '检测结束日期'}


def merge_summary(previous, submitted):
    result = deepcopy(previous or [])
    for section in submitted or []:
        title = section.get('title')
        if title not in SAMPLE_SECTIONS:
            continue
        target = next((s for s in result if s.get('title') == title), None)
        if target is None:
            target = {'title': title, 'fields': []}
            result.append(target)
        fields = dict(target.get('fields') or [])
        for key, value in section.get('fields') or []:
            if key not in RUNTIME_LABELS:
                fields[key] = deepcopy(value)
        target['fields'] = [list(pair) for pair in fields.items()]
    return result


def normalize_judgment_entries(detail):
    raw = detail.get('rawSample')
    if not isinstance(raw, dict) or 'judgmentEntries' not in raw:
        return
    entries = raw['judgmentEntries']
    if not isinstance(entries, list) or any(not isinstance(entry, str) or not entry.strip() for entry in entries):
        raise ValueError('判定标准条目格式无效，请逐条添加后重试')
    raw['judgmentEntries'] = list(dict.fromkeys(entry.strip() for entry in entries))
    raw['standardJudge'] = '；'.join(raw['judgmentEntries'])


def merge_sample_form(previous, submitted):
    detail = deepcopy(previous or {})
    for key in FORM_FIELDS:
        if key not in submitted:
            continue
        value = deepcopy(submitted[key])
        if key == 'summary':
            value = merge_summary(detail.get(key), value)
        if key in ('rawSample', 'entrustSnapshot') and isinstance(value, dict):
            value = {**detail.get(key, {}), **value}
        detail[key] = value
    old_raw = (previous or {}).get('rawSample') or {}
    new_raw = detail.get('rawSample') or {}
    # New forms explicitly submit the request, including when the user chooses
    # the same value as an earlier stripped result. An unchanged legacy form
    # without that field must not erase the original request.
    submitted_raw = submitted.get('rawSample') or {}
    if 'judgmentEntries' not in submitted_raw and 'standardJudge' in submitted_raw and submitted_raw['standardJudge'] != old_raw.get('standardJudge'):
        new_raw.pop('judgmentEntries', None)
    explicit_request = 'requestedSeal' in submitted and submitted['requestedSeal'] == submitted_raw.get('seal')
    if 'seal' in submitted_raw and (explicit_request or submitted_raw['seal'] != old_raw.get('seal')):
        resolution = dict(detail.get('complianceResolution') or {})
        if resolution:
            resolution['requestedSealCurrent'] = str(submitted_raw['seal'] or '').strip()
            detail['complianceResolution'] = resolution
    changed = [key for key in TEST_INPUT_FIELDS if old_raw.get(key) != new_raw.get(key)]
    if changed and (previous or {}).get('checkInput'):
        review = detail.get('testDataReviewRequired') or {}
        detail['testDataReviewRequired'] = {
            **review,
            'fields': sorted(set(review.get('fields', []) + changed)),
            'message': review.get('message') if review.get('kind') == 'historical_missing' else
                       '委托／样品检测相关信息已更改，原检测数据与附件已保留，请复核是否仍适用。',
        }
    return detail
