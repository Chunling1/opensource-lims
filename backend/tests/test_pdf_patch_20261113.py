"""Supplier PyMuPDF update: real composition across supported profiles."""
from io import BytesIO
import fitz
import pytest
from app.document_module import compose_pdf

@pytest.mark.parametrize('language',['CN','EN'])
@pytest.mark.parametrize('category',['Product','Sampling','Engineering','Inspection','Calibration','Entrust'])
def test_current_supplier_composition_retains_body_and_page_numbering(language,category):
    with fitz.open() as doc:
        for i in range(4):
            page=doc.new_page()
            page.insert_text((40,70),'报告编号（No.）：QA-2026' if language=='CN' else 'No.ofReport: QA-2026',
                             fontname='china-s' if language=='CN' else 'helv')
            page.insert_text((40,110),f'Synthetic body {i}')
        source=doc.tobytes()
    final=compose_pdf(source,None if category=='Entrust' else source,category=category,language=language)
    with fitz.open(stream=final,filetype='pdf') as result:
        assert len(result)==4
        for i,page in enumerate(result):
            text=page.get_text()
            assert f'Synthetic body {i}' in text
            assert page.get_images()  # retained institutional background
            numbered=category=='Calibration' or category!='Entrust' and 0<i<3
            if numbered:
                needle=f'Page {i+1 if category=="Calibration" else i} of {4 if category=="Calibration" else 2}'
                assert needle in text
                locations=page.search_for(needle)
                assert len(locations)==1
                assert 0<=locations[0].y0<locations[0].y1<=page.rect.height
                if category!='Calibration':
                    anchor=page.search_for('报告编号（No.）：' if language=='CN' else 'No.ofReport:')[0]
                    spans=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
                    number_span=next(s for s in spans if needle in s['text'])
                    assert abs(number_span['origin'][1]-(anchor.y1-2))<0.1
            else:
                assert 'Page ' not in text

@pytest.mark.parametrize('label',['No. of Report:','No.of Report:','No. ofReport:','No.ofReport:'])
def test_english_wps_anchor_spacing_variants(label):
    with fitz.open() as doc:
        for _ in range(4):
            page=doc.new_page();page.insert_text((40,95),label+' QA')
        source=doc.tobytes()
    final=compose_pdf(source,source,category='Product',language='EN')
    with fitz.open(stream=final,filetype='pdf') as result:
        anchor=result[1].search_for(label)[0]
        spans=[s for b in result[1].get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
        number=next(s for s in spans if 'Page 1 of 2' in s['text'])
        assert abs(number['origin'][1]-(anchor.y1-2))<0.1
