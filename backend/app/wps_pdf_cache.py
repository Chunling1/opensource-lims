"""Private persistent WPS results, shared by all authorized document entry points.

Only ZIP envelopes are ignored. XML metadata, images and relationships remain
part of the key. No document bytes, permission decisions or public URLs are
cached in memory. Failed conversions are never published.
"""
import hashlib
import json
import logging
import time
from io import BytesIO
from zipfile import ZipFile, BadZipFile
from flask import has_app_context


def content_hash(raw, suffix):
    digest = hashlib.sha256()
    digest.update(suffix.lower().encode())
    if suffix.lower() in ('.docx', '.xlsx', '.pptx'):
        try:
            with ZipFile(BytesIO(raw)) as archive:
                for entry in sorted(archive.infolist(), key=lambda row: row.filename):
                    digest.update(entry.filename.encode());digest.update(b'\0')
                    digest.update(hashlib.sha256(archive.read(entry)).digest())
            return digest.hexdigest()
        except (BadZipFile, RuntimeError):
            pass
    digest.update(raw)
    return digest.hexdigest()


def convert_once(raw, suffix, converter, *, policy='wps'):
    if not raw or not has_app_context():
        return converter()
    from . import preview_cache as cache
    from .preview_fingerprint import office_conversion_hash
    key = hashlib.sha256((content_hash(raw, suffix) + office_conversion_hash() + policy).encode()).hexdigest()
    path = cache._entry('wps-pdf-v1', key)
    start = time.monotonic()
    claim = cache._claim(path, blocking=True)
    try:
        try:
            record = json.loads((path / 'result.json').read_text('utf-8'))
            pdf = (path / 'result.pdf').read_bytes()
            if (record['key'] == key and pdf.startswith(b'%PDF-')
                    and hashlib.sha256(pdf).hexdigest() == record['sha256']):
                logging.getLogger(__name__).info('wps_pdf_cache hit elapsed_ms=%.1f', (time.monotonic()-start)*1000)
                return pdf
        except (OSError, ValueError, KeyError, TypeError):
            pass
        # Only an actual Office conversion occupies the shared WPS slot.
        # PDF composition and verified conversion-cache hits need no WPS lock.
        from .preview_timing import Trace
        trace = Trace('office-conversion')
        global_path = cache._root() / 'render'
        global_path.mkdir(mode=0o700, exist_ok=True)
        with trace.stage('global_queue'):
            turn = cache._claim(global_path, blocking=True)
        try:
            with trace.stage('convert'):
                pdf = converter()
        finally:
            cache._release(turn)
        if pdf and pdf.startswith(b'%PDF-'):
            cache._atomic(path / 'result.pdf', pdf)
            cache._atomic(path / 'result.json', json.dumps({
                'key': key, 'sha256': hashlib.sha256(pdf).hexdigest(),
            }).encode())
        return pdf
    finally:
        cache._release(claim)
