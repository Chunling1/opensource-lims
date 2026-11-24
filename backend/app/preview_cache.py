"""Private, content-addressed preview jobs. No business/version writes.

Linux flock coordinates gunicorn workers. A bounded daemon queue survives closing
the browser; a process restart releases claims and exposes interrupted jobs as
failed (explicit retry only). All document generation retains the existing code.
"""
try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
import hashlib
import json
import os
from pathlib import Path
import queue
import threading
import time
import uuid

from flask import current_app
from .extensions import db
from .models import Report
from .report_documents import source_snapshot as _source_snapshot, snapshot_hash, build_complete_report_pdf

_init_lock = threading.Lock()
_package_lock = threading.Lock()


def verified_package_signature():
    # Production releases are immutable. Validate the full 59 MB package once
    # per process/file-stat generation, not on every 3-second status poll.
    # Actual rendering retains its original unconditional integrity checks.
    from .document_module import VENDOR, MANIFEST, verify_vendor
    app = current_app._get_current_object()
    with _package_lock:
        signature = []
        for path in [MANIFEST, *sorted(VENDOR.rglob('*'))]:
            if path.is_symlink():
                raise ValueError('DocParser 原包不能包含链接')
            if path.is_file():
                stat = path.stat()
                signature.append((str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        if app.extensions.get('preview_verified_package') != signature:
            verify_vendor()
            app.extensions['preview_verified_package'] = signature
    return signature


def source_snapshot(report):
    verified_package_signature()
    return _source_snapshot(report, verify_template=False)


def _root():
    root = Path(current_app.config['STORAGE_ROOT']) / 'preview_cache_v1'
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def _entry(report_no, key):
    # Neither user-supplied report numbers nor file names enter a storage path.
    path = _root() / hashlib.sha256(report_no.encode()).hexdigest() / key
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _atomic(path, data):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def _write(path, status, **extra):
    value = dict(status=status, updatedAt=time.time(), **extra)
    _atomic(path / 'state.json', json.dumps(value, ensure_ascii=False).encode())
    return value


def _claim(path, blocking=False):
    handle = (path / 'claim.lock').open('a+b')
    os.chmod(path / 'claim.lock', 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return handle
    except BlockingIOError:
        handle.close()
        return None


def _release(handle):
    if fcntl is not None:
        fcntl.flock(handle, fcntl.LOCK_UN)
    handle.close()


def _engine_hash():
    # Releases are immutable; a worker restart creates a new engine fingerprint.
    app = current_app._get_current_object()
    with _init_lock:
        if 'preview_engine_hash' not in app.extensions:
            root = Path(__file__).parent
            digest = hashlib.sha256()
            for path in sorted(root.rglob('*.py')):
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
            from .document_module import MANIFEST
            digest.update(Path(MANIFEST).read_bytes())
            digest.update(str(app.config.get('DOCUMENT_TEMPLATE_ENGINE', '')).encode())
            for name in ('WPS_RENDERER_REVISION', 'WPS_SERVICE_URL', 'WPS_CONVERT_CMD'):
                digest.update(os.environ.get(name, '').encode())
            app.extensions['preview_engine_hash'] = digest.hexdigest()
        return app.extensions['preview_engine_hash']


def source_key(report):
    from .report_preview_revision import source_hash
    return source_hash(report, _engine_hash(), source_snapshot)


def _locked(report):
    from .report_preview_revision import frozen_original
    from .functions.esign_stages import current_flow
    return bool(current_flow(report)) or frozen_original(report) or report.status in {'待审核', '待批准'}


def _state(path):
    try:
        value = json.loads((path / 'state.json').read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return {'status': 'missing', 'message': '尚未生成预览'}
    if value['status'] in ('queued', 'running'):
        claim = _claim(path)
        if claim is not None:
            try:
                value = _write(path, 'failed', message='预览任务已中断，请重试')
            finally:
                _release(claim)
    if value['status'] == 'ready':
        # Polling reads metadata only; byte integrity is checked when serving.
        if not (path / 'preview.pdf').is_file():
            return {'status': 'failed', 'message': '预览缓存缺失或损坏，请重试'}
    return value


def status(report):
    from .functions.esign_stages import current_flow
    if report.status in {'待审核', '待批准'} or current_flow(report):
        from .blueprints.report_assurance import resolve_artifact
        artifact = resolve_artifact(report, metadata_only=True, original=True)
        return dict(status='ready', sourceHash='official-' + str(artifact['versionId']),
                    pdfHash=artifact['sha256'], versionId=artifact['versionId'],
                    notices=artifact['preview']['notices'])
    key = source_key(report)
    return dict(_state(_entry(report.report_no, key)), sourceHash=key)


def cached_pdf(report):
    from .functions.esign_stages import current_flow
    if report.status in {'待审核', '待批准'} or current_flow(report):
        from .blueprints.report_assurance import resolve_artifact
        artifact = resolve_artifact(report, original=True)
        return artifact['raw'], dict(status='ready', sourceHash='official-' + str(artifact['versionId']),
                                     pdfHash=artifact['sha256'], versionId=artifact['versionId'])
    result = status(report)
    if result['status'] != 'ready':
        return None, result
    try:
        raw = (_entry(report.report_no, result['sourceHash']) / 'preview.pdf').read_bytes()
    except FileNotFoundError:
        return None, dict(result, status='failed', message='预览缓存缺失，请重试')
    if hashlib.sha256(raw).hexdigest() != result['pdfHash']:
        _write(_entry(report.report_no, result['sourceHash']), 'failed', message='预览缓存校验失败，请重试')
        return None, dict(result, status='failed', message='预览缓存校验失败，请重试')
    return raw, result


def _execute(app, report_no, key, path, claim):
    try:
        with app.app_context():
            # Read-only generation must not hold a SQLite read transaction
            # throughout a slow WPS conversion. Fresh before/after hashes
            # reject mixed or changed input; never commit business state here.
            db.session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
            report = Report.query.filter_by(report_no=report_no).first()
            if report is None or _locked(report) or source_key(report) != key:
                _write(path, 'stale', message='报告内容已变化，旧任务已取消')
                return
            _write(path, 'running', message='正在转换并合并报告')
            from .preview_timing import Trace
            trace = Trace('complete-report')
            with trace.stage('build'):
                raw, warnings = build_complete_report_pdf(report)
            from .report_generation_notices import split_generation_warnings
            blocking, notices = split_generation_warnings(warnings)
            if blocking:
                raise ValueError('；'.join(blocking))
            if not raw or not raw.startswith(b'%PDF-'):
                raise ValueError('转换未返回有效 PDF')
            db.session.remove()
            db.session.connection(execution_options={'isolation_level': 'AUTOCOMMIT'})
            report = Report.query.filter_by(report_no=report_no).first()
            if report is None or _locked(report) or source_key(report) != key:
                _write(path, 'stale', message='报告内容已变化，请生成当前版本')
                return
            _atomic(path / 'preview.pdf', raw)
            _write(path, 'ready', message='预览已生成', notices=notices, pdfHash=hashlib.sha256(raw).hexdigest())
            db.session.remove()
    except Exception as exc:
        app.logger.exception('preview background conversion failed')
        message = str(exc)[:240] if isinstance(exc, ValueError) else '报告转换失败，请核对文件及必填内容后重试'
        _write(path, 'failed', message=message)
    finally:
        with app.app_context():
            db.session.remove()
        _release(claim)


def _enqueue(app, task, *, lane='default'):
    # Two bounded lanes: uploaded reports must not queue behind unrelated
    # template rendering or sample warmup. WPS cache misses remain serialized.
    queue_key = 'uploaded_preview_tasks' if lane == 'uploaded' else 'preview_tasks'
    with _init_lock:
        tasks = app.extensions.get(queue_key)
        if tasks is None:
            tasks = queue.Queue(maxsize=32)
            app.extensions[queue_key] = tasks

            def run():
                while True:
                    queued_at, args = tasks.get()
                    app.logger.info('preview_worker_queue elapsed_ms=%.1f',
                                    (time.monotonic() - queued_at) * 1000)
                    try:
                        if callable(args[0]):
                            args[0](app, *args[1:])
                        else:
                            _execute(app, *args)
                    except Exception:
                        app.logger.exception('preview worker failed')
                    finally:
                        tasks.task_done()

            threading.Thread(target=run, name='report-preview-' + lane, daemon=True).start()
        tasks.put_nowait((time.monotonic(), task))


def prepare(report, retry=False):
    from .functions.esign_stages import current_flow
    if report.status in {'待审核', '待批准'} or current_flow(report):
        return status(report)
    if _locked(report):
        return {'status': 'failed', 'message': '该报告已批准，请读取已批准或已签署的正式版本'}
    key = source_key(report)
    path = _entry(report.report_no, key)
    value = _state(path)
    if value['status'] in ('ready', 'queued', 'running') or (value['status'] == 'failed' and not retry):
        return dict(value, sourceHash=key)
    claim = _claim(path)
    if claim is None:
        return dict(_state(path), sourceHash=key)
    try:
        # Recheck after acquiring the cross-worker lock (another request may
        # have finished between the first state read and lock acquisition).
        try:
            latest = json.loads((path / 'state.json').read_text(encoding='utf-8'))
        except (FileNotFoundError, ValueError):
            latest = {}
        if latest.get('status') == 'ready' and value['status'] != 'failed':
            _release(claim)
            return dict(latest, sourceHash=key)
        value = _write(path, 'queued', message='报告已上传，正在排队生成预览')
        from .report_documents import composition_options
        task = (report.report_no, key, path, claim)
        if composition_options(report).get('preserveUploadedReport') is True:
            _enqueue(current_app._get_current_object(), task, lane='uploaded')
        else:
            _enqueue(current_app._get_current_object(), task)
    except Exception:
        _release(claim)
        value = _write(path, 'failed', message='预览队列暂不可用，请重试')
    return dict(value, sourceHash=key)


def schedule_after_save(report):
    """A cache failure must never turn a committed upload into a failed upload."""
    try:
        from .report_documents import attachment_role, attachment_is_active, composition_options
        from .models import ReportAttachment
        rows = ReportAttachment.query.filter_by(report_no=report.report_no, deleted_at=None).all()
        if composition_options(report).get('noSupplementBody') or any(
            attachment_is_active(row) and attachment_role(row) in ('completed_report', 'report_page') for row in rows
        ):
            return prepare(report)
    except Exception:
        current_app.logger.exception('preview scheduling after save failed')
    return None
