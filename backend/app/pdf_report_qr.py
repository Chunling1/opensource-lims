"""Copy the cover report QR onto interior pages once, without a backing.

Runs after complete PDF composition, never on preview/download reads. Reuses
the original image and soft mask; it does not regenerate a URL or replace a
cover. Existing placed copies make the operation byte-idempotent.
"""
from io import BytesIO
import hashlib

import fitz
from PIL import Image

POLICY = 'cover-report-qr-interior-20261024-v1'
MM = 72 / 25.4


def _image(block):
    image = Image.open(BytesIO(block['image'])).convert('RGBA')
    if block.get('mask'):
        image.putalpha(Image.open(BytesIO(block['mask'])).convert('L'))
    return image


def _digest(block):
    image = _image(block)
    return (image.size, hashlib.sha256(image.tobytes()).digest())


def _is_qr(block):
    """Distinguish square logos from QR images using the three finder patterns."""
    rgba = _image(block)
    image = Image.alpha_composite(Image.new('RGBA', rgba.size, 'white'), rgba).convert('L')
    dark = image.point(lambda value: 255 if value < 100 else 0)
    bounds = dark.getbbox()
    if not bounds:
        return False
    dark = dark.crop(bounds)
    w, h = dark.size
    if abs(w - h) > 2 or w < 21:
        return False
    run = 0
    while run < w and dark.getpixel((run, 0)):
        run += 1
    module = run / 7
    if module < 1:
        return False
    count = round(w / module)
    if count < 21 or count > 177 or (count - 21) % 4 or abs(w / module - count) > .5:
        return False
    step = w / count
    for left, top in ((0, 0), (count - 7, 0), (0, count - 7)):
        for y in range(7):
            for x in range(7):
                expected = x in (0, 6) or y in (0, 6) or (2 <= x <= 4 and 2 <= y <= 4)
                actual = bool(dark.getpixel((int((left + x + .5) * step), int((top + y + .5) * step))))
                if actual != expected:
                    return False
    return True


def cover_qr(document):
    page = document[0]
    candidates = []
    # Image-info digests omit soft masks. Two transparent black QR images can
    # have identical RGB digests but DIFFERENT links. Text image blocks retain
    # the positioned image AND its mask, including nested WPS form resources.
    for block in page.get_text('dict')['blocks']:
        if block['type'] != 1:
            continue
        visual = fitz.Rect(block['bbox']) * page.rotation_matrix
        # Office can horizontally scale the cover cell (actual templates have
        # 64.7 x 72 pt codes); validate the square QR pixels, not cell equality.
        if (50 <= visual.width <= 100 and 50 <= visual.height <= 100
                and .85 <= visual.width / visual.height <= 1.15
                and visual.x0 > page.rect.width / 2 and _is_qr(block)):
            candidates.append(block)
    if len(candidates) != 1:
        raise ValueError('无法唯一识别封面右侧的报告信息二维码，请核对封面；未生成内页二维码')
    return candidates[0]


def add_interior_report_qr(raw, *, category):
    if category not in {'product', 'sampling', 'engineering', 'inspection', 'calibration'}:
        raise ValueError('内页二维码的报告类型无效')
    with fitz.open(stream=raw, filetype='pdf') as document:
        if document.is_encrypted or document.get_sigflags() > 0 or any(
                widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE
                for page in document for widget in (page.widgets() or [])):
            raise ValueError('已签名或加密PDF不能补入内页二维码')
        if len(document) < 2:
            raise ValueError('完整报告页数不足，未生成内页二维码')
        cover = cover_qr(document)
        cover_digest = _digest(cover)
        # Some Office exports embed a grayscale JPEG with an ICC color space.
        # Inserting that JPEG with a separate mask is rejected by PDF readers
        # such as Poppler. Lossless RGBA preserves the exact pixels and alpha.
        cover_png = BytesIO()
        _image(cover).save(cover_png, format='PNG')
        xref = None
        # The composer retains one final notice for these four categories.
        # Calibration has no fixed notice: its last results page also gets a QR.
        last_text = ''.join(document[-1].get_text().split())
        notice = category != 'calibration' or ('注意事项' in last_text and 'NOTICE' in last_text.upper())
        pages = list(range(1, len(document) - int(notice)))
        added = []
        for index in pages:
            page = document[index]
            w = page.rect.width
            visual = fitz.Rect(w - 21 * MM, 5 * MM, w - 5 * MM, 21 * MM)
            rect = visual * page.derotation_matrix
            # A repeated generation must not stack images or rewrite the PDF.
            blocks = page.get_text('dict')['blocks']
            present = [item for item in blocks if item['type'] == 1
                       and all(abs(a - b) < .3 for a, b in zip(item['bbox'], rect))]
            if present:
                if len(present) == 1 and _digest(present[0]) == cover_digest:
                    continue
                raise ValueError(f'第{index + 1}页二维码位置已有不同图像，未覆盖')
            for block in blocks:
                if block['type'] != 0:
                    continue
                for line in block['lines']:
                    for span in line['spans']:
                        if span['text'].strip() and rect.intersects(fitz.Rect(span['bbox'])):
                            raise ValueError(f'第{index + 1}页右上角二维码与文字重叠，请调整原报告页边距')
            args = dict(xref=xref) if xref else dict(stream=cover_png.getvalue())
            xref = page.insert_image(rect, **args, rotate=page.rotation, keep_proportion=True, overlay=True)
            added.append(index + 1)
        output = document.tobytes(garbage=3, deflate=True) if added else raw
    return output, dict(policy=POLICY, pages=[p + 1 for p in pages], addedPages=added,
                        sizeMm=16, topMm=5, rightMm=5, addedBackground=False,
                        sourceSha256=hashlib.sha256(raw).hexdigest(),
                        outputSha256=hashlib.sha256(output).hexdigest())
