"""Typed, nonblocking notices for successful document-module results."""
LOCATION_TRUNCATED = '检测地点超出模板容量，已截断，请核对'

class GenerationNotice(str):
    pass

class LocationTruncatedNotice(GenerationNotice):
    def __new__(cls):
        return super().__new__(cls, LOCATION_TRUNCATED)

FIELD_LABELS = {
    'SAMPLENAME': '样品名称', 'SampleName': '样品名称', 'CLIENT': '委托单位', 'Client': '委托单位',
    'MANUFACTURER': '生产单位', 'Manufacturer': '生产单位', 'TestDate': '检测日期',
    'ManufacturingDate': '生产日期', 'Basis': '检测依据', 'BASIS': '检测依据',
    'Place': '检测地点', 'PLACE': '检测地点', 'Conclusion': '结论',
}

class TemplateFieldNotice(GenerationNotice):
    def __new__(cls, fields):
        labels = list(dict.fromkeys(FIELD_LABELS.get(field, field) for field in fields))
        return super().__new__(cls, 'Doc 模块处理后的' + '、'.join(labels) +
            '与输入原文不一致，可能被截短或调整格式，请核对预览；平台未截断原文。')

def notices_from_audit(audit):
    notices = [LocationTruncatedNotice()] if 'LOCATION_TRUNCATED' in audit.get('noticeCodes', []) else []
    if audit.get('capacityWarnings'):
        notices.append(TemplateFieldNotice(audit['capacityWarnings']))
    return notices

def split_generation_warnings(warnings):
    return ([w for w in warnings if not isinstance(w, GenerationNotice)],
            [str(w) for w in warnings if isinstance(w, GenerationNotice)])


def is_saved_generation_notice(value):
    # Used only to display stored version metadata, never to waive a failure.
    return value == LOCATION_TRUNCATED or (isinstance(value, str) and
        value.startswith('Doc 模块处理后的') and value.endswith('平台未截断原文。'))
