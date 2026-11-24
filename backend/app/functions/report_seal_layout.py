"""Read-only organization-seal geometry from the exact PDF submitted to eSign.

PDF coordinates returned to eSign use the bottom-left origin and seal centre.
No PDF editing, provider calls, ORM queries, or real stamp images occur here.
"""
import re

# API sizes are px; measured issued A4 PDFs use 0.78 PDF pt per API px.
# 0.80 is a conservative collision envelope, not a coordinate conversion.
SIGN_SIZE = 72
API_SIZE_PDF_BOUND = 0.80
SEAL_SIZE = 159
HOMEPAGE_SEAL_SIZE = SEAL_SIZE
COMPANY_NAMES = ('示例检测机构', '示例检测科技有限公司', 'Example Testing Lab Co., Ltd.')


def compact(text):
    return re.sub(r'\s+', '', text).casefold()


def _matches(page, phrases, *, whole_line=False):
    import fitz
    found = []
    lines = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            chars = [c for s in line['spans'] for c in s.get('chars', [])]
            visible = [c for c in chars if not c['c'].isspace()]
            if not visible or line.get('dir', (1, 0)) != (1, 0):
                continue
            # WPS emits the spaced Chinese company name as ten separate lines.
            # Join only horizontal glyphs with the same baseline, never rows.
            baseline = visible[0]['origin'][1]
            existing = next((row for row in lines if abs(row[0] - baseline) < 0.5), None)
            if existing is None:
                lines.append((baseline, chars))
            else:
                existing[1].extend(chars)
    for _, chars in lines:
        chars.sort(key=lambda c: c['bbox'][0])
        # Retain original whitespace for word boundaries, while continuing to
        # match spaced labels by their visible glyphs and exact glyph bounds.
        original = ''.join(c['c'] for c in chars).lower()
        offsets = [i for i, c in enumerate(chars) if not c['c'].isspace()]
        chars = [chars[i] for i in offsets]
        text = ''.join(c['c'] for c in chars).lower()
        for phrase in phrases:
            needle = compact(phrase)
            if whole_line and text != needle:
                continue
            start = text.find(needle)
            while start >= 0:
                # "Sealing Inspector" in English sampling metadata is not
                # the organization seal label.
                end = start + len(needle)
                before = original[offsets[start]-1] if offsets[start] else ''
                after_index = offsets[end-1] + 1
                after = original[after_index] if after_index < len(original) else ''
                if needle == 'seal' and ((before.isascii() and before.isalpha())
                                         or (after.isascii() and after.isalpha())):
                    start = text.find(needle, end)
                    continue
                rect = fitz.Rect(chars[start]['bbox'])
                for char in chars[start + 1:start + len(needle)]:
                    rect |= fitz.Rect(char['bbox'])
                found.append((phrase, rect))
                start = text.find(needle, start + len(needle))
    return found


def _position(page, page_no, rect, *, size=SEAL_SIZE):
    if page.rotation or page.rect.width <= 0 or page.rect.height <= 0:
        raise ValueError('签章定位不支持旋转或无效页面，请先核对报告版式')
    x = (rect.x0 + rect.x1) / 2
    y_top = (rect.y0 + rect.y1) / 2
    radius = size * API_SIZE_PDF_BOUND / 2
    if not (radius <= x <= page.rect.width - radius and radius <= y_top <= page.rect.height - radius):
        raise ValueError('签章区域超出页面边界，已阻止发起')
    return {'positionPage': str(page_no), 'positionX': round(x, 3),
            'positionY': round(page.rect.height - y_top, 3)}


def organization_positions(pdf, homepage_anchor):
    """Find the cover company line and homepage seal label, failing closed.

    The report homepage was already identified by the provider's five-anchor
    layout. Match the same label locally rather than hard-coding page 2.
    """
    import fitz
    with fitz.open(stream=pdf, filetype='pdf') as doc:
        homepage = int(homepage_anchor['positionPage'])
        if not 2 <= homepage <= len(doc):
            raise ValueError('未找到报告封面与首页的完整页面关系，已阻止自动盖章')
        cover = doc[0]
        companies = _matches(cover, COMPANY_NAMES, whole_line=True)
        companies = [(name, rect) for name, rect in companies if rect.y0 > cover.rect.height / 2]
        preferred = [r for r in companies if r[0] == COMPANY_NAMES[0]] or companies
        if len(preferred) != 1:
            raise ValueError('封面公司名称定位缺失或不唯一，已阻止自动盖章')
        company_name, company_box = preferred[0]
        page = doc[homepage - 1]
        labels = _matches(page, ('检验检测专用章', 'Seal'))
        # Prefer Chinese on bilingual pages. Restrict by the provider anchor,
        # so arbitrary mentions in report text cannot become stamp targets.
        anchor = homepage_anchor
        labels = [(name, rect) for name, rect in labels
                  if abs(rect.x0 - float(anchor['positionX'])) < 100
                  and abs(page.rect.height - rect.y1 - float(anchor['positionY'])) < 30]
        preferred = [r for r in labels if r[0] == '检验检测专用章'] or labels
        if len(preferred) != 1:
            raise ValueError('报告首页检验检测专用章/Seal定位缺失或不唯一，已阻止自动盖章')
        label_name, label_box = preferred[0]
        positions = {
            'titleCover': _position(cover, 1, company_box),
            'cover': _position(page, homepage, label_box, size=HOMEPAGE_SEAL_SIZE),
        }
        return positions, {
            'method': 'pdf-text-bounds-v1', 'sealSize': SEAL_SIZE,
            'sealSizes': {'titleCover': SEAL_SIZE, 'cover': HOMEPAGE_SEAL_SIZE},
            'origin': 'bottom-left', 'alignment': 'stamp-centre-on-label-centre',
            'titleCover': {'text': company_name, 'bbox': list(company_box)},
            'cover': {'text': label_name, 'bbox': list(label_box)},
        }
