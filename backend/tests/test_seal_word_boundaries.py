import fitz
import pytest
from app.functions.report_seal_layout import _matches, organization_positions
from test_esign_pdf_signature_positioning import report_pdf, resolve_pdf


@pytest.mark.parametrize('label,expected', [
    ('Inspection and Testing Special Seal', 1),
    ('Special Seal:', 1), ('Seal', 1), ('(Seal)', 1),
    ('Sealing Inspector', 0), ('Sealed', 0), ('Reseal', 0),
    ('SpecialSeal', 0), ('Sealant', 0),
])
def test_seal_boundary_uses_original_whitespace(label, expected):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 70), label)
        matches = _matches(page, ['Seal'])
        assert len(matches) == expected
        if expected:
            assert matches[0][1] == page.search_for('Seal')[0]


def test_full_english_seal_label_resolves_signatures_and_org_seal(monkeypatch):
    raw = report_pdf(top=780, bilingual=False)
    with fitz.open(stream=raw, filetype='pdf') as doc:
        page = doc[1]
        for box in page.search_for('Seal'):
            page.add_redact_annot(box)
        page.apply_redactions()
        page.insert_text((350, 715), 'Inspection and Testing Special Seal', fontsize=10)
        raw = doc.tobytes()
    positions, snapshot = resolve_pdf(monkeypatch, raw, autosign=True)
    assert snapshot['requiredPage'] == 2
    assert snapshot['layoutLanguage'] == 'en'
    assert {p['positionPage'] for p in positions.values()} == {'2'}
    seals, _ = organization_positions(raw, snapshot['evidence']['cover']['providerPosition'])
    assert seals['cover']['positionPage'] == '2'
    assert seals['titleCover']['positionPage'] == '1'
