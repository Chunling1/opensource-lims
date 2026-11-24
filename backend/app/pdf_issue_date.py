"""Date-only PDF finalization. Called in the isolated document worker.

Locate the current issue-date label, never test dates or original issue dates.
Supplier files stay byte-identical; existing dates are removed only from their
verified text rectangle before the supplier adds the explicit approved date.
"""
from datetime import date
from io import BytesIO
import hashlib
import re

import fitz
import pdfplumber
from pypdf import PdfReader

POLICY = 'approval-pdf-date-20261108-v3'
MONTHS = ('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')


def formatted_date(value, language):
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError('批准日期缺失或格式无效，未填写报告日期')
    return (f'{day.day} {MONTHS[day.month-1]} {day.year}' if language == 'EN'
            else f'{day.year}年{day.month}月{day.day}日')


def _date_value(value):
    compact = re.sub(r'\s+', '', value)
    if not compact or re.fullmatch(r'[-—_/年月日.]+', compact):
        return None
    # Older PDFs may contain a placeholder immediately before a date that was
    # already inserted. Accept only that prefix plus a complete valid date;
    # keep oldText intact so finalization erases the residue as well.
    compact = compact.lstrip('/')
    m = re.fullmatch(r'(\d{4})(?:年|[-/.])(\d{1,2})(?:月|[-/.])(\d{1,2})日?', compact)
    if m:
        try:
            return date(*map(int,m.groups())).isoformat()
        except ValueError:
            pass
    for i,month in enumerate(MONTHS,1):
        m=re.fullmatch(r'(\d{1,2})'+month+r'(\d{4})',compact,re.I)
        if m:
            try:return date(int(m[2]),i,int(m[1])).isoformat()
            except ValueError:pass
    raise ValueError('报告日期位置存在无法识别的内容，未覆盖；请核对原报告')


def locate(raw, maker, language):
    reader=PdfReader(BytesIO(raw))
    if reader.is_encrypted or any(f.get('/FT')=='/Sig' for f in (reader.get_fields() or {}).values()):
        raise ValueError('已签名或加密PDF不可改写报告日期')
    start,end=maker._issue_pages
    if end<=0:end=len(reader.pages)+end
    if language=='EN':
        pattern=r'(?:(?:Original|Revised)\s*)?Issue\s*Date\s*[:：]'
    elif maker._issue_fontsize==12:
        pattern=r'(?:原\s*|更\s*正\s*)?签\s*发\s*日\s*期'
    else:
        label=r'报\s*告' if maker._issue_keyword.startswith('报告') else r'签\s*发'
        pattern=r'(?:原\s*|更\s*正\s*)?'+label+r'\s*日\s*期\s*(?:Date\s*)?[:：]'
    found=[]
    with fitz.open(stream=raw,filetype='pdf') as probe:
        candidates={i for i in range(start,min(end,len(probe)))
                    if re.search(r'日|期|date',re.sub(r'\s+','',probe[i].get_text()),re.I)}
    with pdfplumber.open(BytesIO(raw)) as pdf:
        for index in range(start,min(end,len(pdf.pages))):
            page=pdf.pages[index]
            if page.rotation:
                raise ValueError('日期页存在旋转，请核对模板后再生成')
            if index not in candidates:
                continue
            for m in page.search(pattern,regex=True,case=False,return_chars=True):
                if re.sub(r'\s+','',m['text']).lower().startswith(('原','original')):continue
                chars=m['chars']
                # Use the last label line for bilingual labels split by WPS.
                last=max(chars,key=lambda c:c['bottom'])
                line=[c for c in chars if abs(c['bottom']-last['bottom'])<2]
                x=max(c['x1'] for c in line)+maker._issue_offset[0]
                baseline=max(c['bottom'] for c in line)+maker._issue_offset[1]
                # Calibration uses a separate date cell on the same row.
                # The insertion offset is not the start of existing text. WPS
                # can place a slash or first date digit immediately after ':'.
                # Calibration alone uses a separate date cell 140pt away.
                value_start = x if maker._issue_fontsize == 12 else max(c['x1'] for c in line)
                values=[c for c in page.chars if c['x0']>=value_start-1 and
                        abs(c['bottom']-last['bottom'])<4 and c['text'].strip()]
                values.sort(key=lambda c:c['x0'])
                text=''.join(c['text'] for c in values)
                value=_date_value(text)
                rect=([min(c['x0'] for c in values),min(c['top'] for c in values),
                       max(c['x1'] for c in values),max(c['bottom'] for c in values)] if values else None)
                found.append(dict(page=index,anchor={'page':index+1,'x1':x-maker._issue_offset[0],
                    'bottom':baseline-maker._issue_offset[1]},x=x,baseline=baseline,oldText=text,
                    oldDate=value,eraseRect=rect,width=page.width,height=page.height))
    if len(found)!=1:
        raise ValueError(f'报告日期位置无法唯一识别（找到{len(found)}处），未改写PDF；请核对报告类别、语言和加长版式')
    return found[0]


