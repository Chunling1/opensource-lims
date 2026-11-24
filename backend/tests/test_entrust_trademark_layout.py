"""Render the actual entrust path: image aspect ratio and row clearance."""
import base64
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
from PIL import Image
import pytest

from app.document_module import render_entrust

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
      'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}


@pytest.mark.parametrize('variant', ['Standard', 'Extended'])
@pytest.mark.parametrize('size', [(300, 300), (100, 500), (800, 100)])
def test_trademark_fits_every_copy_without_distortion(variant, size):
    image = BytesIO()
    Image.new('RGB', size, '#187abd').save(image, format='PNG')
    value = 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode()
    blob, _ = render_entrust(dict(kind='product', variant=variant),
                            dict(SampleNo='QA-TRADEMARK', Trademark=value))
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read('word/document.xml'))
    images = root.xpath('//wp:inline/wp:extent', namespaces=NS)
    assert len(images) == 4  # all four entrust copies, not only the first
    for extent in images:
        row = extent.xpath('ancestor::w:tr[1]', namespaces=NS)[0]
        row_height = float(row.find('w:trPr/w:trHeight', NS).get('{'+NS['w']+'}val')) / 20
        width, height = float(extent.get('cx')) / 12700, float(extent.get('cy')) / 12700
        assert height <= row_height - 6 + .01
        assert width / height == pytest.approx(size[0] / size[1], rel=.001)


@pytest.mark.parametrize('variant', ['Standard', 'Extended'])
def test_text_trademark_is_preserved(variant):
    value = 'QA商标 ABC-2026'
    blob, _ = render_entrust(dict(kind='product', variant=variant), dict(Trademark=value))
    with ZipFile(BytesIO(blob)) as package:
        root = etree.fromstring(package.read('word/document.xml'))
    text = ''.join(root.xpath('//w:t/text()', namespaces=NS))
    assert text.count(value) == 4
