"""Platform adapter. Vendor source/assets are verified against the revision manifest.

No Flask or ORM is imported here. Validated conclusion DOCX files are passed
unchanged to the vendor subdocument API. Each vendor call runs in its own process
because the vendor uses relative assets and process-global font registrations.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

from pypdf import PdfReader

VENDOR = Path(__file__).with_name('vendor_docparser_20260911')
MANIFEST = Path(__file__).with_name('document_module_vendor_20260911.json')
CATEGORIES = {'Product', 'Sampling', 'Engineering', 'Inspection', 'Calibration', 'Entrust'}
MAX_INPUT = 50 * 1024 * 1024
CONCLUSION_POLICY = "conclusion-vendor-subdoc-v2"


@dataclass(frozen=True)
class Upload:
    name: str
    data: bytes


def is_conclusion(name):
    # Windows and POSIX upload basenames, not arbitrary suffix matching.
    return str(name).replace('\\', '/').rsplit('/', 1)[-1].casefold() == 'conclusion.docx'


def validate_docx(blob):
    if not blob or len(blob) > MAX_INPUT:
        raise ValueError('Word 文件为空或超过模块处理上限')
    try:
        with ZipFile(BytesIO(blob)) as package:
            entries = package.infolist()
            if len(entries) > 4096 or sum(x.file_size for x in entries) > 100 * 1024 * 1024:
                raise ValueError('Word 文件解压规模超过模块处理上限')
            if len({x.filename for x in entries}) != len(entries):
                raise ValueError('Word 文件含重复部件')
            if not {'[Content_Types].xml', 'word/document.xml'} <= set(package.namelist()):
                raise ValueError('文件不是有效 DOCX')
            from .docx_formula_validation import validate_embedded_members
            validate_embedded_members(package)
            for entry in entries:
                name = entry.filename
                if name.startswith('/') or '..' in name.split('/') or '\\' in name:
                    raise ValueError('Word 文件包含非法部件路径')
                if 'vbaproject' in name.lower():
                    raise ValueError('Word 文件含宏或嵌入对象，请另存为普通 DOCX')
                if name.endswith('.rels'):
                    root = ET.fromstring(package.read(name))
                    for rel in root:
                        if rel.get('TargetMode') == 'External' and not rel.get('Type', '').endswith('/hyperlink'):
                            raise ValueError('Word 文件含外部资源引用，请先嵌入资源')
    except (BadZipFile, ET.ParseError, RuntimeError) as exc:
        raise ValueError('无法读取 Word 文件') from exc


def pdf_pages(blob):
    if not isinstance(blob, bytes) or not blob.startswith(b'%PDF-') or len(blob) > MAX_INPUT:
        raise ValueError('转换未返回有效 PDF 或超过模块处理上限')
    try:
        reader = PdfReader(BytesIO(blob))
        if reader.is_encrypted:
            raise ValueError('不支持加密 PDF，请上传未加密文件')
        # Never silently strip an existing signature while composing a new file.
        if any(x.get('/FT') == '/Sig' for x in (reader.get_fields() or {}).values()):
            raise ValueError('已签署 PDF 不可重新合并，请使用签署前的文件')
        count = len(reader.pages)
        if count < 1:
            raise ValueError('PDF 没有可用页面')
        return count
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('PDF 结构无效') from exc


def convert_upload(upload, converter):
    suffix = Path(upload.name).suffix.lower()
    if suffix == '.pdf':
        result = upload.data
    elif suffix == '.docx':
        validate_docx(upload.data)
        result = converter(upload.data, '.docx')
    else:
        raise ValueError('仅支持 Word DOCX 和 PDF 附件')
    if not result:
        raise ValueError(f'{upload.name} 转 PDF 失败，未生成合并报告')
    pdf_pages(result)
    return result


def verify_vendor():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    actual = {}
    for path in VENDOR.rglob('*'):
        if path.is_symlink():
            raise ValueError('DocParser 原包不能包含链接')
        if '__pycache__' in path.parts or '%SystemDrive%' in path.parts or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.is_file():
            actual[path.relative_to(VENDOR).as_posix()] = sha256(path.read_bytes()).hexdigest()
    if actual != manifest['files']:
        raise ValueError('DocParser 原包文件校验不一致，已停止调用')
    return manifest['archiveSha256']


def _invoke(operation, profile, context=None, files=(), conclusion=None, *, authoring=False):
    archive_hash = verify_vendor()
    with TemporaryDirectory(prefix='lims-document-module-') as folder:
        task = Path(folder)
        paths = []
        for index, blob in enumerate(files):
            if blob is None:
                paths.append('')
                continue
            if operation == 'pdf' and index == 1 and blob == files[0]:
                paths.append(paths[0])
                continue
            path = task / f'input-{index}.pdf'
            path.write_bytes(blob)
            paths.append(str(path))
        conclusion_path = ''
        if conclusion is not None:
            validate_docx(conclusion)
            path = task / 'Conclusion.docx'
            path.write_bytes(conclusion)
            conclusion_path = str(path)
        output = task / ('output.pdf' if operation in {'pdf', 'issue_date'} else 'output.docx')
        payload = dict(operation=operation, profile=profile, context=context or {},
                       inputs=paths, output=str(output), conclusion=conclusion_path,
                       authoring=authoring)
        env = {key: value for key, value in os.environ.items()
               if key.upper() in {
                   'PATH', 'SYSTEMROOT', 'SYSTEMDRIVE', 'PROGRAMDATA', 'WINDIR',
                   'TEMP', 'TMP', 'LANG', 'LC_ALL',
                   'PDF_PAGE_NUMBER_SIMSUN_FONT_PATH', 'PDF_PAGE_NUMBER_TIMES_FONT_PATH',
                   'LIMS_CN_FONT_PATH', 'LIMS_EN_FONT_PATH',
               }}
        env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
        try:
            result = subprocess.run(
                [sys.executable, '-B', str(Path(__file__).with_name('document_module_worker.py'))],
                input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                encoding='utf-8', cwd=VENDOR, env=env, timeout=120, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('DocParser 模块处理超时') from exc
        if result.returncode or not output.is_file():
            # Vendor stdout can contain report text or coordinates. Never log it.
            if result.returncode == 2:
                try:
                    message = json.loads(result.stdout).get('validationError', '')
                except (ValueError, AttributeError):
                    message = ''
                if message.startswith('字段 ') and message.endswith(('；未生成报告', '；未生成文件')):
                    raise ValueError(message)
                if operation == 'issue_date' and message.startswith('报告日期核查失败：'):
                    raise ValueError(message)
            raise ValueError('DocParser 模块处理失败，请检查模板字段、文件格式及依赖')
        blob = output.read_bytes()
        if operation in {'pdf', 'issue_date'}:
            pdf_pages(blob)
        else:
            validate_docx(blob)
        audit = {'sha256': sha256(blob).hexdigest(), 'archiveSha256': archive_hash,
                      'engine': 'docparser-module-20260907', 'operation': operation,
                      'completeReport': operation == 'entrust',
                      'bodyGuideRetained': operation == 'report', 'changedParts': []}
        if operation not in {'pdf', 'issue_date', 'issuance_record'}:
            filename = (f"LAB-Report-{profile['kind'].title()}-{profile['language']}-{profile['variant']}-202609_tpl.docx"
                        if operation == 'report' else
                        f"LAB-Entrust-{'4204d' if profile['kind'] == 'product' else '4204g'}-{profile.get('variant', 'Standard')}-202601_tpl.docx")
            template = VENDOR / 'assets/templates' / filename
            audit['templateSha256'] = sha256(template.read_bytes()).hexdigest()
            with ZipFile(template) as old, ZipFile(BytesIO(blob)) as new:
                names = set(old.namelist()) | set(new.namelist())
                audit['changedParts'] = sorted(name for name in names
                    if name not in old.namelist() or name not in new.namelist() or old.read(name) != new.read(name))
                audit['addedMedia'] = sorted(set(new.namelist()) - set(old.namelist()))
        if operation == 'report':
            if conclusion is not None:
                audit['conclusionRendering'] = {'policy': CONCLUSION_POLICY}
            worker_result = json.loads(result.stdout or '{}')
            audit['capacityWarnings'] = worker_result.get('capacityWarnings', [])
            audit['noticeCodes'] = worker_result.get('noticeCodes', [])
            audit['contextPolicy'] = {
                'source': 'report_demo.ReportConfig + raw_context',
                'fixedKeys': sorted(['CMAText', 'CNASText', 'CoverFooter', 'PageHeader', 'BusinessTel', 'Fax', 'Email']),
                'rawKeys': sorted(context or {}), 'blankFixedOverrideBlocked': True,
            }
        if operation == 'issue_date':
            audit['issueDate'] = json.loads(result.stdout)['issueDate']
        return blob, audit


def render_report(profile, context, conclusion=None, *, authoring=False):
    return _invoke('report', profile, context, conclusion=conclusion, authoring=authoring)


def finalize_issue_date(pdf, approval_date, *, category, language, extended=False):
    if category not in CATEGORIES - {'Entrust'} or language not in {'CN','EN'} or type(extended) is not bool:
        raise ValueError('报告日期核查的模板参数无效')
    pdf_pages(pdf)
    return _invoke('issue_date',dict(category=category,language=language,extended=extended),
                   context={'approvalDate':approval_date},files=[pdf])


def render_entrust(profile, context):
    return _invoke('entrust', profile, context)


def compose_pdf(system_pdf, uploaded_pdf=None, extra_pdfs=(), *, category='Product', language='CN', extended=False):
    if category not in CATEGORIES or language not in {'CN', 'EN'} or type(extended) is not bool:
        raise ValueError('DocParser 类型或语言参数无效')
    front, back = {'Product': (3 if extended else 2, 1), 'Sampling': (3 if extended else 2, 1),
                   'Engineering': (1, 1), 'Inspection': (1, 1), 'Calibration': (2, 0),
                   'Entrust': (0, 0)}[category]
    system_count = pdf_pages(system_pdf)
    if category == 'Entrust':
        if uploaded_pdf is not None or extra_pdfs:
            raise ValueError('委托单背景处理只接受单份已生成 PDF')
        # The current Entrust maker takes up to four front pages from slot 0.
        # Slot 1 supplies any remaining pages, preserving every page once.
        uploaded_pdf = system_pdf
    elif system_count < front + back:
        raise ValueError('系统 PDF 页数不足，不能按模块规则裁剪')
    if uploaded_pdf is not None and pdf_pages(uploaded_pdf) < front + back:
        raise ValueError('上传完整报告页数不足，不能按模块规则裁剪')
    for pdf in extra_pdfs:
        pdf_pages(pdf)
    blob, _ = _invoke('pdf', dict(category=category, language=language, extended=extended),
                      files=[system_pdf, uploaded_pdf, *extra_pdfs])
    expected = (system_count if category == 'Entrust' else
                front + back + (pdf_pages(uploaded_pdf) - front - back if uploaded_pdf else 0)
                + sum(pdf_pages(x) for x in extra_pdfs))
    if pdf_pages(blob) != expected:
        raise ValueError('DocParser 输出页数与组合清单不一致')
    return blob


def entrust_background(pdf):
    return compose_pdf(pdf, category='Entrust', language='CN', extended=False)


def compose_uploaded_pdf(uploaded_pdf, extra_pdfs=(), *, category='Product', language='CN', extended=False):
    """Use the supplier's empty system slot; never replace uploaded front matter."""
    if category not in CATEGORIES - {'Entrust'} or language not in {'CN', 'EN'} or type(extended) is not bool:
        raise ValueError('DocParser 类型或语言参数无效')
    count = pdf_pages(uploaded_pdf)
    front, back = {'Product': (3 if extended else 2, 1), 'Sampling': (3 if extended else 2, 1),
                   'Engineering': (1, 1), 'Inspection': (1, 1), 'Calibration': (2, 0)}[category]
    # Prevent the vendor's front/back selections overlapping on a short file.
    if count < front + back:
        raise ValueError('上传完整报告页数不足，请核对报告类别和首页版式')
    expected = count + sum(pdf_pages(pdf) for pdf in extra_pdfs)
    blob, _ = _invoke('pdf', dict(category=category, language=language, extended=extended),
                      files=[None, uploaded_pdf, *extra_pdfs])
    if pdf_pages(blob) != expected:
        raise ValueError('保留上传报告模式输出页数与上传清单不一致')
    return blob


