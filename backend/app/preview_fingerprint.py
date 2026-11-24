"""Fingerprint the DOCX->PDF stage, not unrelated HTTP/business source files.

DOCX contents already carry all upstream field rendering inputs. Only conversion,
background composition, validation and their assets belong to this fingerprint.
No existing cache entry is relabelled or trusted under the new key.
"""
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import threading

from flask import current_app

_LOCK = threading.Lock()
_ROOT = Path(__file__).parent
_CODE = ('preview_fingerprint.py', 'entrust_preview_cache.py', 'preview_cache.py',
         'docx_pdf.py', 'docx_linked_pictures.py', 'document_module.py', 'document_module_worker.py',
         'docparser_field_worker.py', 'entrust_render.py', 'report_generation_notices.py')
_RUNTIME = ('/opt/lims/wps_server.py', '/opt/lims/wps_convert_once.py')
_ENV = ('WPS_SERVICE_URL', 'WPS_CONVERT_CMD', 'WPS_BIN', 'WPS_RENDERER_REVISION',
        'PDF_PAGE_NUMBER_SIMSUN_FONT_PATH', 'PDF_PAGE_NUMBER_TIMES_FONT_PATH',
        'SOFFICE_BIN', 'LANG', 'LC_ALL', 'TZ')


def office_conversion_hash():
    """Only dependencies of Word conversion; final PDFs keep conversion_hash.

    Vendor integrity remains mandatory, but changing pagination/backgrounds
    must not force an unchanged uploaded Word through WPS again.
    """
    from . import preview_cache as cache
    cache.verified_package_signature()
    names = ('preview_fingerprint.py', 'wps_pdf_cache.py', 'docx_pdf.py',
             'docx_linked_pictures.py', 'docx_formula_validation.py')
    files = {name: hashlib.sha256((_ROOT / name).read_bytes()).hexdigest()
             for name in names}
    for path in sorted((_ROOT / '_vendor_olefile').rglob('*.py')):
        files[path.relative_to(_ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in _RUNTIME:
        path = Path(name)
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    settings = {name: os.environ.get(name, '') for name in
                ('WPS_SERVICE_URL', 'WPS_CONVERT_CMD', 'WPS_BIN',
                 'WPS_RENDERER_REVISION', 'SOFFICE_BIN', 'LANG', 'LC_ALL', 'TZ')}
    for name in ('WPS_BIN', 'SOFFICE_BIN'):
        path = Path(settings[name]) if settings[name] else None
        files['configured-' + name] = (hashlib.sha256(path.read_bytes()).hexdigest()
                                      if path and path.is_file() else None)
    packages = {}
    for name in ('PyMuPDF', 'pypdf', 'Pillow', 'lxml'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    raw = json.dumps({'schema': 'office-only-v1', 'files': files,
                      'settings': settings, 'packages': packages},
                     sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


def conversion_hash():
    from . import preview_cache as cache
    from .document_module import MANIFEST
    # This is still an integrity gate on every call, including cache hits.
    cache.verified_package_signature()
    app = current_app._get_current_object()
    paths = [(name, _ROOT / name) for name in _CODE]
    paths += [('manifest', Path(MANIFEST))]
    paths += [('runtime-' + str(i), Path(name)) for i, name in enumerate(_RUNTIME)]
    settings = {name: os.environ.get(name, '') for name in _ENV}
    for name in ('PDF_PAGE_NUMBER_SIMSUN_FONT_PATH', 'PDF_PAGE_NUMBER_TIMES_FONT_PATH', 'WPS_BIN', 'SOFFICE_BIN'):
        if settings[name]:
            paths.append(('configured-' + name, Path(settings[name])))
    # These adapters are small. Hash contents rather than trusting stat equality:
    # rapid same-length rewrites can have identical filesystem timestamps.
    files = {}
    for label, path in paths:
        if label == 'manifest':
            files[label] = json.loads(path.read_text(encoding='utf-8'))['files']
        elif path.is_file():
            files[label] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif label.startswith(('runtime-', 'configured-')):
            files[label] = None
        else:
            raise ValueError('预览转换依赖缺失，请联系管理员')
    with _LOCK:
        # Dependency installations are immutable until process restart.
        packages = app.extensions.get('entrust_conversion_libraries_v2')
        if packages is None:
            packages = {}
            for name in ('PyMuPDF', 'pypdf', 'reportlab', 'Pillow', 'lxml'):
                try:
                    packages[name] = version(name)
                except PackageNotFoundError:
                    packages[name] = None
            app.extensions['entrust_conversion_libraries_v2'] = packages
    raw = json.dumps({'schema': 2, 'files': files, 'settings': settings,
                      'packages': packages}, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()
