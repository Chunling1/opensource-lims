"""User-approved English display values, applied only at report rendering.

This is not a qualification/site resolver. Match complete known addresses so
an onsite address in the same district is never replaced by a laboratory.
Unknown/custom values and persisted business data remain untouched.
"""
import re


CATEGORIES = {
    '委托': 'Commission',
    '委托(有见证送检)': 'Commission (with Witnessed Sampling)',
    '型式检验': 'Type Inspection',
    '型式试验': 'Type Test',
    '抽样检测': 'Sampling Test',
    '抽样型式检验': 'Sampling Type Inspection',
}

# Approved wording supplied on 2026-11-03. Aliases are complete stored values,
# not substring matches (notably Daxing has a different historical address).
SITES = (
    (('示例站点B', '示例市东区实验大道2号'),
     'No.2 Lab Avenue, East District, Example City'),
    (('示例站点E', '示例市华南工业园西区12号'),
     'No.12 West Park, South Industrial Zone, Example City'),
    (('示例站点D', '示例市南区高新街7号5号楼'),
     'Building 5, Yard 7, High-Tech Street, South District, Example City'),
    (('示例站点G', '示例市华东检测基地166号',
      '示例市华东研发检测中心166号'),
     'No.166 East R&D Testing Center, Example City'),
    (('示例站点A', '示例市科技园区一号院1号楼'),
     'Building 1, Yard 1, Science Park, Example City'),
    (('示例站点H', '示例市齐鲁产业园88号'),
     'No.88 North Industrial Park, Example City'),
    (('示例站点I', '示例市海滨实验园2号'),
     'No.2 Coastal Lab Park, Example City'),
    (('示例站点C', '示例园区实验楼 A 座'),
     'Building A, Demo Lab Park, Example City'),
    (('示例站点F', '示例市华北产业园兴业大街6号', '示例市华北产业园兴业大街6号'),
     'No.6 Central Industrial Park, Example City'),
)


def _key(value):
    return re.sub(r'\s+', '', value).replace('（', '(').replace('）', ')')


_ADDRESSES = {_key(alias): english for aliases, english in SITES for alias in aliases}


def english_category(value):
    return CATEGORIES.get(_key(value), value)


def english_sample_condition(value):
    # Translate only the two built-in choices, not user-authored descriptions.
    return {'正常': 'Normal', '异常': 'Abnormal'}.get(value.strip(), value)


def english_place(value):
    # Stored multi-site locations use semicolons; keep English address commas.
    # A maintained calibration address may include this explicit prefix.
    def translate(part):
        key = _key(part)
        if key.startswith('(校准实验室)'):
            key = key[len('(校准实验室)'):]
        return _ADDRESSES.get(key, part)

    return '; '.join(translate(part.strip()) for part in re.split(r'[；;\r\n]+', value)
                     if part.strip())


def localize_report_fields(context, *, language):
    result = dict(context)
    if language == 'EN':
        for field, formatter in (('Category', english_category), ('Place', english_place),
                                 ('SampleCondition', english_sample_condition)):
            if isinstance(result.get(field), str):
                result[field] = formatter(result[field])
    return result