def build_report(profile, context, completed, extras, *, converter):
    """Ordered uploaded documents -> one PDF. Conclusion is consumed, not appended."""
    conclusions = [item for item in extras if is_conclusion(item.name)]
    if len(conclusions) > 1:
        raise ValueError('存在多个有效 Conclusion.docx，请只保留一个检测结论文件')
    ordinary = [item for item in extras if not is_conclusion(item.name)]
    docx, _ = render_report(profile, context, conclusions[0].data if conclusions else None)
    system_pdf = convert_upload(Upload('system.docx', docx), converter)
    completed_pdf = convert_upload(completed, converter) if completed is not None else None
    extra_pdfs = [convert_upload(item, converter) for item in ordinary]
    return compose_pdf(system_pdf, completed_pdf, extra_pdfs,
                       category=profile['kind'].title(), language=profile['language'],
                       extended=profile['variant'] == 'Extended')


def render_issuance_record(kind, rows):
    if kind not in {'product', 'engineering'} or not rows or len(rows) > 200:
        raise ValueError('请选择产品类或工程类，单次选择1至200份报告')
    fields = []
    for row in rows:
        for key in ('no', 'au', 'nam', 'cli', 'qty'):
            value = str(row.get(key) or '')
            # The public supplier API uses tabs as field separators.
            fields.append(value.replace('\t', ' ').replace('\r', ' ').replace('\n', ' '))
    return _invoke('issuance_record', {'kind': kind}, {'IssuanceRecords': '\t'.join(fields)})
