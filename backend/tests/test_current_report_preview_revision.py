"""Returned reports must never preview a prior approval as current content."""
import hashlib
from unittest.mock import Mock
import pytest
from app.extensions import db
from app.models import Report, ReportAttachment, ReportDocumentContent, ReportDocumentVersion
from test_preserved_approval_and_seal_confirmation import prepared
from testkit.factories import login_headers

pytest_plugins = ('testkit.fixtures',)


@pytest.mark.parametrize('status', ['检测录入中', '委托更改中', '检测更改中', '待审核', '待批准'])
def test_return_keeps_history_but_never_selects_old_approval(prepared, status):
    from app.blueprints.report_assurance import resolve_artifact
    report, old, _, _ = prepared
    raw = b'%PDF-new unsigned'
    new = ReportDocumentVersion(report_no=report.report_no, version_no=2,
        profile_code='TEST', source_hash='new', sha256=hashlib.sha256(raw).hexdigest(), pdf_data=raw)
    db.session.add(new); db.session.flush()
    report.current_document_version_id = new.id
    report.status = status
    db.session.commit()
    assert resolve_artifact(report, original=True)['raw'] == raw
    assert report.approved_document_version_id == old.id


def test_signed_stage_keeps_approved_original(prepared):
    from app.blueprints.report_assurance import resolve_artifact
    report, old, _, raw = prepared
    assert resolve_artifact(report, original=True)['raw'] == raw


def test_frozen_original_metadata_preserves_truncation_notice(prepared):
    from app.blueprints.report_assurance import resolve_artifact
    from app.report_generation_notices import LOCATION_TRUNCATED, TemplateFieldNotice
    report, version, _, _ = prepared
    template_notice = str(TemplateFieldNotice(['Conclusion']))
    version.warnings = [LOCATION_TRUNCATED, template_notice, 'other version information']
    db.session.commit()
    assert resolve_artifact(report, metadata_only=True, original=True)['preview']['notices'] == [LOCATION_TRUNCATED, template_notice]


def test_revision_cache_hits_avoid_snapshot_and_changes_invalidate(isolated_app, monkeypatch):
    from app import preview_cache as cache
    with isolated_app.app_context():
        report = Report(report_no='QA-REV', status='检测录入中', detail={'field': 'before'})
        db.session.add(report); db.session.commit()
        snapshot = Mock(side_effect=lambda r: {'detail': r.detail,
            'content': [c.remarks for c in ReportDocumentContent.query.all()],
            'attachments': [(a.id, a.status, bool(a.deleted_at), str(a.uploaded_at)) for a in ReportAttachment.query.all()]})
        monkeypatch.setattr(cache, 'source_snapshot', snapshot)
        first = cache.source_key(report)
        for _ in range(10): assert cache.source_key(report) == first
        assert snapshot.call_count == 1
        report.detail = {'field': 'after'}; db.session.commit()
        second = cache.source_key(report)
        assert second != first
        content = ReportDocumentContent(report_no=report.report_no, remarks='new body')
        db.session.add(content); db.session.commit()
        third = cache.source_key(report)
        assert third != second
        content.remarks = 'revised body'; db.session.commit()
        fourth = cache.source_key(report)
        assert fourth != third
        att = ReportAttachment(report_no=report.report_no, name='body.pdf', source='完整报告正文', status='已上传', data=b'large-binary')
        db.session.add(att); db.session.commit()
        fifth = cache.source_key(report)
        assert fifth != fourth
        att.status = '已替代'; db.session.commit()
        sixth = cache.source_key(report)
        assert sixth != fifth
        assert snapshot.call_count == 6
        att.data = b'replaced legacy binary'; db.session.commit()
        seventh = cache.source_key(report)
        assert seventh != sixth
        from datetime import datetime
        att.deleted_at = datetime.utcnow(); db.session.commit()
        assert cache.source_key(report) != seventh
        import time
        started = time.perf_counter()
        for _ in range(50): cache.source_key(report)
        print(f' revision_hit_mean_ms={(time.perf_counter()-started)*1000/50:.3f}')
        assert snapshot.call_count == 8


