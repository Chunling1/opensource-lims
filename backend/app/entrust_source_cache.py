"""Memoize the original entrust renderer, before Word construction.

Only asynchronous original-DocParser previews opt in. The canonical input is
the exact maker context plus post-processing inputs, not database timestamps.
Routes keep their authorization, original renderer and transaction ownership.
"""
import hashlib
import json

from . import preview_cache as cache


from .preflight_reads import reuse_preflight_reads


@reuse_preflight_reads
def render(entrust, report, kind, project_no='', language='CN'):
    from . import docparser_field_only as fields
    from .entrust_render import _business_values

    # Compute using existing functions on every request: changes to related
    # configuration, in-memory form values and embedded image bytes are seen.
    selection = fields.entrust_profile_for(entrust, report, kind)
    context = fields.entrust_context(entrust, report, kind, project_no, language)
    location = _business_values(entrust, report, project_no)['test_location']
    signature = cache.verified_package_signature()
    source = {'schema': 1, 'engine': cache._engine_hash(), 'package': signature,
              'profile': selection, 'context': context, 'location': location, 'language': language,
              'entrustNo': fields.text(getattr(entrust, 'entrust_no', ''))}
    try:
        raw_key = json.dumps(source, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError):
        # Unknown future inputs are not silently converted or ignored.
        return fields.render_entrust(entrust, report, kind, project_no, language)
    key = hashlib.sha256(raw_key).hexdigest()
    path = cache._entry('entrust-source-v1', key)
    claim = cache._claim(path, blocking=True)
    try:
        try:
            record = json.loads((path / 'source.json').read_text(encoding='utf-8'))
            raw = (path / 'source.docx').read_bytes()
            audit = record['audit']
            if (record['key'] == key and isinstance(audit, dict)
                    and audit.get('templateSelection') == selection
                    and hashlib.sha256(raw).hexdigest() == record['sha256']):
                return raw, audit
        except (OSError, ValueError, KeyError, TypeError):
            pass
        # Preserve the public renderer as the dependency/monkeypatch boundary.
        raw, audit = fields.render_entrust(entrust, report, kind, project_no, language)
        if raw:
            record = {'key': key, 'sha256': hashlib.sha256(raw).hexdigest(), 'audit': audit}
            encoded = json.dumps(record, ensure_ascii=False, allow_nan=False).encode()
            cache._atomic(path / 'source.docx', raw)
            cache._atomic(path / 'source.json', encoded)
        return raw, audit
    finally:
        cache._release(claim)
