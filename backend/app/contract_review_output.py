"""Account-bound image signatures and authoritative review preview fields."""
import base64
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

ASSETS = Path(__file__).with_name('contract_review_signatures')


def effective_review(report):
    """Ignore a source review leaked into an unreviewed English registration."""
    detail = getattr(report, 'detail', None) or {}
    review = detail.get('contractReview') or {}
    english = (getattr(report, 'report_kind', '') == 'english'
               or detail.get('reportCategory') in ('英文', '英文报告'))
    registration = (getattr(report, 'sample_reg_state', '') == '登记中'
                    or getattr(report, 'status', '') == '待合同评审')
    if review and english and registration and (
        getattr(report, 'main_report_no', '') or detail.get('derivedFrom')
    ):
        from .audit import latest_operation_audit
        action = 'report.contract_review.return' if review.get('result') == '退回' else 'report.contract_review.pass'
        if not latest_operation_audit('report', report.report_no, action):
            return {}
    return review


def review_flags(report):
    review = effective_review(report)
    completed = review.get('result') in ('通过', '退回')
    items = review.get('items') or {}
    keys = {'TECHNIQUE': 'tech', 'INSTRUMENT': 'instrument', 'ENVIRONMENT': 'env',
            'METHOD': 'method', 'PERSON': 'personnel', 'SAMPLE': 'sample', 'SCOPE': 'basisAuth'}
    # None is an unreviewed box, distinct from an unchecked completed review.
    values = {field: (items.get(key) is True if completed else None) for field, key in keys.items()}
    values.update(CMA=(review.get('cma') is True if completed else None),
                  CNAS=(review.get('cnas') is True if completed else None))
    return values


def mark_review_text(text, flags):
    labels = {'TECHNIQUE': '技术能力', 'INSTRUMENT': '仪器设备',
              'ENVIRONMENT': '环境设施条件', 'METHOD': '方法', 'PERSON': '人员',
              'SAMPLE': '样品', 'SCOPE': '检验依据授权', 'CMA': '加盖CMA章', 'CNAS': '加盖CNAS章'}
    for key, label in labels.items():
        state = flags.get(key)
        mark = '□' if state is None else ('☑' if state else '☒')
        # The template may space out CMA/CNAS labels or split them across runs.
        pattern = r'[□☐☑☒](?=\s*' + r'\s*'.join(map(re.escape, label)) + ')'
        text = re.sub(pattern, mark, text)
    return text


def fill_review_marks(blob, flags):
    """Change only review checkbox characters in the generated document copy."""
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    from .entrust_render import _following_cells, _direct_paragraphs, _transform_same_length

    with ZipFile(BytesIO(blob)) as source:
        infos = source.infolist()
        parts = {info.filename: source.read(info.filename) for info in infos}
    original = parts['word/document.xml']
    root = etree.fromstring(original, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    for cell in _following_cells(root, '合同评审'):
        for paragraph in _direct_paragraphs(cell):
            _transform_same_length(paragraph, lambda text: mark_review_text(text, flags))
    updated = etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    parts['word/document.xml'] = updated
    target = BytesIO()
    with ZipFile(target, 'w') as output:
        for info in infos:
            output.writestr(info, parts[info.filename])
    return target.getvalue(), {'changedParts': ['word/document.xml'] if updated != original else []}


@lru_cache(maxsize=1)
def _registry():
    try:
        return json.loads((ASSETS / 'manifest.json').read_text('utf-8'))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=160)
def account_image(account, name):
    entry = _registry().get(account)
    if not entry or entry['name'] != name:
        return ''
    digest = entry['sha256']
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        return ''
    try:
        suffix = '.png' if entry.get('format') == 'PNG' else '.jpg'
        data = (ASSETS / (digest + suffix)).read_bytes()
    except OSError:
        return ''
    if len(data) > 5 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != digest:
        return ''
    mime = 'png' if suffix == '.png' else 'jpeg'
    return 'data:image/' + mime + ';base64,' + base64.b64encode(data).decode('ascii')


def snapshot_image(user):
    return account_image(str(user.account or ''), str(user.name or ''))


def review_image(report):
    if report is None:
        return ''
    review = effective_review(report)
    if review.get('result') != '通过':
        return ''
    # A completed review's new image snapshot remains immutable, even when
    # the account's assigned image changes in a later asset release.
    if review.get('signatureSource') == 'account-image-v1':
        value = review.get('signature') or ''
        return value if value.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,')) else ''
    from .audit import latest_operation_audit
    event = latest_operation_audit('report', report.report_no, 'report.contract_review.pass')
    if not event or review.get('reviewer') not in (event.user_name, event.account):
        return ''
    if review.get('reviewerAccount') and review['reviewerAccount'] != event.account:
        return ''
    # Historical approvals are matched by their recorded actor account AND
    # name. Never use the current viewer, registrar, or a fuzzy name match.
    return account_image(str(event.account or ''), str(event.user_name or ''))


def authoritative_review(body, user):
    """Keep unsaved sample fields, but never accept client-supplied approvals."""
    from copy import deepcopy
    detail = deepcopy(body.get('detail') or {})
    detail.pop('contractReview', None)
    number = str(body.get('reportNo') or '').strip()
    if not number:
        return detail
    from .applications.report_lifecycle import scoped_report_query
    from .models import Report
    saved = scoped_report_query(Report.query, user).filter(Report.report_no == number).first()
    if saved is None:
        raise ValueError('样品不存在或不在数据范围内')
    review = effective_review(saved)
    if isinstance(review, dict):
        detail['contractReview'] = deepcopy(review)
    return detail


def attach_legacy_signature(blob, report):
    """Embed the recorded review image into generated legacy forms only."""
    signature = review_image(report)
    if not signature:
        return blob
    from io import BytesIO
    from docx import Document
    from docx.shared import Inches
    from docx.text.paragraph import Paragraph
    from PIL import Image
    raw = base64.b64decode(signature.split(',', 1)[1], validate=True)
    with Image.open(BytesIO(raw)) as image:
        width, height = image.size
        image.verify()
    scale = min(1.0 / width, 0.25 / height)
    document = Document(BytesIO(blob))
    targets = []
    for row in document.element.xpath('.//w:tr'):
        cells = row.xpath('./w:tc')
        for index, cell in enumerate(cells):
            label = ''.join(''.join(cell.xpath('.//w:t/text()')).split())
            if label != '合同评审':
                continue
            paragraphs = [p for target in cells[index + 1:] for p in target.xpath('./w:p')]
            if paragraphs:
                paragraph = next((p for p in paragraphs if '签字' in ''.join(p.xpath('.//w:t/text()'))), paragraphs[-1])
                if paragraph not in targets:
                    targets.append(paragraph)
    if not targets:
        raise ValueError('未定位到委托单合同评审签字栏，已停止生成以避免漏签')
    for target in targets:
        Paragraph(target, document._body).add_run().add_picture(
            BytesIO(raw), width=Inches(width * scale), height=Inches(height * scale))
    output = BytesIO()
    document.save(output)
    return output.getvalue()
