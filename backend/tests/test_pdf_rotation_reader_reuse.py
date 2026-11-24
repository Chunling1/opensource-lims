from io import BytesIO

import fitz
import pytest

from app import document_module


def document(prefix, count):
    with fitz.open() as pdf:
        for i in range(count):
            page = pdf.new_page()
            page.insert_text((40, 70), 'No. of Report: QA-ROTATION')
            page.insert_text((40, 150), f'{prefix}-{i}')
        return pdf.tobytes()


@pytest.mark.parametrize('front_count,body_count', [(3, 7), (7, 3)])
def test_body_range_uses_body_reader_and_preserves_extra_order(front_count, body_count):
    result = document_module.compose_pdf(document('FRONT', front_count), document('BODY', body_count),
        [document('EXTRA', 2)], category='Engineering', language='EN')
    with fitz.open(stream=result, filetype='pdf') as pdf:
        expected = ['FRONT-0', *[f'BODY-{i}' for i in range(1, body_count-1)], 'EXTRA-0', 'EXTRA-1', f'FRONT-{front_count-1}']
        assert len(pdf) == len(expected)
        for page, marker in zip(pdf, expected):
            assert marker in page.get_text()


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_page_number_uses_visible_anchor_after_rotation(rotation):
    from pypdf import PdfWriter
    import importlib.util
    import sys
    path = document_module.VENDOR / 'pdf_helper.py'
    spec = importlib.util.spec_from_file_location('rotation_pdf_helper', path)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    with fitz.open(stream=document('BODY', 3), filetype='pdf') as source:
        source[1].set_rotation(rotation)
        rect = source[1].search_for('No. of Report:')[0] * source[1].rotation_matrix
        raw = source.tobytes()
    writer = PdfWriter(clone_from=BytesIO(raw))
    anchor = next(p for p in helper.PdfMaker.find_text(writer, 'No. of Report:') if p['page'] == 2)
    assert anchor['bottom'] == pytest.approx(rect.y1, abs=.01)
    writer.close()
    result = document_module.compose_pdf(document('FRONT', 3), raw, category='Engineering', language='EN')
    with fitz.open(stream=result, filetype='pdf') as output:
        assert len(output) == 3 and output[1].rotation == 0
        spans = [s for b in output[1].get_text('dict')['blocks'] for line in b.get('lines', []) for s in line['spans']]
        page_no = next(s for s in spans if 'Page 1 of 1' in s['text'])
        assert page_no['origin'][1] == pytest.approx(rect.y1-2, abs=.02)
        assert 'BODY-1' in output[1].get_text()


@pytest.mark.parametrize('category', ['Engineering', 'Entrust'])
def test_identical_content_shares_input_path_and_preserves_pages(category, monkeypatch):
    import json
    from pathlib import Path
    run = document_module.subprocess.run
    calls = []

    def inspect_and_run(*args, **kwargs):
        payload = json.loads(kwargs['input'])
        calls.append(payload['inputs'])
        assert payload['inputs'][0] == payload['inputs'][1]
        assert not Path(payload['inputs'][0]).with_name('input-1.pdf').exists()
        return run(*args, **kwargs)

    monkeypatch.setattr(document_module.subprocess, 'run', inspect_and_run)
    raw = document('SAME', 7)
    # Independent bytes with equal content must also reuse the file.
    body = bytes(bytearray(raw)) if category == 'Engineering' else None
    extras = [document('EXTRA', 2)] if category == 'Engineering' else []
    result = document_module.compose_pdf(raw, body, extras, category=category, language='EN')
    assert len(calls) == 1
    expected = [f'SAME-{i}' for i in range(7)]
    if category == 'Engineering':
        expected[6:6] = ['EXTRA-0', 'EXTRA-1']
    with fitz.open(stream=result, filetype='pdf') as pdf:
        assert len(pdf) == len(expected)
        for page, marker in zip(pdf, expected):
            assert marker in page.get_text()
