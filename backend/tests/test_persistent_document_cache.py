"""Disk reuse at real print boundaries; converters never call external services."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from time import perf_counter
from zipfile import ZipFile, ZipInfo

from flask import Flask
import pytest

pytest_plugins = ('testkit.fixtures',)


def word(text='unchanged', year=2026):
    out = BytesIO()
    with ZipFile(out, 'w') as archive:
        entry = ZipInfo('word/document.xml', (year, 1, 1, 0, 0, 0))
        archive.writestr(entry, text)
    return out.getvalue()


def pdf(label=''):
    import fitz
    with fitz.open() as doc:
        doc.new_page().insert_text((30, 30), label)
        return doc.tobytes()


@pytest.fixture
def cache_app(tmp_path):
    app = Flask(__name__)
    app.config.update(STORAGE_ROOT=str(tmp_path), JWT_SECRET='test-cache-only-secret')
    return app


@pytest.fixture
def conversions(monkeypatch):
    from app import docx_pdf, document_module, entrust_render
    calls = {'convert': 0, 'background': 0}
    def convert(raw):
        calls['convert'] += 1
        return pdf(str(calls['convert']))
    def background(raw):
        calls['background'] += 1
        return raw
    monkeypatch.setattr(docx_pdf, 'docx_to_pdf_wps', convert)
    monkeypatch.setattr(document_module, 'entrust_background', background)
    monkeypatch.setattr(entrust_render, 'require_business_form_page_count', lambda *_: 1)
    return calls


def test_all_variants_survive_switching_restart_and_changed_source(cache_app, conversions):
    from app.entrust_preview_cache import render_pdf, ensure
    variants = ['product', 'engineering', 'product-extended', 'engineering-extended']
    with cache_app.app_context():
        first = {kind: render_pdf(word(), kind)[0] for kind in variants}
        for kind in reversed(variants):
            assert render_pdf(word(year=2025), kind)[0] == first[kind]
            assert ensure(word(), kind)[0]['status'] == 'ready'
    # A fresh Flask app has no in-memory state; only STORAGE_ROOT is reused.
    restarted = Flask('restarted')
    restarted.config.update(cache_app.config)
    with restarted.app_context():
        assert render_pdf(word(), 'product')[0] == first['product']
        assert conversions == {'convert': 4, 'background': 4}
        assert render_pdf(word('edited amount/signature'), 'product')[0] != first['product']
        assert conversions == {'convert': 5, 'background': 5}


def test_concurrent_sync_and_async_share_one_final_file(cache_app, conversions, monkeypatch):
    from app import preview_cache as cache
    from app.entrust_preview_cache import render_pdf, ensure
    queued = []
    monkeypatch.setattr(cache, '_enqueue', lambda app, task: queued.append((app, task)))
    with cache_app.app_context():
        state, key = ensure(word(), 'product')
        assert state['status'] == 'queued'
        assert ensure(word(), 'product')[0]['status'] == 'queued'
    assert len(queued) == 1
    app, (execute, *args) = queued[0]
    def read():
        with app.app_context():
            return render_pdf(word(), 'product')[0]
    with ThreadPoolExecutor(max_workers=3) as pool:
        readers = [pool.submit(read) for _ in range(2)]
        execute(app, *args)
        assert readers[0].result() == readers[1].result()
    assert conversions == {'convert': 1, 'background': 1}


def test_corruption_failure_and_changed_renderer_do_not_reuse(cache_app, conversions, monkeypatch):
    from app import preview_cache as cache, preview_fingerprint, docx_pdf
    from app.entrust_preview_cache import render_pdf, docx_key, ensure
    with cache_app.app_context():
        raw = word()
        render_pdf(raw, 'product')
        path = cache._entry('entrust', docx_key(raw, 'product'))
        (path / 'preview.pdf').write_bytes(b'broken')
        render_pdf(raw, 'product')
        assert conversions['convert'] == 2
        monkeypatch.setattr(preview_fingerprint, 'conversion_hash', lambda: 'new-renderer')
        render_pdf(raw, 'product')
        assert conversions['convert'] == 3
        monkeypatch.setattr(docx_pdf, 'docx_to_pdf_wps', lambda _: None)
        with pytest.raises(ValueError, match='转换不可用'):
            render_pdf(word('failed'), 'product')
        failed = cache._entry('entrust', docx_key(word('failed'), 'product'))
        assert not (failed / 'preview.pdf').exists()


def test_generic_report_conversion_is_persistent_and_separate_from_strict(cache_app, monkeypatch):
    from app import docx_pdf
    calls = []
    def convert(raw, suffix, converters):
        calls.append(converters)
        return pdf(str(len(calls)))
    monkeypatch.setattr(docx_pdf, '_office_to_pdf_with', convert)
    with cache_app.app_context():
        generic = docx_pdf.office_to_pdf(word())
        assert docx_pdf.office_to_pdf(word(year=2025)) == generic
        strict = docx_pdf.office_to_pdf_wps(word())
        assert strict != generic
        assert docx_pdf.office_to_pdf_wps(word()) == strict
        assert len(calls) == 2
        assert docx_pdf.office_to_pdf(word('changed')) != generic
        assert len(calls) == 3


def test_report_conversion_retries_failed_or_corrupt_results(cache_app, monkeypatch):
    from app import docx_pdf
    calls = []
    def convert(*_):
        calls.append(1)
        return None if len(calls) == 1 else pdf(str(len(calls)))
    monkeypatch.setattr(docx_pdf, '_office_to_pdf_with', convert)
    with cache_app.app_context():
        assert docx_pdf.office_to_pdf(word()) is None
        good = docx_pdf.office_to_pdf(word())
        assert good.startswith(b'%PDF-')
        from pathlib import Path
        for path in Path(cache_app.config['STORAGE_ROOT']).rglob('result.pdf'):
            path.write_bytes(b'%PDF-corrupted')
        assert docx_pdf.office_to_pdf(word()) != good
        assert len(calls) == 3


def test_complete_report_reuses_final_pdf_and_rejects_changed_content(isolated_app, monkeypatch):
    from app import preview_cache as cache
    from app.extensions import db
    from app.models import Report
    builds = []
    def build(report):
        builds.append(report.detail)
        return pdf(str(len(builds))), []
    monkeypatch.setattr(cache, 'source_snapshot', lambda r: {'detail': r.detail})
    monkeypatch.setattr(cache, 'build_complete_report_pdf', build)
    monkeypatch.setattr(cache, '_enqueue', lambda app, task: cache._execute(app, *task))
    with isolated_app.app_context():
        report = Report(report_no='CACHE-FULL', sample_no='CACHE-FULL-S', detail={'content': 'old'})
        db.session.add(report); db.session.commit()
        cache.prepare(report)
        report = Report.query.filter_by(report_no='CACHE-FULL').one()
        first, state = cache.cached_pdf(report)
        assert state['status'] == 'ready'
        cache.prepare(report)
        assert cache.cached_pdf(report)[0] == first and len(builds) == 1
        report.detail = {'content': 'new'}; db.session.commit()
        assert cache.cached_pdf(report)[0] is None
        cache.prepare(report)
        report = Report.query.filter_by(report_no='CACHE-FULL').one()
        assert cache.cached_pdf(report)[0] != first and len(builds) == 2


def test_real_source_renderer_reuses_word_and_invalidates_fields_and_review(isolated_app, monkeypatch):
    from app import docparser_field_only as fields
    from app.entrust_source_cache import render
    from test_entrust_output_release import objects
    calls = []
    original = fields.render_entrust
    def observed(*args):
        calls.append(args[2])
        return original(*args)
    monkeypatch.setattr(fields, 'render_entrust', observed)
    monkeypatch.setattr(fields, 'institution_profile_for', lambda _: {'centerName': '虚拟机构'})
    with isolated_app.app_context():
        e, r = objects()
        r.report_no = 'LAB-TEST-R'
        original_detail = deepcopy(r.detail)
        timings = []
        results = []
        for kind in ('product', 'engineering', 'product'):
            started = perf_counter()
            results.append(render(e, r, kind))
            timings.append(round((perf_counter() - started) * 1000))
        assert results[0] == results[2]
        assert calls == ['product', 'engineering']
        assert r.detail == original_detail
        r.detail['rawSample']['stdPrice'] = '99.01'
        assert render(e, r, 'product')[0] != results[0][0]
        r.detail['contractReview']['result'] = '退回'
        assert render(e, r, 'product')[0] != results[0][0]
        assert len(calls) == 4
        # An unreviewed form and an all-unchecked completed review must never
        # share a source cache entry, even without any signature image.
        r.sample_no = 'CACHE-EMPTY-REVIEW'
        r.detail.pop('contractReview')
        pending = render(e, r, 'product')[0]
        assert render(e, r, 'product')[0] == pending
        r.detail['contractReview'] = {'result': '通过', 'signatureSource': 'account-image-v1', 'signature': ''}
        reviewed = render(e, r, 'product')[0]
        assert reviewed != pending
        assert render(e, r, 'product')[0] == reviewed
        assert len(calls) == 6
        print('real DOCX product/engineering/product timings_ms:', timings)


@pytest.mark.parametrize('permission', ['entrust.query.view', 'entrust.contract_review.view'])
def test_print_routes_share_disk_and_recheck_permission(isolated_app, scenario_factory, monkeypatch, conversions, permission):
    from app import docparser_field_only as fields, entrust_render, preview_cache
    from app.extensions import db
    from app.models import Entrust, Report
    from app.security import issue_token
    from app.blueprints import samples
    with isolated_app.app_context():
        dept = scenario_factory.department()
        user = scenario_factory.user(dept, permissions=[permission])
        parent = Entrust(entrust_no='CACHE-WT', contract_no='', department=dept.name, owner=user.name, info={})
        report = Report(report_no='CACHE-R', sample_no='CACHE-S', entrust_no=parent.entrust_no,
                        department=dept.name, owner=user.name, detail={})
        db.session.add_all([parent, report]); db.session.commit()
        headers = {'Authorization': 'Bearer ' + issue_token(user)}
        monkeypatch.setattr(fields, 'applies_to_entrust', lambda _: False)
        monkeypatch.setattr(entrust_render, 'build_entrust_doc', lambda e, r, kind, *_: word(kind + str(r.detail)))
        monkeypatch.setattr(samples, '_business_form_page_count', lambda *_: 1)
        # Run queued tasks synchronously with real locks and disk; no WPS/HTTP.
        monkeypatch.setattr(preview_cache, '_enqueue', lambda app, task: task[0](app, *task[1:]))
        client = isolated_app.test_client()
        sample_url = '/api/samples/CACHE-R/print?templateKind=product&asyncPreview=1'
        parent_url = f'/api/entrust/{parent.id}/print?templateKind=product'
        response = client.get(parent_url, headers=headers)
        assert response.mimetype == 'application/pdf', response.json
        first = response.data
        assert client.get(sample_url, headers=headers).data == first
        assert conversions == {'convert': 1, 'background': 1}
        etag = client.get(sample_url, headers=headers).headers['ETag']
        conditional = {**headers, 'If-None-Match': etag}
        assert client.get(sample_url, headers=conditional).status_code == 304
        assert client.get(parent_url, headers=conditional).status_code == 304
        report.detail = {'rawSample': {'stdPrice': '0.01'}}
        db.session.commit()
        changed = client.get(parent_url, headers=conditional)
        assert changed.status_code == 200 and changed.data != first
        assert conversions['convert'] == 2
        report.department = '其他部门'; report.owner = '其他用户'; db.session.commit()
        denied = client.get(sample_url, headers=conditional)
        assert denied.status_code != 304 and denied.mimetype == 'application/json'
        assert denied.json['code'] != 0
