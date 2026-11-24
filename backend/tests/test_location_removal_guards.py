"""Changed input probes: appendix removal must not weaken unrelated guards."""
from io import BytesIO
import fitz
import pytest
from app import docparser_field_only as fields, document_module as module


def pdf(*texts):
    with fitz.open() as doc:
        for text in texts: doc.new_page().insert_text((48,72),text,fontname='china-s',fontsize=10)
        return doc.tobytes()


NO='QA-2026-0001'
BASE=lambda: pdf('SERVER COVER '+NO,NO+' Chief Tester Verification Approval',
                 NO+' 内容编写说明',NO+' 注意事项 NOTICE')


@pytest.mark.parametrize('changed',[False,True])
def test_old_address_page_is_never_stripped_or_rejected(changed):
    uploaded=pdf('UPLOADED COVER '+NO,'UPLOADED HOME '+NO,NO+' RESULT',
                 NO+' HN-LOCATION-V1: old-address'+(' EDITED' if changed else ''),
                 NO+' 注意事项 NOTICE')
    final,audit=fields.compose_completed_pdf(BASE(),[uploaded],NO,allow_guide_pages=True)
    with fitz.open(stream=final,filetype='pdf') as doc:
        assert len(doc)==5 and 'SERVER COVER' in doc[0].get_text()
        assert 'HN-LOCATION-V1' in doc[3].get_text()
        assert ('EDITED' in doc[3].get_text())==changed
    assert audit['bodyPages']==2


@pytest.mark.parametrize('mutation',['text','drawing','annotation'])
def test_changed_guide_is_rejected(mutation):
    with fitz.open(stream=BASE(),filetype='pdf') as doc:
        if mutation=='text': doc[2].insert_text((40,140),'AUTHOR RESULT')
        if mutation=='drawing': doc[2].draw_rect((40,140,80,180))
        if mutation=='annotation': doc[2].add_text_annot((40,140),'AUTHOR RESULT')
        uploaded=doc.tobytes()
    with pytest.raises(ValueError,match='说明页含有其他内容'):
        fields.compose_completed_pdf(BASE(),[uploaded],NO,allow_guide_pages=True)


def test_output_missing_page_is_rejected(monkeypatch):
    monkeypatch.setattr(module,'_invoke',lambda *a,**k:(pdf('lost pages'),{}))
    with pytest.raises(ValueError,match='输出页数'):
        module.compose_pdf(BASE(),BASE())


def test_signed_pdf_is_rejected():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, DictionaryObject, ArrayObject, TextStringObject
    writer=PdfWriter(clone_from=PdfReader(BytesIO(BASE())))
    signature=DictionaryObject({NameObject('/FT'):NameObject('/Sig'),NameObject('/T'):TextStringObject('SignatureQA')})
    writer._root_object[NameObject('/AcroForm')]=DictionaryObject({NameObject('/Fields'):ArrayObject([writer._add_object(signature)])})
    buffer=BytesIO();writer.write(buffer)
    with pytest.raises(ValueError,match='已签署'):
        module.pdf_pages(buffer.getvalue())
