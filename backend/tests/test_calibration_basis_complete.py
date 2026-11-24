from io import BytesIO
from docx import Document
import pytest
from app import document_module

@pytest.mark.parametrize('basis', [
    'JJG 882-2019 《压力变送器检定规程》',
    'JJG 882-2019  《压力变送器检定规程》',
    'JJG 229-2010《工业铂、铜热电阻检定规程》',
    'JJG 882-2019《压力变送器检定规程》\nJJG 229-2010《工业铂、铜热电阻检定规程》',
    'JJG 882-2019',
    '校' * 180,
    'A' * 360,
])
def test_calibration_basis_keeps_complete_source(basis):
    context=dict(ReportNo='LAB-CAL-QA-0001', SampleName='校准样品', Basis=basis)
    blob,audit=document_module.render_report(dict(kind='calibration',center='LAB',language='CN',variant='Standard'),context)
    doc=Document(BytesIO(blob))
    cells=[c.text for t in doc.tables for row in t.rows for c in row.cells]
    assert basis in cells
    assert context['Basis']==basis
    assert 'Basis' not in audit.get('capacityWarnings', [])
