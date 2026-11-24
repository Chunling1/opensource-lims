"""Shared persistent final PDFs for sync and async entrust print snapshots."""
import hashlib
from io import BytesIO
from zipfile import ZipFile

from flask import current_app, has_request_context, jsonify, Response, request
from itsdangerous import URLSafeTimedSerializer
from . import preview_cache as cache


def _serializer():
    return URLSafeTimedSerializer(current_app.config['JWT_SECRET'], salt='entrust-preview-v1')


def docx_key(raw, kind):
    # Ignore ZIP envelope timestamps/compression only, NOT document text,
    # embedded images, fonts, relationships, fields or XML metadata.
    digest = hashlib.sha256()
    with ZipFile(BytesIO(raw)) as archive:
        for name in sorted(archive.namelist()):
            digest.update(name.encode()); digest.update(b'\0')
            digest.update(hashlib.sha256(archive.read(name)).digest())
    from .preview_fingerprint import conversion_hash
    digest.update(kind.encode()); digest.update(conversion_hash().encode())
    return digest.hexdigest()


def _publish(raw, kind, path, trace, page_counter=None):
    from .docx_pdf import docx_to_pdf_wps
    from .document_module import entrust_background
    from .entrust_render import require_business_form_page_count
    with trace.stage('wps_conversion'):
        pdf = docx_to_pdf_wps(raw)
    if not pdf:
        raise ValueError('WPS 转换不可用或超时，请稍后重试')
    with trace.stage('background'):
        pdf = entrust_background(pdf)
    with trace.stage('validate_and_publish'):
        pages = (page_counter or require_business_form_page_count)(pdf, kind)
        cache._atomic(path / 'preview.pdf', pdf)
        cache._write(path, 'ready', message='委托单预览已生成', pages=pages,
                     pdfHash=hashlib.sha256(pdf).hexdigest())
    return pdf, pages


def render_pdf(raw, kind, *, page_counter=None):
    """Authorized synchronous callers share the async final PDF on disk.

    Caller owns permissions. The same per-document claim prevents concurrent
    sync/async requests from publishing or converting the same snapshot twice.
    """
    from .preview_timing import Trace
    trace = Trace('entrust-sync')
    key = docx_key(raw, kind)
    path = cache._entry('entrust', key)
    claim = cache._claim(path, blocking=True)
    try:
        # No _state() here: it probes the very lock we already hold.
        import json
        try:
            state = json.loads((path / 'state.json').read_text('utf-8'))
            pdf = (path / 'preview.pdf').read_bytes()
            if (state.get('status') == 'ready' and pdf.startswith(b'%PDF-')
                    and hashlib.sha256(pdf).hexdigest() == state.get('pdfHash')):
                current_app.logger.info('entrust_pdf_cache hit')
                return pdf, state['pages']
        except (OSError, ValueError, KeyError, TypeError):
            pass
        cache._atomic(path / 'source.docx', raw)
        return _publish(raw, kind, path, trace, page_counter)
    finally:
        cache._release(claim)


def _execute(app, key, kind, path, claim):
    from .preview_timing import Trace
    trace = Trace('entrust')
    try:
        with app.app_context():
            cache._write(path, 'running', message='正在转换委托单 PDF')
            raw = (path / 'source.docx').read_bytes()
            if docx_key(raw, kind) != key:
                raise ValueError('委托单源文件或模板版本已变化，请重新预览')
            _publish(raw, kind, path, trace)
    except Exception as exc:
        app.logger.exception('entrust background conversion failed')
        message = str(exc)[:240] if isinstance(exc, ValueError) else '委托单转换失败，请联系管理员核查'
        cache._write(path, 'failed', message=message)
    finally:
        cache._release(claim)


def ensure(raw, kind, retry=False):
    key = docx_key(raw, kind)
    path = cache._entry('entrust', key)
    state = cache._state(path)
    if state['status'] in ('missing', 'stale') or (state['status'] == 'failed' and retry):
        claim = cache._claim(path)
        if claim is not None:
            try:
                # Re-read under the claim: other requests may have completed.
                import json
                try: latest = json.loads((path / 'state.json').read_text(encoding='utf-8'))
                except (ValueError, FileNotFoundError): latest = {}
                if latest.get('status') == 'ready' and state['status'] != 'failed':
                    cache._release(claim)
                    state = latest
                else:
                    cache._atomic(path / 'source.docx', raw)
                    state = cache._write(path, 'queued', message='委托单正在排队生成')
                    cache._enqueue(current_app._get_current_object(), (_execute, key, kind, path, claim))
            except Exception:
                cache._release(claim)
                state = cache._write(path, 'failed', message='委托单生成队列暂不可用，请重试')
    return state, key


def prepare(raw, kind, user, metadata, retry=False):
    state, key = ensure(raw, kind, retry)
    ticket = _serializer().dumps({'uid': user.id, 'key': key, **metadata})
    if state['status'] == 'ready':
        return read(ticket, user)
    return _response(state, ticket)


def _response(state, ticket):
    code = 1 if state['status'] == 'failed' else 0
    return jsonify({'code': code, 'message': state.get('message', ''),
                    'data': {**state, 'pollUrl': '/api/samples/entrust-preview-jobs/' + ticket}}), (200 if code else 202)


def read(ticket, user):
    """Re-authorize every poll/download; signed ticket alone grants no access."""
    from .models import Report
    from .applications.report_lifecycle.queries import scoped_report_query
    try:
        data = _serializer().loads(ticket, max_age=1800)
        key = data['key']
        if data['uid'] != user.id or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError()
        from .blueprints.samples import _can_read_sample_form
        if not _can_read_sample_form(user):
            raise ValueError()
        # Persisted samples retain their exact department/data-scope boundary.
        report_no = data.get('persistedReportNo')
        if report_no and scoped_report_query(Report.query, user).filter_by(report_no=report_no).first() is None:
            raise ValueError()
    except Exception:
        return jsonify({'code': 403, 'message': '预览凭据过期或无访问权限，请重新打开预览', 'data': None}), 200
    path = cache._entry('entrust', key)
    state = cache._state(path)
    if state['status'] != 'ready':
        return _response(state, ticket)
    pdf = (path / 'preview.pdf').read_bytes()
    if hashlib.sha256(pdf).hexdigest() != state['pdfHash']:
        return jsonify({'code': 1, 'message': '委托单缓存校验失败，请重新生成', 'data': None}), 200
    from .blueprints.samples import _parse_pdf_pages, _select_pdf_pages
    pages = _parse_pdf_pages(data.get('pages', ''), state['pages'])
    if pages:
        pdf = _select_pdf_pages(pdf, pages)
    # Check only AFTER all existing authorization, state and integrity checks.
    # Hash the actual selected output so page subsets cannot share validators.
    etag = hashlib.sha256(pdf).hexdigest()
    if has_request_context() and request.if_none_match.contains(etag):
        return Response(status=304, headers={
            'ETag': f'"{etag}"', 'Cache-Control': 'private, no-store',
        })
    return Response(pdf, mimetype='application/pdf', headers={
        **data['headers'], 'Cache-Control': 'private, no-store',
        'ETag': f'"{etag}"',
        'X-Preview-Engine': 'wps', 'X-Expected-Pages': str(state['pages']),
    })
