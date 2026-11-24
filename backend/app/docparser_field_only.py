"""Original-package field replacement; never compose/rewrite report body."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from io import BytesIO
import json
import os
import re
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import subprocess
import sys
from datetime import datetime, timezone
from zipfile import BadZipFile, ZipFile

from lxml import etree

from flask import current_app, has_app_context

# Stable deployment/configuration protocol; implementation revision is RELEASE.
# Renaming this value would reject the existing production configuration.
ENGINE = 'docparser-original-202609'
RELEASE = 'DOCPARSER-MODULE-20260907-correction-date-20261108'
ASSETS = Path(__file__).parent / 'vendor_docparser_20260911' / 'assets' / 'templates'
VENDOR = Path(__file__).parent / 'vendor_docparser_20260911'
SOURCE_MANIFEST = Path(__file__).with_name('document_module_vendor_20260911.json')
W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
REPORT_FILES = {
    'product': 'LAB-Report-Product-{language}-{variant}-202609_tpl.docx',
    'sampling': 'LAB-Report-Sampling-{language}-{variant}-202609_tpl.docx',
    'engineering': 'LAB-Report-Engineering-{language}-Standard-202609_tpl.docx',
    'inspection': 'LAB-Report-Inspection-{language}-Standard-202609_tpl.docx',
    'calibration': 'LAB-Report-Calibration-CN-Standard-202609_tpl.docx',
}
ENTRUST_FILES = {
    'product': 'LAB-Entrust-4204d-202601_tpl.docx',
    'engineering': 'LAB-Entrust-4204g-202601_tpl.docx',
}
CENTERS = {
    'LAB': '', 'NCSA': '国家空调设备质量检验检测中心',
    'NCAS': '国家空调设备质量检验检测中心',
}
CENTER_ENGLISH = {
    'LAB': '',
    'NCSA': 'National Center of Quality Inspection and Testing for Air Conditioning Equipment',
    'NCAS': 'National Center of Quality Inspection and Testing for Air Conditioning Equipment',
}
DEFAULT_DEPARTMENT_RULES = (
    {'center': 'NCSA', 'keywords': ('空调', '通风', '净化', '热湿')},
)


def number_identity(report, entrust=None):
    """Use report identity and the physical sample identity shared by derivatives."""
    from .sample_identity import sample_number
    identity = {}
    for key, attr in [('reportNo', 'report_no'), ('sampleNo', 'sample_no'), ('entrustNo', 'entrust_no')]:
        value = sample_number(report) if key == 'sampleNo' else getattr(report, attr, None)
        if (not isinstance(value, str) or not value or value != value.strip()
                or re.search(r'[\x00-\x20/\\<>:"|?*]', value)):
            raise ValueError(f'{key} 缺失或格式无效，请先保存并核对系统编号')
        identity[key] = value
    if entrust is not None:
        if not getattr(entrust, 'entrust_no', None):
            raise ValueError('关联委托缺少系统编号')
        if getattr(entrust, 'entrust_no', None) != identity['entrustNo']:
            raise ValueError('entrustNo 与关联数据不一致，拒绝生成串号报告')
    return identity


def identity_snapshot_conflicts(report):
    """List stale denormalized identity slots without trusting or persisting them.

    Report/sample/entrust columns are the saved system identities.  Older UI
    snapshots can legitimately retain a number from before a report copy or
    correction was created; those values must not replace the persisted ones,
    but they also must not make the report permanently unrenderable.
    """
    identity = number_identity(report)
    detail = getattr(report, 'detail', None) or {}
    raw = detail.get('rawSample') or {}
    snapshot = detail.get('entrustSnapshot') or {}
    checks = (
        ('rawSample.reportNo', 'reportNo', raw.get('reportNo')),
        ('rawSample.sampleNo', 'sampleNo', raw.get('sampleNo')),
        ('entrustSnapshot.entrustNo', 'entrustNo', snapshot.get('entrustNo')),
        ('entrustSnapshot.sourceEntrustNo', 'entrustNo', snapshot.get('sourceEntrustNo')),
        ('entrustSnapshot.info.entrustNo', 'entrustNo',
         (snapshot.get('info') or {}).get('entrustNo')),
    )
    return [source for source, key, candidate in checks
            if candidate not in (None, '') and candidate != identity[key]]


def _worker_environment():
    existing = os.environ.get('PYTHONPATH', '')
    python_path = str(VENDOR) + (os.pathsep + existing if existing else '')
    return {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONIOENCODING': 'utf-8', 'PYTHONPATH': python_path}


@lru_cache(maxsize=1)
def verify_original_source():
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding='utf-8'))
    expected = manifest.get('files') or {}
    if not expected:
        raise ValueError('原包源码清单为空')
    checked = []
    root = ASSETS.parent
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob('*')
        if path.is_file()
        and '__pycache__' not in path.relative_to(root).parts
        and path.suffix.lower() not in {'.pyc', '.pyo'}
    }
    if actual != set(expected):
        raise ValueError('原包文件集合与来源清单不一致')
    for relative, digest in sorted(expected.items()):
        path = root / PurePosixPath(relative)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'原包源码或模板哈希不一致：{relative}')
        checked.append({'filename': relative, 'sha256': digest})
    return {'archiveSha256': manifest['archiveSha256'], 'files': checked}


def _render_with_original(kind, filename, context, report_profile=None):
    verify_original_source()
    worker = Path(__file__).with_name('docparser_field_worker.py')
    payload = dict(context)
    if report_profile is not None:
        payload['__DocParserReportConfig'] = {
            'center': report_profile['center'],
            'category': report_profile['kind'],
            'language': report_profile['language'],
            'extended': report_profile['variant'] == 'Extended',
        }
    with TemporaryDirectory(prefix='docparser-original-') as folder:
        output = Path(folder) / 'filled.docx'
        command = [sys.executable, str(worker), kind, filename, str(output)]
        try:
            process = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8',
                cwd=ASSETS.parent, timeout=90, check=False, env=_worker_environment())
        except subprocess.TimeoutExpired as exc:
            raise ValueError('原包字段填充超时，未生成文件') from exc
        if process.returncode:
            try:
                message = json.loads(process.stdout)['error']
            except (ValueError, KeyError):
                message = '原包字段填充失败，请检查模板依赖和容量'
            raise ValueError(message)
        audit = json.loads(process.stdout)
        blob = output.read_bytes()
    if audit['sha256'] != hashlib.sha256(blob).hexdigest():
        raise ValueError('生成文件校验失败')
    blob, symbol_audit = _replace_legacy_symbol_font(blob)
    audit['makerSha256'] = audit['sha256']
    audit['sha256'] = hashlib.sha256(blob).hexdigest()
    audit['symbolCompatibility'] = symbol_audit
    audit['changedParts'] = list(dict.fromkeys(
        [*(audit.get('changedParts') or []), *symbol_audit['changedParts']]))
    return blob, audit


def _replace_legacy_symbol_font(blob):
    """Replace Wingdings 2 checkboxes in the generated copy only.

    Linux WPS substitutes an unrelated font when Wingdings 2 is unavailable,
    making F051/F052 private-use glyphs disappear.  Unicode ballot boxes in
    DejaVu Sans preserve the official template geometry and render on both WPS
    and Word.  Original sources and template binaries are never touched.
    """
    replacements = {'F051': '\u2612', 'F052': '\u2611', 'F0A3': '\u2610'}
    source = BytesIO(blob)
    target = BytesIO()
    replaced = 0
    changed_parts = []
    with ZipFile(source) as archive, ZipFile(target, 'w') as output:
        for item in archive.infolist():
            value = archive.read(item.filename)
            if item.filename.startswith('word/') and item.filename.endswith('.xml'):
                try:
                    root = etree.fromstring(value, parser=etree.XMLParser(
                        resolve_entities=False, no_network=True))
                except etree.XMLSyntaxError:
                    root = None
                changed = False
                if root is not None:
                    for symbol in root.xpath('.//w:sym', namespaces={'w': W_NS}):
                        font = symbol.get('{' + W_NS + '}font', '')
                        code = symbol.get('{' + W_NS + '}char', '').upper()
                        if re.sub(r'\s+', '', font).lower() != 'wingdings2' or code not in replacements:
                            continue
                        run = symbol.getparent()
                        run_properties = run.find('{' + W_NS + '}rPr')
                        if run_properties is None:
                            run_properties = etree.Element('{' + W_NS + '}rPr')
                            run.insert(0, run_properties)
                        fonts = run_properties.find('{' + W_NS + '}rFonts')
                        if fonts is None:
                            fonts = etree.SubElement(run_properties, '{' + W_NS + '}rFonts')
                        for attr in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
                            fonts.set('{' + W_NS + '}' + attr, 'DejaVu Sans')
                        text_node = etree.Element('{' + W_NS + '}t')
                        text_node.text = replacements[code]
                        run.replace(symbol, text_node)
                        replaced += 1
                        changed = True
                    if changed:
                        value = etree.tostring(root, xml_declaration=True,
                                               encoding='UTF-8', standalone=True)
                        changed_parts.append(item.filename)
            output.writestr(item, value)
    return target.getvalue(), {
        'strategy': 'wingdings2-to-unicode',
        'font': 'DejaVu Sans',
        'replaced': replaced,
        'changedParts': changed_parts,
    }


def render_preview(report, *, authoring=False):
    """Return field-only DOCX plus audit. This is NOT an approved complete PDF.

    The original package has a body-authoring guide rather than a result-table
    placeholder. Preserve that guide; never silently discard supplied results.
    """
    profile, context = profile_for(report), report_context(report)
    _validate_module_report_context(context, authoring=authoring)
    from .document_module import render_report
    if authoring:
        blob, audit = render_report(profile, context, authoring=True)
    else:
        blob, audit = render_report(profile, context)
    blob, symbol_audit = _replace_legacy_symbol_font(blob)
    audit.update(makerSha256=audit['sha256'], sha256=hashlib.sha256(blob).hexdigest(),
                 symbolCompatibility=symbol_audit)
    audit['changedParts'] = list(dict.fromkeys([*audit['changedParts'], *symbol_audit['changedParts']]))
    audit.update(identity=number_identity(report),
                 legacyIdentityConflicts=identity_snapshot_conflicts(report), engine=ENGINE,
                 templateSelection=profile)
    return blob, audit


def _validate_module_report_context(context, *, authoring=False):
    from .docparser_field_worker import REPORT_RAW_CONTEXT_KEYS
    if set(context) - REPORT_RAW_CONTEXT_KEYS:
        raise ValueError('平台仅可替换 report_demo.raw_context 中定义的报告字段')
    if len(str(context.get('ReportNo') or '')) > 40:
        raise ValueError('字段 ReportNo 长度超出模板上限，拒绝截断')
    if not authoring and len(str(context.get('SampleName') or '')) > 260:
        raise ValueError('字段 SampleName 长度超出模板上限，拒绝截断')
    for key in ('Trademark', 'Conclusion'):
        value = context.get(key, '')
        if key == 'Trademark' and isinstance(value, str) and value.startswith('data:image/'):
            continue
        if isinstance(value, str) and re.search(r'\.(docx|png|jpe?g)$', value, re.I):
            raise ValueError(f'字段 {key} 不接受本地文件路径')


def require_complete_report(audit):
    if audit.get('bodyGuideRetained') or audit.get('completeReport') is not True:
        raise ValueError('原包正文说明区尚未对接实际完整正文；不得作为正式报告签发')


def scope_mark_fields(mode, evidence, company_name):
    """Use reviewed identities while retaining the original demo's text format."""
    required = {'CNAS', 'CMA'} if mode == 'cnas_cma' else {'CNAS'} if mode == 'cnas' else set()
    if not required or not evidence or {e['kind'] for e in evidence} != required:
        raise ValueError('报告标识与核查资质模式不一致')
    if {e['institution'] for e in evidence} != {company_name}:
        raise ValueError('报告机构名称与资质证据不一致')
    if {e['category'] for e in evidence} != {'检测'}:
        raise ValueError('原包检验机构标识须核对，不能自动套用检测实验室标识')
    marks = {}
    for kind in required:
        ids = {e['certificate'] for e in evidence if e['kind'] == kind}
        if len(ids) != 1:
            raise ValueError('同份报告对应多个证书编号，原模板单证书字段无法表达')
        marks[kind] = ids.pop()
    if not re.fullmatch(r'L[0-9]+', marks['CNAS']):
        raise ValueError('检测实验室 CNAS 证书编号格式不匹配')
    return marks.get('CMA', ''), '中国认可\n国际互认\n检测\nTESTING\nCNAS ' + marks['CNAS']


