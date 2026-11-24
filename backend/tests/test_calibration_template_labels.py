"""The generated document must preserve the template's environment labels."""
import ast
from pathlib import Path

from docx import Document


def test_original_units_and_table_layout_are_preserved(tmp_path):
    # Load the pure DOCX adjustment without starting the isolated worker protocol.
    source = Path(__file__).parents[1] / 'app/document_module_worker.py'
    tree = ast.parse(source.read_text('utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'fit_calibration_equipment_table')
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    document = Document()
    labels = ['温度', '湿度', '大气压力', '温度（℃）', '湿度（%）', '大气压力（kPa）']
    for label in labels:
        document.add_paragraph(label)
    table = document.add_table(rows=3, cols=6)
    table.cell(0, 0).text = '名称/编号'
    table.cell(0, 4).text = '溯源机构'
    table.cell(2, 0).text = '测试仪器'
    output = tmp_path / 'calibration.docx'
    document.save(output)
    namespace['fit_calibration_equipment_table'](output, 'CN')
    actual = Document(output)
    assert [p.text for p in actual.paragraphs] == labels
    assert len(actual.tables[0].rows) == 2
    assert len(actual.element.xpath('.//w:trPr/w:cantSplit')) == 2
