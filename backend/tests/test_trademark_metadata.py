"""Synthetic EXIF reproduces python-docx's failure without customer image data."""
import base64
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image, ImageChops, ImageOps, ImageStat
from docx.image.image import Image as DocxImage
from lxml import etree
from app.document_module import render_entrust, render_report

NS = {'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}


def jpeg_with_non_utf8_exif(orientation=1):
    image = Image.new('RGB', (1392, 273), '#06438e')
    exif = Image.Exif()
    exif[270] = 'SYNTHETIC_DESCRIPTION'
    exif[274] = orientation
    raw = BytesIO()
    image.save(raw, 'JPEG', exif=exif, dpi=(72, 72))
    # An ASCII-tag payload from legacy software can contain non-UTF-8 bytes.
    data = raw.getvalue().replace(b'SYNTHETIC_DESCRIPTION', b'\xcaYNTHETIC_DESCRIPTION')
    with Image.open(BytesIO(data)) as decoded:
        decoded.verify()
    with pytest.raises(UnicodeDecodeError):
        DocxImage.from_blob(data)
    return data


@pytest.mark.parametrize('variant', ['Standard', 'Extended'])
@pytest.mark.parametrize('orientation', [1, 6])
def test_jpeg_metadata_is_removed_only_from_render_copy(variant, orientation):
    raw = jpeg_with_non_utf8_exif(orientation)
    value = 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()
    context = dict(SampleNo='QA-EXIF', Trademark=value)
    blob, _ = render_entrust(dict(kind='product', variant=variant), context)
    assert context['Trademark'] == value
    with Image.open(BytesIO(raw)) as original:
        expected = ImageOps.exif_transpose(original).convert('RGB')
    with ZipFile(BytesIO(blob)) as package:
        embedded = [package.read(name) for name in package.namelist() if name.startswith('word/media/')]
        matches = []
        for data in embedded:
            with Image.open(BytesIO(data)) as image:
                if image.size == expected.size:
                    # JPEG input stays JPEG to avoid inflating photos; only metadata is dropped.
                    assert image.format == 'JPEG' and not image.getexif()
                    diff = ImageChops.difference(image.convert('RGB'), expected)
                    assert max(ImageStat.Stat(diff).mean) < 3
                    matches.append(data)
        assert matches
        root = etree.fromstring(package.read('word/document.xml'))
    extents = root.xpath('//wp:inline/wp:extent', namespaces=NS)
    assert len(extents) == 4
    for extent in extents:
        assert int(extent.get('cx')) / int(extent.get('cy')) == pytest.approx(expected.width / expected.height, rel=.001)


@pytest.mark.parametrize('variant', ['Standard', 'Extended'])
def test_transparent_png_remains_transparent(variant):
    raw = BytesIO()
    Image.new('RGBA', (80, 20), (10, 50, 120, 80)).save(raw, 'PNG')
    blob, _ = render_entrust(dict(kind='product', variant=variant),
                            dict(Trademark='data:image/png;base64,' + base64.b64encode(raw.getvalue()).decode()))
    with ZipFile(BytesIO(blob)) as package:
        images = [package.read(name) for name in package.namelist() if name.startswith('word/media/')]
        assert any(Image.open(BytesIO(data)).convert('RGBA').getpixel((0, 0)) == (10, 50, 120, 80) for data in images)


@pytest.mark.parametrize('language', ['CN', 'EN'])
def test_shared_report_worker_accepts_same_legacy_jpeg(language):
    raw = jpeg_with_non_utf8_exif()
    blob, _ = render_report(dict(center='LAB', kind='product', language=language, variant='Standard'),
                            dict(ReportNo='LAB-2026QA-0001', SampleName='QA',
                                 Trademark='data:image/jpeg;base64,' + base64.b64encode(raw).decode()))
    with ZipFile(BytesIO(blob)) as package:
        assert any(name.startswith('word/media/') and name.endswith(('.jpg', '.jpeg')) for name in package.namelist())


def test_oversized_trademark_is_bounded_and_keeps_aspect():
    raw = BytesIO()
    Image.new('RGB', (4800, 1200), '#06438e').save(raw, 'JPEG', quality=95)
    source = raw.getvalue()
    blob, _ = render_entrust(dict(kind='product', variant='Standard'),
                            dict(Trademark='data:image/jpeg;base64,' + base64.b64encode(source).decode()))
    with ZipFile(BytesIO(blob)) as package:
        media = [package.read(name) for name in package.namelist() if name.startswith('word/media/')]
        sized = [Image.open(BytesIO(data)).size for data in media]
        assert (1600, 400) in sized
        assert all(max(size) <= 1600 for size in sized if size[0] / size[1] == 4)
        root = etree.fromstring(package.read('word/document.xml'))
    for extent in root.xpath('//wp:inline/wp:extent', namespaces=NS):
        assert int(extent.get('cx')) / int(extent.get('cy')) == pytest.approx(4, rel=.001)