def finalize(input_file, output_file, profile, approval_date):
    from pathlib import Path
    from pdf_helper import PdfMaker, PdfTextWriter
    from reportlab.pdfbase import pdfmetrics
    from pypdf import PdfWriter
    raw=Path(input_file).read_bytes()
    text=formatted_date(approval_date,profile['language'])
    maker=PdfMaker(profile['category'],profile['language'],profile['extended'])
    point=locate(raw,maker,profile['language'])
    evidence={'policy':POLICY,'approvalDate':approval_date,'displayDate':text,
              'profile':profile,'page':point['page']+1,'previousText':point['oldText'],
              'sourceSha256':hashlib.sha256(raw).hexdigest(),'changed':False}
    if point['oldDate']==approval_date and re.sub(r'\s+','',point['oldText'])==re.sub(r'\s+','',text):
        Path(output_file).write_bytes(raw)
        evidence['outputSha256']=evidence['sourceSha256']
        return evidence
    # Measure before changing the source; never spill into the next column.
    from pdf_helper import ASSETS_DIR, resolve_runtime_font
    tw=PdfTextWriter(PdfWriter(),resolve_runtime_font('cn'),resolve_runtime_font('en'))
    width=sum(pdfmetrics.stringWidth(run,font,maker._issue_fontsize) for font,run in tw._iter_font_runs(text))
    if point['x']+width>point['width']-12:
        raise ValueError('报告日期超出页面可用区域，未改写PDF')
    prepared=Path(output_file).with_suffix('.date-source.pdf')
    if point['eraseRect']:
        with fitz.open(stream=raw,filetype='pdf') as doc:
            page=doc[point['page']]
            rect=fitz.Rect(point['eraseRect'])
            # Remove only the verified old date text; preserve image and vector layers.
            page.add_redact_annot(rect,fill=False,cross_out=False)
            page.apply_redactions(images=0,graphics=0,text=0)
            doc.save(prepared,garbage=4,deflate=True)
    else:
        prepared.write_bytes(raw)
    try:
        # Bind the public supplier method to the uniquely verified label only.
        class LocatedMaker(PdfMaker):
            @classmethod
            def find_text(cls,writer,keyword,regex=False):return [point['anchor']]
        selected=LocatedMaker(profile['category'],profile['language'],profile['extended'])
        selected.add_issue_date(prepared,output_file,issue_date=text)
        after=Path(output_file).read_bytes()
        checked=locate(after,maker,profile['language'])
        if checked['oldDate']!=approval_date or len(PdfReader(BytesIO(after)).pages)!=len(PdfReader(BytesIO(raw)).pages):
            raise ValueError('补入报告日期后复核失败，未采用新PDF')
        evidence.update(changed=True,outputSha256=hashlib.sha256(after).hexdigest(),
                        eraseRect=point['eraseRect'],position=[point['x'],point['baseline']])
        return evidence
    finally:
        prepared.unlink(missing_ok=True)
