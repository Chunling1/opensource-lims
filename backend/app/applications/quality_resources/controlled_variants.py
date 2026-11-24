"""Pure planning of current controlled records; never choose among old dates.

Source row ownership, not a same-code permission union, defines each group.
Historical rows absent from the source remain historical, not newly authorized.
"""

PRESERVED_FIELDS = ('impl_date', 'void_date', 'is_english', 'location',
                    'issue_count', 'issuer', 'delay_days', 'replace_no')


def plan_controlled_groups(source, predecessors, maintained_ids):
    groups = {}
    for variant in source.get('sourceVariants', []):
        values = variant.get('values')
        if values is None:  # Explicitly confirmed supplement, not a main row.
            continue
        number = str(values.get('受控号') or '').strip()
        group = groups.setdefault(number, {'controlledNo': number, 'sourceRows': [], 'departments': []})
        group['sourceRows'].append(variant['sourceRow'])
        for department in variant['departmentAuthorization']['names']:
            if department not in group['departments']:
                group['departments'].append(department)
    if not groups:
        groups[str(source.get('controlledNo') or '').strip()] = {
            'controlledNo': str(source.get('controlledNo') or '').strip(),
            'sourceRows': source['sourceRows'], 'departments': source['departments']}
    result = []
    for number, group in groups.items():
        exact = [row for row in predecessors if str(row.controlled_no or '').strip() == number]
        variants = {}
        for row in exact:
            # None and a real date stay distinct. Do not infer a missing value.
            attributes = {field: getattr(row, field, None) for field in PRESERVED_FIELDS}
            identity = tuple(attributes.values())
            variant = variants.setdefault(identity, {**attributes, 'predecessorIds': []})
            variant['predecessorIds'].append(row.id)
        if not variants:
            variants[(None, None, False)] = {
                **dict.fromkeys(PRESERVED_FIELDS), 'is_english': False, 'predecessorIds': []}
        # The approved onsite attribute describes the standard, not its language.
        maintained = {bool(row.is_onsite_standard) for row in predecessors if row.id in maintained_ids}
        if len(maintained) > 1:
            raise ValueError(f"{source['code']} 已维护的现场属性冲突，不能自动覆盖")
        result.append({**group, 'variants': list(variants.values()),
            'isOnsiteStandard': next(iter(maintained)) if maintained else source['isOnsiteStandard']})
    assigned_rows = [row for group in result for row in group['sourceRows']]
    if len(assigned_rows) != len(set(assigned_rows)) or set(assigned_rows) != set(source['sourceRows']):
        raise ValueError('受控记录来源行归属不完整或重复')
    return result