def test_query_preview_uses_latest_cache_not_old_approval(prepared, isolated_client, monkeypatch):
    from app import preview_cache as cache
    report, old, user, original = prepared
    user.role_key = 'admin'; report.status = '检测录入中'; db.session.commit()
    raw = b'%PDF-current fields and upload'
    monkeypatch.setattr(cache, 'status', lambda r: {'status': 'ready', 'sourceHash': 'revision-2'})
    monkeypatch.setattr(cache, 'cached_pdf', lambda r: (raw, {'status': 'ready'}))
    headers = login_headers(isolated_client, user.account)
    url = f'/api/report-assurance/reports/{report.report_no}/artifact?view=query&original=1'
    metadata = isolated_client.get(url, headers=headers).get_json()
    assert metadata['data']['kind'] == 'preview', metadata
    for download in (0, 1):
        response = isolated_client.get(url + f'&file=1&download={download}', headers=headers)
        assert response.data == raw
    assert report.approved_document_version_id == old.id
    assert old.pdf_data == original
    monkeypatch.setattr(cache, 'cached_pdf', lambda r: (None, {'status': 'missing', 'sourceHash': 'revision-3'}))
    response = isolated_client.get(url + '&file=1', headers=headers)
    assert response.status_code == 202
    assert response.get_json()['data']['sourceHash'] == 'revision-3'
    monkeypatch.setattr(cache, 'prepare', lambda r, retry=False: {'status': 'queued', 'sourceHash': 'revision-3'})
    response = isolated_client.post(url + '&file=1', json={}, headers=headers)
    assert response.get_json()['data']['status'] == 'queued'


def test_polling_does_not_read_pdf_but_delivery_checks_integrity(isolated_app, monkeypatch):
    from pathlib import Path
    from app import preview_cache as cache
    with isolated_app.app_context():
        report = Report(report_no='QA-INTEGRITY', status='检测录入中', detail={})
        db.session.add(report); db.session.commit()
        monkeypatch.setattr(cache, 'source_snapshot', lambda r: {})
        key = cache.source_key(report); path = cache._entry(report.report_no, key)
        (path / 'preview.pdf').write_bytes(b'%PDF-broken')
        cache._write(path, 'ready', pdfHash=hashlib.sha256(b'%PDF-valid').hexdigest())
        read = Path.read_bytes
        monkeypatch.setattr(Path, 'read_bytes', lambda p: pytest.fail('poll must not read PDF') if p.name == 'preview.pdf' else read(p))
        assert cache.status(report)['status'] == 'ready'
        monkeypatch.setattr(Path, 'read_bytes', read)
        raw, state = cache.cached_pdf(report)
        assert raw is None and state['status'] == 'failed'
        assert cache.status(report)['status'] == 'failed'


def test_preview_prepare_denied_without_preview_permission(prepared, isolated_client, monkeypatch):
    from app.blueprints import report_assurance as api
    from app import preview_cache as cache
    report, _, user, _ = prepared
    user.role_key = 'admin'; report.status = '检测录入中'; db.session.commit()
    headers = login_headers(isolated_client, user.account)
    monkeypatch.setattr(api, 'allowed', lambda _: False)
    prepare = Mock(side_effect=AssertionError('must not enqueue'))
    monkeypatch.setattr(cache, 'prepare', prepare)
    response = isolated_client.post(f'/api/report-assurance/reports/{report.report_no}/artifact?view=query', json={}, headers=headers)
    assert response.status_code == 403
    prepare.assert_not_called()


@pytest.mark.parametrize('stage', ['待校核', '待审核', '待批准'])
def test_approval_preview_reads_current_official_without_render(prepared, isolated_client, stage):
    report, old, user, original = prepared
    user.role_key = 'admin'
    raw = b'%PDF-confirmed current version'
    version = ReportDocumentVersion(report_no=report.report_no, version_no=2,
        profile_code='TEST', source_hash='confirmed', sha256=hashlib.sha256(raw).hexdigest(), pdf_data=raw)
    db.session.add(version); db.session.flush()
    report.current_document_version_id = version.id
    report.status = stage
    db.session.commit()
    headers = login_headers(isolated_client, user.account)
    url = f'/api/report-assurance/reports/{report.report_no}/artifact?view=query&original=1'
    metadata = isolated_client.get(url, headers=headers).get_json()['data']
    assert metadata['kind'] == 'controlled' and metadata['versionId'] == version.id
    for download in (0, 1):
        response = isolated_client.get(url + f'&file=1&download={download}', headers=headers)
        assert response.data == raw
    assert isolated_client.post(url, json={}, headers=headers).status_code == 409
    assert report.approved_document_version_id == old.id and old.pdf_data == original
    if stage == '待校核':
        return
    from app import preview_cache
    assert preview_cache.prepare(report)['versionId'] == version.id
    assert preview_cache.cached_pdf(report)[0] == raw
    assert preview_cache._locked(report)
    version.pdf_data = b'corrupt'
    db.session.commit()
    with pytest.raises(ValueError, match='完整性'):
        preview_cache.cached_pdf(report)
