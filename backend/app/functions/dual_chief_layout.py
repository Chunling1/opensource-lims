"""Place two chiefs after the bilingual label, on the same line, without overlap."""
import math
import fitz
from .report_seal_layout import _matches, SIGN_SIZE, API_SIZE_PDF_BOUND


def dual_chief_positions(pdf, positions, *, manual=False):
    result = {k: dict(v) for k,v in positions.items()}
    first = result['chief']
    with fitz.open(stream=pdf, filetype='pdf') as doc:
        page_index = int(first['positionPage']) - 1
        if not 0 <= page_index < len(doc):
            raise ValueError('双主检签名页码无效')
        page = doc[page_index]
        y = page.rect.height - float(first['positionY'])
        matches = [(word,box) for word,box in _matches(page, ['主检','Chief Tester','ChiefTester','校准员','Calibrated by'])
                   if abs((box.y0+box.y1)/2-y) < 30]
        if not matches:
            raise ValueError('双主检签名位置未找到对应主检/校准员标签，已阻止发起')
        left = max(box.x1 for _,box in matches) + 5
        right = page.rect.width - 14
        gap = 5
        size = SIGN_SIZE
        extent = size * API_SIZE_PDF_BOUND
        if manual:
            if 'chief2' not in result:
                raise ValueError('手动定位必须同时指定主检1和主检2')
        else:
            if right-left < 2*extent+gap:
                raise ValueError('主检栏不足以容纳两个正常大小签名，请人工校准位置')
            result['chief']['positionX'] = round(left + extent/2, 3)
            result['chief2'] = {**first, 'positionX':round(left+extent+gap+extent/2,3)}
        a,b = result['chief'],result['chief2']
        if (str(a['positionPage']) != str(b['positionPage'])
                or abs(float(a['positionY'])-float(b['positionY'])) > 2
                or float(b['positionX'])-float(a['positionX']) < extent+gap-0.01):
            raise ValueError('主检2必须位于主检1右侧同一行，且两个签名不能重叠')
        for position in (a,b):
            x=float(position['positionX']);cy=page.rect.height-float(position['positionY'])
            rect=fitz.Rect(x-extent/2,cy-extent/2,x+extent/2,cy+extent/2)
            if not all(math.isfinite(v) for v in rect) or not page.rect.contains(rect) or rect.x0 < left-0.01 or rect.x1 > right+0.01:
                raise ValueError('双主检签名超出主检栏或覆盖标签，已阻止发起')
            for word in page.get_text('words'):
                if fitz.Rect(word[:4]).intersects(rect):
                    raise ValueError('双主检签名与报告文字重叠，已阻止发起')
        return result, {'chief':size,'chief2':size}, {'method':'chief-pair-full-size-px-v2','page':page_index+1,'left':round(left,3),'right':round(right,3),'gap':gap,'size':size,'pdfBoundsSize':extent,'apiSizeUnit':'px'}
