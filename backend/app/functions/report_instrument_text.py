"""Report-only equipment projection; no writes or live equipment lookups."""


def _field(value):
    return ' '.join(str(value).split()) if value is not None else ''


def report_instrument_text(snapshots, legacy_text='', display=None, separator=None):
    """Keep recorded equipment order and honor saved optional display fields.

    Use saved report snapshots, not today's equipment catalogue. Historical
    free text without structured snapshots is retained, because punctuation
    inside model names is not a reliable equipment delimiter.
    """
    if not isinstance(snapshots, (list, tuple)):
        return legacy_text
    # Missing preferences retain the historic archive/name/model projection.
    # An explicit false must never be replaced by a truthy default.
    options = {'archiveNo': True, 'spec': True, 'maker': False, 'factoryNo': False}
    if isinstance(display, dict):
        options.update({key: value for key,value in display.items()
                        if key in options and isinstance(value, bool)})
    keys = (['archiveNo'] if options['archiveNo'] else []) + ['name']
    keys += [key for key in ('spec','maker','factoryNo') if options[key]]
    rows = []
    for item in snapshots:
        if not isinstance(item, dict):
            continue
        fields = [_field(item.get(key)) for key in keys]
        row = ' '.join(field for field in fields if field)
        if row:
            rows.append(row)
    from .report_standard_text import display_separator
    return display_separator(separator).join(rows) if rows else legacy_text