def config(key, default=''):
    return current_app.config.get(key, os.environ.get(key, default)) if has_app_context() else os.environ.get(key, default)


def enabled():
    engine = config('DOCUMENT_TEMPLATE_ENGINE', 'legacy')
    if engine not in ('legacy', ENGINE):
        raise ValueError(f'DOCUMENT_TEMPLATE_ENGINE must be legacy or {ENGINE}')
    return engine == ENGINE


def _applies_to_created_at(entity, label):
    """Select the new engine with a server-owned rollout cutoff.

    An empty cutoff intentionally keeps the existing all-or-nothing behavior
    for local tests. Production must set the cutoff to the immutable release
    instant so historical and already-running reports retain their old layout.
    """
    if not enabled():
        return False
    raw = str(config('DOCPARSER_ROLLOUT_STARTED_AT', '') or '').strip()
    if not raw:
        return True
    try:
        cutoff = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('DOCPARSER_ROLLOUT_STARTED_AT 必须为 ISO-8601 时间') from exc
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    created = getattr(entity, 'created_at', None)
    if created is None:
        raise ValueError(f'{label}缺少创建时间，不能判断模板版本')
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created >= cutoff


def applies_to(report):
    return _applies_to_created_at(report, '报告')


def applies_to_entrust(entrust):
    return _applies_to_created_at(entrust, '委托')


