"""Module upgrades rebuild final previews without reconverting unchanged Word."""
import json
from pathlib import Path

from flask import Flask
import pytest


@pytest.fixture
def environment(tmp_path, monkeypatch):
    from app import preview_fingerprint as fp, preview_cache, document_module
    root = tmp_path / 'code'
    root.mkdir()
    names = set(fp._CODE) | {'wps_pdf_cache.py', 'docx_formula_validation.py'}
    for name in names:
        (root / name).write_text(name)
    ole = root / '_vendor_olefile'
    ole.mkdir()
    (ole / '__init__.py').write_text('ole')
    runtime = root / 'wps_server.py'
    runtime.write_text('renderer')
    manifest = root / 'manifest.json'
    manifest.write_text(json.dumps({'files': {'pdf_helper.py': 'old'}}))
    monkeypatch.setattr(fp, '_ROOT', root)
    monkeypatch.setattr(fp, '_RUNTIME', (str(runtime),))
    monkeypatch.setattr(document_module, 'MANIFEST', manifest)
    monkeypatch.setattr(preview_cache, 'verified_package_signature', lambda: None)
    for name in fp._ENV:
        monkeypatch.delenv(name, raising=False)
    app = Flask(__name__)
    app.config['STORAGE_ROOT'] = str(tmp_path / 'storage')
    return app, root, manifest


def test_module_update_reuses_conversion_but_invalidates_final_form(environment, monkeypatch):
    from app import wps_pdf_cache as wc, preview_fingerprint as fp
    from app.entrust_preview_cache import docx_key
    from test_persistent_document_cache import word
    app, root, manifest = environment
    calls = []
    def converter():
        calls.append(1)
        return b'%PDF-test-conversion'
    with app.app_context():
        raw = word()
        old_final_key = docx_key(raw, 'engineering')
        first = wc.convert_once(raw, '.docx', converter)
        manifest.write_text(json.dumps({'files': {'pdf_helper.py': 'new'}}))
        assert docx_key(raw, 'engineering') != old_final_key
        assert wc.convert_once(raw, '.docx', converter) == first
        assert len(calls) == 1
        (root / 'docx_formula_validation.py').write_text('updated formula handling')
        wc.convert_once(raw, '.docx', converter)
        assert len(calls) == 2
        wc.convert_once(word('changed report'), '.docx', converter)
        assert len(calls) == 3


@pytest.mark.parametrize('dependency', ['docx_pdf.py', 'docx_linked_pictures.py',
    'docx_formula_validation.py', '_vendor_olefile/__init__.py', 'wps_server.py'])
def test_conversion_dependencies_still_invalidate(environment, dependency):
    from app.preview_fingerprint import office_conversion_hash
    app, root, _ = environment
    with app.app_context():
        before = office_conversion_hash()
        (root / dependency).write_text('changed')
        assert office_conversion_hash() != before


def test_runtime_revision_and_installed_library_still_invalidate(environment, monkeypatch):
    from app import preview_fingerprint as fp
    app, _, _ = environment
    with app.app_context():
        before = fp.office_conversion_hash()
        monkeypatch.setenv('WPS_RENDERER_REVISION', 'new-fonts')
        revised = fp.office_conversion_hash()
        assert revised != before
        monkeypatch.setattr(fp, 'version', lambda name: 'changed-library')
        assert fp.office_conversion_hash() != revised


def test_cache_hit_still_rejects_invalid_vendor(environment, monkeypatch):
    from app import preview_cache, wps_pdf_cache as wc
    app, _, _ = environment
    with app.app_context():
        wc.convert_once(b'word', '.doc', lambda: b'%PDF-test')
        def reject():
            raise ValueError('vendor integrity failed')
        monkeypatch.setattr(preview_cache, 'verified_package_signature', reject)
        with pytest.raises(ValueError, match='integrity'):
            wc.convert_once(b'word', '.doc', lambda: pytest.fail('must not convert'))
