"""Retained full-output invariants from the removed private scan feature.

Reference: immutable v1.0.96 worker (30594ba), using the current vendor.
The supplier removed regex in 20261113. Adapt only that API call on the legacy
side; new spacing/coordinates/profile checks live in test_pdf_patch_20261113.
"""
from io import BytesIO
import fitz
import pytest

@pytest.mark.parametrize('language',['CN','EN'])
@pytest.mark.parametrize('category',['Product','Sampling','Engineering','Inspection','Calibration','Entrust'])
def test_composed_document_matches_v196_text_coordinates_and_pixels(tmp_path,monkeypatch,language,category):
    from app import document_module as module
    from pathlib import Path
    import subprocess
    original=subprocess.run
    base=tmp_path/'legacy-worker.py'
    worker=Path(module.__file__).with_name('document_module_worker.py')
    # Execute the real worker; restore only its previous text-search method.
    import hashlib
    reference = Path(__file__).with_name('fixtures').joinpath('v196_document_module_worker.py').read_text(encoding='utf-8')
    assert hashlib.sha256(reference.encode()).hexdigest() == '17566f948baaae5b7cf410cf69039baddc2074f5bc2aa8a8bfd6a3df672be679'
    # This fixture always contains the literal spaced English anchor. Keep
    # full text-coordinate/pixel equality, without calling a removed vendor API.
    old_call = "return PdfMaker.find_text(writer, r'No\\.[ \\t\\u00a0]*of[ \\t\\u00a0]*Report:', regex=True)"
    assert reference.count(old_call) == 1
    reference = reference.replace(old_call, "return PdfMaker.find_text(writer, 'No. of Report:')")
    reference = reference.replace('return PdfMaker.find_text(writer, keyword, regex=regex)',
                                  'return PdfMaker.find_text(writer, keyword)')
    base.write_text(reference, encoding='utf-8')
    # The reference worker loads its validator/assets relative to __file__.
    # Replace only that path anchor; execute its original PDF path unchanged.
    base.write_text(reference.replace("Path(__file__)", "Path("+repr(str(worker))+")"), encoding='utf-8')
    def old(args,**kw):return original(args[:2]+[str(base)],**kw)
    with fitz.open() as document:
        for i in range(4):
            page=document.new_page()
            page.insert_text((40,70),'No. of Report: QA-0225')
            page.insert_text((40,110),'Report content '+str(i))
            shape=page.new_shape()
            for k in range(200):shape.draw_line((40+k,150),(43+k,180))
            shape.finish(color=(.4,.4,.4));shape.commit()
        raw=document.tobytes()
    with monkeypatch.context() as patch:
        patch.setattr(module.subprocess,'run',old)
        before=module.compose_pdf(raw,None if category=='Entrust' else raw,category=category,language=language)
    after=module.compose_pdf(raw,None if category=='Entrust' else raw,category=category,language=language)
    with fitz.open(stream=before,filetype='pdf') as a,fitz.open(stream=after,filetype='pdf') as b:
        assert len(a)==len(b)
        for x,y in zip(a,b):
            assert x.get_text('dict')==y.get_text('dict')
            assert x.get_pixmap().samples==y.get_pixmap().samples