# Exact marker printed by every retained original report template.  The PDF
# compositor must use the package text verbatim; adding a synthetic prefix
# makes the guide page impossible to locate after WPS conversion.
GUIDE_MARKER = '内容编写说明'
GUIDE_UPLOAD_MARKERS = (
    GUIDE_MARKER, '请删除本说明', '如无须补充内容', '请勿修改页眉',
    '请勿在本文件中', '请务必通过系统预览', '如有其他问题',
    '请保留本页下方的分节符',
)
NOTICE_MARKER = '注意事项NOTICE'
SIGNATURE_ANCHORS = {'主检': 'ChiefTester', '审核': 'Verification', '批准': 'Approval'}
CALIBRATION_SIGNATURE_ANCHORS = {
    '校准': 'Calibratedby', '审核': 'Checkedby', '批准': 'Approvedby',
}


def _normalized(value):
    return re.sub(r'\s+', '', value or '')


def _is_calibration_signature_text(value):
    compact = _normalized(value)
    return (all(anchor in compact for anchor in CALIBRATION_SIGNATURE_ANCHORS.values())
            or all(anchor in compact for anchor in ('校准员', '审核员', '批准人')))


def validate_completed_template_source(blob, filename, report_no, *, allow_guide_pages=False, preserve_uploaded=False):
    """Reject uploads that are not a completed copy of the issued template."""
    lower = str(filename or '').lower()
    if preserve_uploaded:
        from . import document_module
        if lower.endswith('.pdf'):
            document_module.pdf_pages(blob)
        elif lower.endswith('.docx'):
            document_module.validate_docx(blob)
    if lower.endswith('.doc') and not lower.endswith('.docx'):
        raise ValueError('新报告正文不接受旧版 .doc，请下载系统 DOCX 模板填写')
    if lower.endswith('.pdf'):
        try:
            import fitz
            document = fitz.open(stream=blob, filetype='pdf')
            try:
                text_value = '\n'.join(page.get_text() for page in document)
            finally:
                document.close()
        except Exception as exc:
            raise ValueError('上传的报告 PDF 无法读取') from exc
    elif lower.endswith('.docx'):
        try:
            with ZipFile(BytesIO(blob)) as archive:
                names = archive.namelist()
                from .docx_formula_validation import validate_embedded_members
                validate_embedded_members(archive)
                rels = [name for name in names if name.endswith('.rels')]
                for name in rels:
                    relationships = etree.fromstring(
                        archive.read(name), parser=etree.XMLParser(resolve_entities=False, no_network=True))
                    for relationship in relationships:
                        if str(relationship.get('TargetMode') or '').lower() != 'external':
                            continue
                        kind = str(relationship.get('Type') or '')
                        # Hyperlinks use text already stored in the document;
                        # PDF rendering does not need to retrieve their target.
                        # Linked images/templates/OLE still depend on external IO.
                        if not kind.endswith('/hyperlink'):
                            raise ValueError('Word 文件引用了外部图片、文件或模板，请先嵌入资源后上传，以免 PDF 缺失内容')
                parts = [name for name in names if re.fullmatch(
                    r'word/(document|header[0-9]+|footer[0-9]+)\.xml', name)]
                parser = etree.XMLParser(resolve_entities=False, no_network=True)
                text_value = ''.join(''.join(etree.fromstring(archive.read(name), parser=parser).xpath(
                    './/w:t/text()', namespaces={'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                )) for name in parts)
        except BadZipFile as exc:
            raise ValueError('上传的 DOCX 文件损坏') from exc
    else:
        raise ValueError('报告正文仅支持系统模板填写后的 DOCX 或 PDF')
    compact = _normalized(text_value)
    if report_no not in compact:
        raise ValueError('上传文件中的报告编号与当前报告不一致')
    if not preserve_uploaded and NOTICE_MARKER not in compact and not _is_calibration_signature_text(compact):
        raise ValueError('上传文件不是系统发出的完整报告模板，缺少注意事项页')
    if not allow_guide_pages and any(marker in compact for marker in GUIDE_UPLOAD_MARKERS):
        raise ValueError('请先删除“补充内容编写说明”并填写正文后再上传')
    return {'reportNo': report_no, 'textLayer': bool(compact),
            'sha256': hashlib.sha256(blob).hexdigest()}


def _pdf_texts(blob):
    try:
        import fitz
        document = fitz.open(stream=blob, filetype='pdf')
        try:
            if document.page_count < 1:
                raise ValueError('报告 PDF 没有页面')
            return document, [_normalized(page.get_text()) for page in document]
        except Exception:
            document.close()
            raise
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('报告 PDF 无法读取或缺少文本层') from exc


def _unique_marker_page(texts, marker, label):
    indexes = [index for index, value in enumerate(texts) if marker in value]
    if len(indexes) != 1:
        raise ValueError(f'报告{label}页无法唯一识别')
    return indexes[0]


def _unchanged_guide_page(reference, uploaded):
    """Delete only a pure, unchanged guide; never discard mixed user content.

    Ignore text whitespace, not words. Images, vector graphics, annotations and
    widgets cannot be added to a page that will be removed. A mismatch fails
    closed and asks the author to separate guide and body pages.
    """
    if _normalized(reference.get_text()) != _normalized(uploaded.get_text()):
        return False
    if list(uploaded.annots() or []) or list(uploaded.widgets() or []):
        return False
    def images(page):
        return [(item['digest'], tuple(round(v, 2) for v in item['bbox']))
                for item in page.get_image_info(hashes=True)]
    return (images(reference) == images(uploaded)
            and reference.get_drawings() == uploaded.get_drawings()
            and reference.rect == uploaded.rect)


def compose_completed_pdf(base_pdf, completed_pdfs, report_no, *, allow_guide_pages=False):
    """Keep immutable original fixed pages and only accept uploaded body pages.

    ``base_pdf`` is the freshly rendered server template containing the guide.
    Each uploaded PDF is a completed copy of that template: its cover/home and
    notice pages are discarded, while body pages are inserted in upload order.
    """
    import fitz

    base, base_texts = _pdf_texts(base_pdf)
    try:
        guide_index = _unique_marker_page(base_texts, GUIDE_MARKER, '正文说明')
        calibration = any(_is_calibration_signature_text(value) for value in base_texts)
        base_notice_pages = [index for index, value in enumerate(base_texts)
                             if NOTICE_MARKER in value]
        if len(base_notice_pages) == 1:
            notice_index = base_notice_pages[0]
        elif not base_notice_pages and calibration:
            notice_index = len(base_texts)
        else:
            raise ValueError('报告注意事项页无法唯一识别')
        # Original variants may have either one cover page or a cover plus a
        # separate home page before the editable continuation body.
        if guide_index < 1 or notice_index <= guide_index:
            raise ValueError('原报告模板页面顺序异常')
        output = fitz.open()
        try:
            output.insert_pdf(base, from_page=0, to_page=guide_index - 1)
            body_count = 0
            # insert_pdf copies pages without changing their text. Reuse the
            # validated source text in the exact output page order.
            final_texts = list(base_texts[:guide_index])
            for raw in completed_pdfs:
                uploaded, texts = _pdf_texts(raw)
                try:
                    uploaded_notice_pages = [index for index, value in enumerate(texts)
                                             if NOTICE_MARKER in value]
                    if len(uploaded_notice_pages) == 1:
                        uploaded_notice = uploaded_notice_pages[0]
                    elif not uploaded_notice_pages and calibration:
                        uploaded_notice = len(texts)
                    else:
                        raise ValueError('报告注意事项页无法唯一识别')
                    if uploaded_notice < guide_index:
                        raise ValueError('上传报告缺少首页后的正文页')
                    body = texts[guide_index:uploaded_notice]
                    if not allow_guide_pages and (not body or any(
                            any(marker in value for marker in GUIDE_UPLOAD_MARKERS) for value in body)):
                        raise ValueError('上传报告正文仍包含编写说明或没有正文')
                    kept = []
                    for offset, value in enumerate(body, start=guide_index + 1):
                        if allow_guide_pages and any(marker in value for marker in GUIDE_UPLOAD_MARKERS):
                            if not _unchanged_guide_page(base[guide_index], uploaded[offset - 1]):
                                raise ValueError('编写说明页含有其他内容或版式变化，无法安全自动删除；请将补充正文移至独立页，或手工删除说明文字后上传')
                            continue
                        if report_no not in value:
                            raise ValueError(f'上传报告第 {offset} 页缺少当前报告编号')
                        if NOTICE_MARKER in value:
                            raise ValueError('上传报告正文混入注意事项页')
                        kept.append(offset - 1)
                    if not allow_guide_pages:
                        output.insert_pdf(uploaded, from_page=guide_index, to_page=uploaded_notice - 1)
                    else:
                        for page in kept:
                            output.insert_pdf(uploaded, from_page=page, to_page=page)
                    final_texts.extend(texts[page] for page in kept)
                    body_count += len(kept)
                finally:
                    uploaded.close()
            # The immutable notice may span more than one physical page.
            if notice_index < base.page_count:
                output.insert_pdf(base, from_page=notice_index, to_page=base.page_count - 1)
                final_texts.extend(base_texts[notice_index:])
            if len(final_texts) != output.page_count:
                raise ValueError("报告组合页数与校验清单不一致")
            final = output.tobytes(garbage=4, deflate=True)
        finally:
            output.close()
    finally:
        base.close()
    combined = '\n'.join(final_texts)
    if GUIDE_MARKER in combined:
        raise ValueError('正式报告仍包含正文编写说明')
    if report_no not in combined:
        raise ValueError('正式报告编号缺失')
    anchors = CALIBRATION_SIGNATURE_ANCHORS if calibration else SIGNATURE_ANCHORS
    for label, anchor in anchors.items():
        if sum(value.count(anchor) for value in final_texts) != 1:
            raise ValueError(f'正式报告缺少{label}签署定位文字')
    return final, {'frontPages': guide_index, 'bodyPages': body_count,
                   'noticePages': len(base_texts) - notice_index,
                   'sha256': hashlib.sha256(final).hexdigest()}


def text(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list, tuple)):
        raise ValueError('模板字段应为文本，不能是复合对象')
    value = str(value).strip()
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
        raise ValueError('模板字段含非法控制字符')
    return '' if value in ('—', '待填写', '待录入', '待检测人员录入') else value


def section_field(report, section, *names):
    for group in (getattr(report, 'detail', None) or {}).get('summary') or []:
        if group.get('title') == section:
            fields = dict(group.get('fields') or [])
            for name in names:
                value = text(fields.get(name))
                if value:
                    return value
    return ''


def _department_rules():
    configured = config('DOCPARSER_DEPARTMENT_RULES', '')
    if not configured:
        return DEFAULT_DEPARTMENT_RULES
    rules = json.loads(configured) if isinstance(configured, str) else configured
    if not isinstance(rules, list):
        raise ValueError('DOCPARSER_DEPARTMENT_RULES 必须为数组')
    checked = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {'center', 'keywords'}:
            raise ValueError('部门模板规则仅允许 center 与 keywords')
        center, keywords = text(rule['center']).upper(), rule['keywords']
        if center not in CENTERS or not isinstance(keywords, list) or not keywords:
            raise ValueError('部门模板规则的中心或关键词无效')
        checked.append({'center': center, 'keywords': tuple(text(item) for item in keywords)})
    return tuple(checked)


def _department_center(departments):
    matches = []
    for department in dict.fromkeys(text(value) for value in departments if text(value)):
        for rule in _department_rules():
            hit = [keyword for keyword in rule['keywords'] if keyword and keyword in department]
            if hit:
                matches.append({'department': department, 'center': rule['center'], 'keywords': hit})
    centers = {item['center'] for item in matches}
    if len(centers) > 1:
        raise ValueError('报告出具部门同时命中多个中心模板，请配置明确的出具中心')
    return (next(iter(centers)) if centers else ''), matches


def _report_kind(report_type):
    normalized = re.sub(r'[\s_-]+', '', text(report_type)).lower()
    aliases = (('抽样', 'sampling'), ('sampling', 'sampling'),
               ('工程', 'engineering'), ('engineering', 'engineering'),
               ('校准', 'calibration'), ('calibrat', 'calibration'),
               ('检验', 'inspection'), ('检查', 'inspection'), ('inspection', 'inspection'),
               ('产品', 'product'), ('检测', 'product'), ('product', 'product'))
    kind = next((value for marker, value in aliases if marker in normalized), None)
    if kind is None:
        raise ValueError(f'原包模板未支持报告格式：{report_type}')
    return kind


def _report_language(raw, format_text=''):
    value = text(raw.get('reportLanguage') or raw.get('reportTemplateLanguage')
                 or raw.get('language'))
    normalized = re.sub(r'[\s_-]+', '', value or text(format_text)).lower()
    if not normalized:
        return 'CN'
    if any(marker in normalized for marker in ('中英', '双语', 'bilingual')):
        raise ValueError('新版原包提供中、英文独立模板，不支持自动合成双语报告')
    if normalized in ('en', 'eng', 'english', '英文') or '英文' in normalized or 'english' in normalized:
        return 'EN'
    if normalized in ('cn', 'zh', 'zhcn', 'chinese', '中文', '汉语') or '中文' in normalized:
        return 'CN'
    # A layout-only reportFormat such as “双页” is not a language request.
    if not value:
        return 'CN'
    raise ValueError(f'新版原包未支持报告语言：{value}')


def _report_variant(raw, format_text=''):
    value = text(raw.get('reportTemplateVariant') or raw.get('reportVariant')
                 or raw.get('reportTemplatePages'))
    normalized = re.sub(r'[\s_-]+', '', value or text(format_text)).lower()
    if any(marker in normalized for marker in ('extended', 'extend', '扩展', '2p', '双页', '两页')):
        return 'Extended'
    if any(marker in normalized for marker in ('standard', '标准', '1p', '单页', '一页')):
        return 'Standard'
    if not value:
        return 'Standard'
    raise ValueError(f'新版原包未支持报告版式：{value}')


def profile_for(report, composition=None, *, allow_unnumbered=False):
    detail = getattr(report, 'detail', None) or {}
    raw = dict(detail.get('rawSample') or {})
    options = (detail.get('reportComposition') or {}) if composition is None else composition
    for key in ('reportLanguage', 'reportTemplateVariant'):
        if key in options:
            raw[key] = options[key]
    report_type = (text(raw.get('reportType')) or
                   section_field(report, '送样信息', '报告类型') or '产品报告')
    from .blueprints.technical_subprojects import validate_render_kind
    validate_render_kind(report, report_type)
    kind = _report_kind(report_type)
    format_text = text(raw.get('reportFormat'))
    english_derived = text(getattr(report, 'report_kind', '')).lower() == 'english'
    if english_derived and options.get('reportLanguage', 'EN') != 'EN':
        raise ValueError('英文派生报告必须使用英文模板')
    language = ('EN' if english_derived
                else _report_language(raw, format_text))
    variant = _report_variant(raw, format_text)
    if variant == 'Extended' and kind not in ('product', 'sampling'):
        raise ValueError('新版原包仅产品和抽样报告提供扩展版')
    if kind == 'calibration' and language != 'CN':
        raise ValueError('新版原包未提供英文校准证书模板')
    pages = '2p' if variant == 'Extended' else '1p'
    report_no = text(getattr(report, 'report_no', ''))
    prefix = report_no.partition('-')[0].upper()
    # The form selection is authoritative, never inferred from test department.
    explicit_center = text(raw.get('centerPrefix') or raw.get('reportIssuingCenter')
                           or raw.get('issuingCenter')).upper()
    if explicit_center and explicit_center not in CENTERS:
        raise ValueError('表单选择的报告标题/检测中心未配置，请重新选择')
    if prefix not in CENTERS and not (allow_unnumbered and not report_no and explicit_center):
        raise ValueError('报告编号的中心前缀未配置，不能自动改为其他中心')
    departments = (raw.get('reportIssuingDepartment'), raw.get('testDept'),
                   getattr(report, 'department', ''), section_field(report, '实验信息', '报告出具部门', '检测部门'))
    matches = []
    for dept_value in departments:
        dept_text = text(dept_value)
        if not dept_text:
            continue
        for rule in DEFAULT_DEPARTMENT_RULES:
            if any(kw in dept_text for kw in rule['keywords']):
                if not any(m['center'] == rule['center'] for m in matches):
                    matches.append({'center': rule['center'], 'department': dept_text})
    compatible = {prefix, 'NCSA' if prefix == 'NCAS' else prefix, 'NCAS' if prefix == 'NCSA' else prefix}
    if prefix and explicit_center and explicit_center not in compatible:
        raise ValueError('已生成报告编号与表单选择的报告标题/检测中心不一致，请核对；不能自动改号')
    if prefix and not explicit_center and prefix != 'LAB' and matches:
        matched_centers = {m['center'] for m in matches}
        if not (matched_centers & compatible):
            raise ValueError('报告编号前缀与出具部门所属检测中心不一致，请核对')
    center = explicit_center or prefix
    requirements = {
        'cma': (detail.get('contractReview') or {}).get('cma') is True,
        'cnas': (detail.get('contractReview') or {}).get('cnas') is True,
        'seal': text(raw.get('seal')) or section_field(report, '委托信息', '盖章要求'),
        'reportFormat': format_text,
        'language': language,
        'variant': variant,
    }
    if center in {'NCSA', 'NCAS'}:
        requirements['cmaOptionalPolicy'] = 'lab-explicit-seal-v1'
    filename = REPORT_FILES[kind].format(language=language, variant=variant)
    from .document_module import VENDOR as module_vendor
    if not (module_vendor / 'assets/templates' / filename).is_file():
        raise ValueError('新版原包没有与报告类别、语言和版式完全匹配的模板')
    return {'entity': 'report', 'kind': kind, 'pages': pages,
            'language': language, 'variant': variant, 'center': center,
            'filename': filename,
            'selectionEvidence': {'reportType': report_type, 'prefix': prefix,
                                  'languageRequest': text(raw.get('reportLanguage')
                                                          or raw.get('reportTemplateLanguage')
                                                          or raw.get('language')),
                                  'reportKind': text(getattr(report, 'report_kind', '')),
                                  'variantRequest': text(raw.get('reportTemplateVariant')
                                                         or raw.get('reportVariant')
                                                         or raw.get('reportTemplatePages')),
                                  'explicitCenter': explicit_center,
                                  'centerSource': 'form' if explicit_center else 'storedReportNumber',
                                  'departments': [text(value) for value in departments if text(value)],
                                  'departmentMatches': matches},
            'requirements': requirements}


def institution_profile_for(center):
    raw = config('DOCPARSER_INSTITUTION_PROFILES', '{}')
    profiles = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(profiles, dict):
        raise ValueError('DOCPARSER_INSTITUTION_PROFILES 必须为对象')
    defaults = {'companyName': '示例检测机构', 'companyEnglish': 'Example Testing Lab Co., Ltd.',
                'centerName': CENTERS[center], 'centerEnglish': CENTER_ENGLISH[center],
                'businessTel': '', 'fax': '', 'email': '', 'cmaNumber': '', 'cnasText': '',
                'accountQrUrl': '', 'reportQrBaseUrl': ''}
    configured = profiles.get(center, {})
    if not isinstance(configured, dict) or set(configured) - set(defaults):
        raise ValueError('模板机构配置含未知字段')
    merged = {**defaults, **{key: text(value) for key, value in configured.items()}}
    # A national-center report is always bilingual in the fixed institution
    # header. An empty site override must not erase the official English line.
    if merged['centerName'] and not merged['centerEnglish']:
        merged['centerEnglish'] = CENTER_ENGLISH[center]
    return merged


def institution_profile(report):
    return institution_profile_for(profile_for(report)['center'])


def entrust_profile_for(entrust, report=None, requested_kind=None):
    detail = (getattr(report, 'detail', None) or {}) if report is not None else {}
    raw = detail.get('rawSample') or {}
    info = getattr(entrust, 'info', None) or {}
    explicit = text(raw.get('entrustTemplateMode') or raw.get('entrustMode') or
                    info.get('entrustTemplateMode') or info.get('entrustMode'))

    def mode(value):
        normalized = re.sub(r'[\s_-]+', '', text(value)).lower()
        if not normalized:
            return ''
        if '工程' in normalized or 'engineering' in normalized or normalized in ('g', '4204g'):
            return 'engineering'
        if any(marker in normalized for marker in ('产品', '送样', '抽样', '校准', '检验',
                                                    'product', 'sample', '4204d', 'd')):
            return 'product'
        raise ValueError(f'原包未支持委托模式：{value}')

    explicit_kind = mode(explicit)
    requested = mode(requested_kind)
    if explicit_kind and requested and explicit_kind != requested:
        raise ValueError('显式委托模式与打印请求不一致')
    if report is not None:
        report_profile = profile_for(report, allow_unnumbered=True)
        inferred = 'engineering' if report_profile['kind'] == 'engineering' else 'product'
        center = report_profile['center']
        department_matches = report_profile['selectionEvidence']['departmentMatches']
    else:
        structured = next((text(value) for value in (
            getattr(entrust, 'project_type', ''), info.get('erpType'),
            info.get('erpProjectType')) if text(value)), '')
        inferred = ('engineering' if '工程' in (structured or text(
            getattr(entrust, 'project_name', ''))) else 'product')
        center = text(info.get('centerPrefix') or info.get('reportIssuingCenter')
                      or info.get('issuingCenter')).upper() or 'LAB'
        if center not in CENTERS:
            raise ValueError('表单选择的报告标题/检测中心未配置，请重新选择')
        department_matches = []
    kind = explicit_kind or requested or inferred
    variant = 'Extended' if str(requested_kind or '').endswith('-extended') else 'Standard'
    return {'entity': 'entrust', 'kind': kind, 'center': center, 'variant': variant,
            'filename': f"LAB-Entrust-{'4204d' if kind == 'product' else '4204g'}-{variant}-202601_tpl.docx",
            'selectionEvidence': {'explicitMode': explicit,
                                  'requestedMode': text(requested_kind),
                                  'inferredMode': inferred,
                                  'departmentMatches': department_matches}}


def entrust_context(entrust, report=None, requested_kind=None, project_no='', language='CN'):
    from .entrust_render import _business_values
    from .report_date_display import production_date_text
    selection = entrust_profile_for(entrust, report, requested_kind)
    values = _business_values(entrust, report, project_no)
    raw = ((getattr(report, 'detail', None) or {}).get('rawSample') or {}) if report is not None else {}
    review = values.get('review_items') or {}
    mapping = {
        'Client': 'client', 'SampleName': 'sample_name', 'Model': 'spec',
        'Manufacturer': 'manufacturer', 'EntrustDate': 'entrust_date',
        'SubmissionDate': 'send_date', 'Category': 'category', 'Quantity': 'quantity',
        'Trademark': 'trademark', 'Basis': 'basis', 'Criteria': 'judgment',
        'Items': 'test_project', 'Appearance': 'appearance', 'Nameplate': 'nameplate',
        'Other': 'sample_other', 'SampleHandling': 'sample_handle',
        'ReportQuantity': 'deliver_count', 'ReportDate': 'deliver_date',
        'Amount': 'amount', 'Payment': 'pay_status', 'Remark': 'remark',
        'Consignor': 'consignor', 'ConsignorPhone': 'consignor_phone',
        'ClientAddress': 'client_address', 'PartyA': 'contract_party_a',
        'Payer': 'other_party_a', 'Handler': 'handler', 'Phone': 'handler_phone',
        'Department': 'laboratory',
    }
    context = {key: text(values.get(source)) for key, source in mapping.items()}
    # Trademark is an existing DocParser raw_context field.  Prefer the uploaded
    # PNG/JPEG data URL when present; the isolated worker validates and converts
    # it to a temporary local image before invoking the unmodified maker.
    context['Trademark'] = text(values.get('trademark_image')) or context['Trademark']
    profile = institution_profile_for(selection['center'])
    context.update({
        'Center': profile['centerName'],
        'SampleNo': text(values['sample_identifier']),
        'ManufacturingDate': production_date_text(getattr(report, 'detail', None)),
        'Serial': text(raw.get('factoryNo')),
        'PICKUP': values.get('deliver_way') == '自取',
        'CMA': values.get('cma') is True, 'CNAS': values.get('cnas') is True,
        'Signature': __import__(__package__ + '.report_final_fields', fromlist=['review_signature']).review_signature(report),
    })
    for name, key in [('TECHNIQUE', 'tech'), ('INSTRUMENT', 'instrument'),
                      ('ENVIRONMENT', 'env'), ('METHOD', 'method'),
                      ('PERSON', 'personnel'), ('SAMPLE', 'sample'), ('SCOPE', 'basisAuth')]:
        context[name] = review.get(key) is True
    from .contract_review_output import review_flags
    context.update(review_flags(report))
    from .report_date_display import format_report_dates
    context = format_report_dates(context)
    if language != 'CN':
        from .entrust_output_fields import localized_entrust_fields
        context.update(localized_entrust_fields(
            getattr(report, 'detail', None), context['Category'], context['SubmissionDate'],
            language, category_separator='\n',
        ))
    return context


def render_entrust(entrust, report=None, requested_kind=None, project_no='', language='CN'):
    selection = entrust_profile_for(entrust, report, requested_kind)
    context = entrust_context(entrust, report, requested_kind, project_no, language)
    from .document_module import render_entrust as render_module_entrust
    blob, audit = render_module_entrust({**selection, 'outputLanguage': language}, context)
    from .entrust_render import _business_values
    from .entrust_output_fields import fill_testing_location
    blob, location_audit = fill_testing_location(blob, _business_values(entrust, report, project_no)['test_location'])
    blob, symbol_audit = _replace_legacy_symbol_font(blob)
    from .contract_review_output import fill_review_marks
    blob, review_audit = fill_review_marks(blob, context)
    audit.update(makerSha256=audit['sha256'], sha256=hashlib.sha256(blob).hexdigest(),
                 symbolCompatibility=symbol_audit)
    audit['changedParts'] = list(dict.fromkeys([*audit['changedParts'], *location_audit['changedParts'], *symbol_audit['changedParts'], *review_audit['changedParts']]))
    audit['reviewMarks'] = review_audit
    audit['testingLocation'] = location_audit
    audit.update(engine=ENGINE, templateSelection=selection,
                 identity={'entrustNo': text(getattr(entrust, 'entrust_no', '')),
                           'sampleNo': context['SampleNo']})
    return blob, audit


def template_snapshot(report, *, verify_package=True):
    profile = profile_for(report)
    from .document_module import VENDOR as module_vendor, MANIFEST, verify_vendor
    if verify_package:
        verify_vendor()
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    original_source = {'archiveSha256': manifest['archiveSha256'],
                       'files': [{'filename': name, 'sha256': digest}
                                 for name, digest in sorted(manifest['files'].items())]}
    paths = [module_vendor / 'assets/templates' / profile['filename'],
             Path(__file__), Path(__file__).with_name('sample_identity.py'), Path(__file__).with_name('report_generation_notices.py'), Path(__file__).with_name('report_english_fields.py'), Path(__file__).with_name('report_date_display.py'), Path(__file__).with_name('document_module_worker.py'),
             Path(__file__).with_name('production_dates.py'), Path(__file__).with_name('report_correction_dates.py'), Path(__file__).with_name('document_module.py'), MANIFEST]
    return {'engine': ENGINE, 'release': RELEASE, 'profile': profile,
            'originalSource': original_source,
            'institution': institution_profile(report),
            'identity': number_identity(report),
            'legacyIdentityConflicts': identity_snapshot_conflicts(report),
            'fieldValues': report_context(report),
            'files': [{'filename': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in dict.fromkeys(paths)]}


def _display_width(value):
    import unicodedata
    return sum(0 if unicodedata.combining(char) or unicodedata.category(char).startswith('C')
               else 2 if unicodedata.east_asian_width(char) in {'F', 'W'} else 1
               for char in text(value))


def _cnas_template_text(value):
    """Map a verbose institution configuration to the official 42-unit slot."""
    value = text(value).replace('\r\n', '\n').replace('\r', '\n')
    if _display_width(value) <= 42:
        return value
    certificate = re.search(r'(?i)\bL\s*([0-9]{3,12})\b', value)
    if certificate:
        canonical = ('中国认可\n国际互认\n检测\nTESTING\nCNAS L'
                     + certificate.group(1))
        if _display_width(canonical) <= 42:
            return canonical
    raise ValueError('CNAS 说明无法放入原模板固定标识区，请在机构配置中填写 CNAS L证书号')


def _sample_form_engineering_name(report):
    """Use the independent curtain-wall field; retain untouched legacy records."""
    detail = getattr(report, 'detail', None) or {}
    raw = detail.get('rawSample') or {}
    # Presence matters: an explicitly cleared field must never borrow sampleName.
    if 'engineeringName' in raw:
        return text(raw['engineeringName']) or '/'
    for group in detail.get('summary') or []:
        if group.get('title') == '送样信息':
            fields = dict(group.get('fields') or [])
            if '工程名称（幕墙）' in fields:
                return text(fields['工程名称（幕墙）']) or '/'
    # Existing records saved before this field was introduced keep their output.
    for key in ('sampleName', 'sampleOrProjectName'):
        if key in raw:
            return text(raw[key]) or '/'
    return (section_field(report, '送样信息', '样品/工程名称', '样品名称')
            or section_field(report, '样品信息', '样品/工程名称', '样品名称') or '/')

def report_cover_names(report):
    """Shared cover text, without requiring QR publication or rendering assets."""
    from .report_documents import _summary_sections, _pick
    detail = report.detail or {}
    raw = detail.get('rawSample') or {}
    snapshot = detail.get('entrustSnapshot') or {}
    info = snapshot.get('info') or {}
    return {
        'SampleName': (section_field(report, '送样信息', '样品名称', '样品/工程名称')
                       or text(raw.get('sampleName')) or text(info.get('sampleName'))
                       or text(info.get('projectName')) or text(report.project_name)),
        'Client': (text(snapshot.get('client')) or report.client
                   or _pick(_summary_sections(report), ('委托信息', '委托单位'))),
    }


def report_context(report):
    from .report_correction_dates import original_issue_date
    from .report_date_display import format_report_dates, report_date, production_date_text
    from .report_english_fields import localize_report_fields
    from .functions.report_standard_text import format_standard_titles
    identity = number_identity(report)
    mismatches = identity_snapshot_conflicts(report)
    if mismatches:
        raise ValueError(f"报告留存编号与系统编号不一致（{', '.join(mismatches)}），存在串号风险，禁止生成报告")
    from .report_documents import report_values
    values = report_values(report)
    detail = report.detail or {}
    raw = detail.get('rawSample') or {}
    check_input = detail.get('checkInput') or {}
    snapshot = detail.get('entrustSnapshot') or {}
    info = snapshot.get('info') or {}
    info_aliases = {
        'sampleName': ('sampleName', 'projectName'),
        'manufacturer': ('manufacturer',),
        'spec': ('specification',),
        'sampleAmount': ('sampleAmount', 'quantity'),
        'unit': ('quantityUnit',),
        'trademark': ('trademark',),
        'factoryNo': ('factoryNo', 'serialNo'),
        'produceDate': ('produceDate', 'manufacturingDate'),
        'sendDate': ('sendDate', 'submissionDate'),
        'appearance': ('appearance',),
        'testCategory': ('testCategory',),
        'testLocation': ('testLocation',),
    }
    def sample(key, *labels):
        return (section_field(report, '送样信息', *labels) or text(raw.get(key))
                or next((text(info.get(alias)) for alias in info_aliases.get(key, ())
                         if text(info.get(alias))), ''))
    def experiment(*labels):
        return section_field(report, '实验信息', *labels)
    def sampling(key, *labels):
        aliases = {'sampleUnit': 'samplingUnit', 'sampleTime': 'samplingDate', 'sampleQty': 'samplingAmount',
                   'samplingLocation': 'samplingPlace', 'entrustQty': 'samplingBase', 'sealChecker': 'sealingInspector'}
        return section_field(report, '抽样信息', *labels) or text(raw.get(key)) or text(raw.get(aliases.get(key)))
    quantity = sample('sampleAmount', '样品数量')
    unit = sample('unit', '数量单位', '单位')
    if quantity and unit and not quantity.endswith(unit):
        quantity += unit
    selection = profile_for(report)
    from .blueprints.report_publication import report_qr_url
    report_qr = report_qr_url(report)
    from .blueprints.technical_subprojects import report_item_text

    def calibration_instruments():
        if selection['kind'] != 'calibration':
            return values['instruments']
        rows = []
        for item in check_input.get('equipmentSnapshots') or []:
            if not isinstance(item, dict):
                continue
            name = text(item.get('name'))
            factory_no = text(item.get('factoryNo'))
            if factory_no:
                name = f'{name}/{factory_no}' if name else factory_no
            rows.extend((
                name,
                text(item.get('range') or item.get('measRange')),
                text(item.get('accuracy') or item.get('technicalSpecification')),
                text(item.get('certificateNo')),
                text(item.get('calUnit') or item.get('traceability')),
                report_date(item.get('planCalDate', item.get('validUntil')), iso=True),
            ))
        if not rows and values['instruments']:
            rows.extend((values['instruments'], '', '', '', '', ''))
        return '\t'.join(rows)
    return localize_report_fields(format_report_dates({
        # These are the only two QR slots present in report_demo.raw_context.
        # Fixed institution text and marks come solely from ReportConfig.
        'ReportQRCode': report_qr,
        'AccountQRCode': 'https://lab.example.com/wechat-demo',
        'ReportNo': identity['reportNo'], 'SampleNo': identity['sampleNo'],
        **report_cover_names(report),
        'Manufacturer': sample('manufacturer', '生产单位', '生产厂家'),
        'Model': sample('spec', '规格型号'),
        # Same image-first policy as entrust rendering. Normalize/validate saved
        # images via report_values; keep text as fallback for missing/bad images.
        'Trademark': (text(values.get('trademarkImage'))
                      or sample('trademark', '商标') or text(detail.get('trademark'))),
        'Serial': sample('factoryNo', '出厂编号'),
        'Place': (experiment('校准地点', '检测地点')
                  or text(check_input.get('calibrationPlace'))
                  or sample('testLocation', '检测地点')),
        'EngineeringName': _sample_form_engineering_name(report),
        'Category': sample('testCategory', '检测类别', '检验类别') or '委托', 'Quantity': quantity,
        'SampleCondition': sample('appearance', '外观'), 'ManufacturingDate': production_date_text(detail, language=selection['language']),
        'EntrustDate': text(info.get('entrustDate')) or section_field(report, '委托信息', '委托日期'),
        'SubmissionDate': sample('sendDate', '送样日期'), 'TestDate': values['testDate'],
        'ClientAddress': text(info.get('clientAddr') or info.get('clientAddress')) or values['clientAddress'],
        'Basis': (check_input['standardDisplay'] if check_input.get('standardTitleStyles') and check_input.get('standardDisplay')
                  else format_standard_titles(values['testBasis'] or text(raw.get('testBasis')), language=selection['language'])),
        'Criteria': (values['judgmentBasis'] if 'judgmentEntries' in raw or check_input.get('judgmentDisplay') is not None or raw.get('judgmentDisplay') is not None
                     else format_standard_titles(values['judgmentBasis'], language=selection['language'])),
        'Items': report_item_text(report, values['testItems']), 'Instruments': calibration_instruments(),
        'Conclusion': section_field(report, '原始记录', '结论', '检测结论'),
        'ReportDate': '',  # Filled and verified on the composed PDF after approval.
        'OriginalReportDate': original_issue_date(report),
        'Remark': section_field(report, '项目信息', '报告首页备注') or section_field(report, '原始记录', '备注'),
        'SampleArrivalDate': sampling('sampleArrivalDate', '样品到达日期') or sample('sendDate', '送样日期'),
        'SamplingUnit': sampling('sampleUnit', '抽样单位'), 'SamplingDate': sampling('sampleTime', '抽样时间', '抽样日期'),
        'Sampler': sampling('sampler', '抽样人'), 'SamplingQuantity': sampling('sampleQty', '抽样数量'),
        'SamplingPlace': sampling('samplingLocation', '抽样地点'), 'SamplingBase': sampling('entrustQty', '抽样基数', '基数'),
        'SealingInspector': sampling('sealChecker', '检查封样人员'), 'SealingCondition': sampling('sealStatus', '封样状态'),
        'TaskSource': sampling('taskSource', '任务来源'), 'SampleGrade': sampling('sampleGrade', '样品等级'),
        'InspectedUnit': sampling('inspectedUnit', '受检单位'),
        'CalibrationDate': __import__('re').sub(r'(\d{4}-\d{2}-\d{2})[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?', r'\1',
                            experiment('校准日期', '校准时间') or text(check_input.get('calibrationTime'))),
        'Temperature': experiment('温度') or text(check_input.get('temperature')),
        'Humidity': experiment('湿度') or text(check_input.get('humidity')),
        'Pressure': experiment('大气压力') or text(check_input.get('pressure')),
    }, language=selection['language']), language=selection['language'])
