"""Read-only geometry for bilingual calibration certificates, from immutable PDF."""
import hashlib
import fitz
from .report_seal_layout import _matches, _position, SEAL_SIZE, API_SIZE_PDF_BOUND


LABELS = {
    'chief': ('校准员', 'Calibrated by'),
    'reviewer': ('审核员', 'Checked by'),
    'approver': ('批准人', 'Approved by'),
    'date': ('签发日期', 'Issue Date'),
}


def _one(page, aliases):
    for word in aliases:
        found = _matches(page, (word,))
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise ValueError('校准证书签字标签重复，请人工校准位置')
    raise ValueError('校准证书缺少签字或签发日期标签')


def calibration_positions(pdf):
    """None for detection reports. Calibration must pass a distinct layout check.

    The organization seal deliberately overlays the issue-date/reviewer area
    selected by the user. Derive its centre from the immutable signature grid.
    Personal signatures and template bytes are never moved or rewritten.
    """
    with fitz.open(stream=pdf, filetype='pdf') as doc:
        pages = [p for p in doc if _matches(p, ('Calibration Certificate', '校准证书'))]
        if not pages:
            return None
        if len(pages) != 1 or pages[0].number != 0:
            raise ValueError('校准证书首页不唯一或不是第一页，请人工核对')
        p = pages[0]
        if p.rotation:
            raise ValueError('校准证书页面旋转，请人工核对')
        marks = {key: _one(p, LABELS[key]) for key in ('chief', 'reviewer', 'approver')}
        # Some certificates repeat Issue Date in the information table. Use
        # the nearest date row above the verified signature row, not the first occurrence.
        signature_y = marks['chief'][1].y0
        for alias in LABELS['date']:
            dates = [(word, box) for word, box in _matches(p, (alias,)) if 10 < signature_y-box.y0 < 100]
            if dates:
                dates.sort(key=lambda item:item[1].y0, reverse=True)
                if len(dates)>1 and abs(dates[0][1].y0-dates[1][1].y0)<2:
                    raise ValueError('校准证书签发日期行不唯一，请人工核对')
                marks['date'] = dates[0]
                break
        if 'date' not in marks:
            raise ValueError('校准证书签字栏上方缺少签发日期')
        a, r, c = [marks[key][1] for key in ('approver', 'reviewer', 'chief')]
        if not (a.x0 + 80 < r.x0 and r.x0 + 80 < c.x0 and
                max(a.y0, r.y0, c.y0) - min(a.y0, r.y0, c.y0) < 10 and
                10 < a.y0 - marks['date'][1].y0 < 100):
            raise ValueError('校准证书签字区排列不符合模板，请人工核对')
        positions = {}
        for key, next_x in [('approver', r.x0), ('reviewer', c.x0), ('chief', p.rect.width - 50)]:
            box = marks[key][1]
            bilingual = [b for _, b in _matches(p, LABELS[key]) if abs(b.y0-box.y0)<25]
            x = max(b.x1 for b in bilingual) + 5 + 36
            if x + 36 >= next_x - 5:
                raise ValueError('校准证书签名区宽度不足，请人工校准位置')
            positions[key] = {'positionPage': '1', 'positionX': round(x, 3),
                              'positionY': round(p.rect.height - (box.y0 + box.y1)/2, 3)}
        # Date belongs in the value column, not over the bilingual row label.
        date_box = marks['date'][1]
        positions['date'] = {'positionPage':'1', 'positionX':round(p.rect.width * .62,3),
                             'positionY':round(p.rect.height-(date_box.y0+date_box.y1)/2,3)}
        # User-selected location: between the issue-date value and reviewer
        # signature, not the unrelated empty certificate header corner.
        x = (positions['reviewer']['positionX'] + c.x0) / 2
        cy = ((date_box.y0+date_box.y1)/2 + (r.y0+r.y1)/2) / 2
        radius = SEAL_SIZE * API_SIZE_PDF_BOUND / 2
        signature_bottom = max(b.y1 for _,b in _matches(p, LABELS['chief']+LABELS['reviewer']+LABELS['approver']))
        footer_edges = []
        for drawing in p.get_drawings():
            for item in drawing['items']:
                if item[0]=='l':
                    p1,p2=item[1:3]
                    if abs(p1.y-p2.y)<.5 and abs(p1.x-p2.x)>p.rect.width*.6 and p1.y>signature_bottom+2:
                        footer_edges.append(p1.y)
        footer_edges += [b.y0 for _,b in _matches(p, ('地址','ADD:','Address')) if b.y0>signature_bottom+2]
        if not footer_edges:
            raise ValueError('校准证书未找到签字区下方页脚边界，请人工校准位置')
        footer_y=min(footer_edges)
        cy=min(cy,footer_y-radius-3)
        seal = fitz.Rect(x-radius, cy-radius, x+radius, cy+radius)
        if not p.rect.contains(seal) or seal.x0 <= r.x0 or seal.y1 >= p.rect.height-50:
            raise ValueError('校准证书签发日期/审核签字区无法容纳印章，请人工校准位置')
        positions['cover'] = _position(p, 1, seal)
        positions['titleCover'] = dict(positions['cover'])
        return positions, {'layoutKind':'calibration', 'method':'calibration-review-date-overlay-v3',
            'sourceSha256':hashlib.sha256(pdf).hexdigest(), 'requiredPage':1,
            'positions':positions, 'labels':{k:{'text':v[0],'bbox':list(v[1])} for k,v in marks.items()},
            'sealBox':list(seal), 'normalSealCount':1, 'sealSize':SEAL_SIZE, 'intentionalOverlay':'issue-date-reviewer', 'footerY':footer_y}
