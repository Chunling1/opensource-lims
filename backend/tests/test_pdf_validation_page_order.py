"""Reuse text only for pages actually retained, without weakening anchors."""
import fitz
import pytest
from app import docparser_field_only as fields
from test_location_removal_guards import pdf, BASE, NO

@pytest.mark.parametrize('allow_guide', [False, True])
def test_multiple_uploads_validate_only_retained_pages_in_order(allow_guide):
    def upload(label):
        return pdf('Ignored Chief Tester', 'Ignored Verification Approval',
                   NO+' '+label, NO+' 注意事项 NOTICE Ignored Approval')
    raw,audit=fields.compose_completed_pdf(BASE(),[upload('FIRST'),upload('SECOND')],NO,
                                          allow_guide_pages=allow_guide)
    with fitz.open(stream=raw,filetype='pdf') as doc:
        texts=[fields._normalized(p.get_text()) for p in doc]
        assert len(doc)==5
        assert 'FIRST' in texts[2] and 'SECOND' in texts[3]
        assert all('Ignored' not in t for t in texts)
        assert sum(t.count('Approval') for t in texts)==1
    assert audit['bodyPages']==2

@pytest.mark.parametrize('extra', ['Chief Tester','Verification','Approval'])
def test_duplicate_signature_in_retained_body_still_rejected(extra):
    uploaded=pdf('cover','home',NO+' RESULT '+extra,NO+' 注意事项 NOTICE')
    with pytest.raises(ValueError,match='签署定位文字'):
        fields.compose_completed_pdf(BASE(),[uploaded],NO)

def test_missing_signature_in_retained_pages_still_rejected():
    base=pdf(NO+' COVER',NO+' Chief Tester Verification',NO+' 内容编写说明',NO+' 注意事项 NOTICE')
    uploaded=pdf('cover','Approval discarded',NO+' RESULT',NO+' 注意事项 NOTICE')
    with pytest.raises(ValueError,match='签署定位文字'):
        fields.compose_completed_pdf(base,[uploaded],NO)


def test_compact_composition_preserves_links_annotations_and_widgets(tmp_path):
    from app.vendor_docparser_20260911.pdf_helper import PdfMaker
    source=tmp_path/'source.pdf'
    with fitz.open() as doc:
        for i in range(4):
            doc.new_page().insert_text((40,70),'No. of Report: QA')
        page=doc[1]
        page.add_text_annot((90,180),'retained annotation')
        page.insert_link({'kind':fitz.LINK_URI,'from':fitz.Rect(100,200,180,220),'uri':'https://example.invalid/qa'})
        widget=fitz.Widget();widget.field_name='QA-field';widget.field_type=fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_value='kept';widget.rect=fitz.Rect(100,240,180,270);page.add_widget(widget)
        doc.save(source)
    output=tmp_path/'composed.pdf'
    PdfMaker('Product','EN').make([str(source),str(source)],output)
    with fitz.open(output) as doc:
        assert len(doc)==4
        assert any(a.info['content']=='retained annotation' for a in doc[1].annots())
        assert any(link.get('uri')=='https://example.invalid/qa' for link in doc[1].get_links())
        assert any(w.field_name=='QA-field' and w.field_value=='kept' for w in doc[1].widgets())
