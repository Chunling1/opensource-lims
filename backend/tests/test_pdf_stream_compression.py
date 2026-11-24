"""Merged vector pages remain compressed without changing their contents."""
from io import BytesIO
import fitz
import pytest
from pypdf import PdfReader
from pypdf._page import PageObject
from app.document_module import MAX_INPUT, pdf_pages
from app.vendor_docparser_20260911.pdf_helper import PdfMaker


def test_composition_compresses_streams_losslessly(tmp_path, monkeypatch):
    source = tmp_path / 'source.pdf'
    with fitz.open() as doc:
        for index in range(4):
            page = doc.new_page()
            page.insert_text((40,70), 'No. of Report: SYNTHETIC')
            shape = page.new_shape()
            for i in range(60000):
                x, y = 40+i%480, 100+i%600
                shape.draw_line((x,y),(x+2,y+2))
            shape.finish(width=.1)
            shape.commit()
        doc.save(source, deflate=True)
    before, after = tmp_path/'before.pdf', tmp_path/'after.pdf'
    with monkeypatch.context() as patch:
        patch.setattr(PageObject, 'compress_content_streams', lambda self: None)
        PdfMaker('Product','EN').make([str(source),str(source)], before)
    PdfMaker('Product','EN').make([str(source),str(source)], after)
    assert after.stat().st_size < before.stat().st_size / 2
    a,b = PdfReader(before),PdfReader(after)
    assert len(a.pages) == len(b.pages) == 4
    with fitz.open(before) as old, fitz.open(after) as new:
        for i in range(4):
            assert a.pages[i].get_contents().get_data() == b.pages[i].get_contents().get_data()
            assert old[i].get_text() == new[i].get_text()
            assert old[i].get_pixmap().samples == new[i].get_pixmap().samples
    assert pdf_pages(after.read_bytes()) == 4


def test_oversize_pdf_still_rejected():
    with pytest.raises(ValueError, match='PDF'):
        pdf_pages(b'%PDF-' + b' ' * MAX_INPUT)
