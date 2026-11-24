"""Keep the user's current request distinct from the last review's final marks."""


def requested_seal(detail):
    detail = detail or {}
    resolution = detail.get('complianceResolution') or {}
    for key in ('requestedSealCurrent', 'requestedSealOriginal'):
        if key in resolution:
            return str(resolution[key] or '').strip()
    raw = detail.get('rawSample') or {}
    if 'seal' in raw:
        return str(raw['seal'] or '').strip()
    for section in detail.get('summary') or []:
        if section.get('title') == '委托信息':
            for field in section.get('fields') or []:
                if len(field) >= 2 and field[0] == '盖章要求':
                    return str(field[1] or '').strip()
    # Older reports may only have the accepted review/configuration snapshot.
    review = detail.get('contractReview') or {}
    if 'sealRequirement' in review:
        return str(review['sealRequirement'] or '').strip()
    for source in (review, detail.get('sampleConfiguration') or {}):
        if 'requiredCma' in source or 'requiredCnas' in source:
            return ' + '.join(mark for key, mark in [('requiredCma', 'CMA'), ('requiredCnas', 'CNAS')] if source.get(key))
    return str((detail.get('checkInput') or {}).get('seal') or '').strip()
