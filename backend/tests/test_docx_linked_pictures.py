"""Offline OOXML regressions; no Flask app, database or converter required."""
import importlib.util
from io import BytesIO
from pathlib import Path
import sys
import types
import unittest
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1] / 'app'
PACKAGE = '_linked_picture_test_app'
pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = pkg


def load(name):
    spec = importlib.util.spec_from_file_location(PACKAGE + '.' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


linked = load('docx_linked_pictures')
pdf_module = load('docx_pdf')
W, R, A, V = linked.W, linked.R, linked.A, linked.V
NS = f'xmlns:w="{W}" xmlns:r="{R}" xmlns:a="{A}" xmlns:v="{V}"'
IMAGE = '<w:r><w:drawing><a:blip r:embed="image1"/></w:drawing></w:r>'
VML = '<w:r><w:pict><v:shape style="width:80pt;height:60pt"><v:imagedata r:id="image1"/></v:shape></w:pict></w:r>'
BEGIN = '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
SEP = '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
END = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'


def field(code='INCLUDEPICTURE "https://example.invalid/picture"', image=IMAGE):
    return BEGIN + '<w:r><w:instrText>' + code + '</w:instrText></w:r>' + SEP + image + END


def package(content, *, image=True, target='media/image.png', external=False, header=None):
    output = BytesIO()
    with ZipFile(output, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr('word/document.xml', f'<w:document {NS}><w:body><w:p>{content}</w:p></w:body></w:document>')
        rels = f'<Relationships><Relationship Id="image1" Type="{R}/image" Target="{target}" TargetMode="{"External" if external else "Internal"}"/></Relationships>'
        z.writestr('word/_rels/document.xml.rels', rels)
        if image:
            z.writestr('word/media/image.png', b'embedded-image-sentinel')
        if header is not None:
            z.writestr('word/header1.xml', f'<w:hdr {NS}><w:p>{header}</w:p></w:hdr>')
            z.writestr('word/_rels/header1.xml.rels', rels)
    return output.getvalue()


class LinkedPicturesTest(unittest.TestCase):
    def test_complex_preserves_text_picture_layout_and_other_members(self):
        raw = package('<w:r><w:t>Sample text</w:t></w:r>' + field(image=VML))
        fixed = linked.prepare_linked_pictures(raw)
        with ZipFile(BytesIO(raw)) as before, ZipFile(BytesIO(fixed)) as after:
            self.assertIn(b'INCLUDEPICTURE', before.read('word/document.xml'))
            self.assertNotIn(b'INCLUDEPICTURE', after.read('word/document.xml'))
            for name in before.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(before.read(name), after.read(name))
            a, b = (ET.fromstring(z.read('word/document.xml')) for z in (before, after))
            self.assertEqual(a.xpath('//*[local-name()="t"]/text()'), b.xpath('//*[local-name()="t"]/text()'))
            self.assertEqual(ET.tostring(a.find('.//' + '{'+W+'}pict')), ET.tostring(b.find('.//' + '{'+W+'}pict')))
        self.assertEqual(linked.prepare_linked_pictures(fixed), fixed)

    def test_split_instruction_and_xml_entity(self):
        split = field().replace('INCLUDEPICTURE', 'INCLUDE</w:instrText></w:r><w:r><w:instrText>PIC&#84;URE')
        with ZipFile(BytesIO(linked.prepare_linked_pictures(package(split)))) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            self.assertEqual(len(list(root.iter('{'+W+'}instrText'))), 0)

    def test_simple_field_and_header(self):
        simple = '<w:fldSimple w:instr="INCLUDEPICTURE &quot;https://example.invalid/x&quot;">'+IMAGE+'</w:fldSimple>'
        with ZipFile(BytesIO(linked.prepare_linked_pictures(package(simple, header=field())))) as z:
            for name in ('word/document.xml', 'word/header1.xml'):
                self.assertNotIn(b'INCLUDEPICTURE', z.read(name))
                self.assertIn(b'image1', z.read(name))

    def test_page_fields_and_math_unchanged(self):
        content = field('PAGE', '<w:r><w:t>1</w:t></w:r>') + '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>x</m:t></m:r></m:oMath>'
        raw = package(content)
        self.assertEqual(linked.prepare_linked_pictures(raw), raw)
        with ZipFile(BytesIO(linked.prepare_linked_pictures(package(content+field())))) as z:
            root = ET.fromstring(z.read('word/document.xml'))
            self.assertEqual(root.xpath('//*[local-name()="instrText"]/text()'), ['PAGE'])
            self.assertEqual(root.xpath('//*[local-name()="oMath"]/*/*/text()'), ['x'])

    def test_missing_images_refused(self):
        for raw in (package(field(), image=False), package(field(image='')), package(field(image=IMAGE.replace('image1','absent')))):
            with self.subTest(raw_size=len(raw)), self.assertRaisesRegex(ValueError, '内嵌图片'):
                linked.prepare_linked_pictures(raw)

    def test_external_and_unsafe_image_targets_refused(self):
        for options in ({'external':True}, {'target':'../secret'}, {'target':'https://example.invalid/x'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                linked.prepare_linked_pictures(package(field(), **options))

    def test_link_attribute_refused(self):
        with self.assertRaises(ValueError):
            linked.prepare_linked_pictures(package(field(image=IMAGE.replace('r:embed="image1"','r:embed="image1" r:link="external"'))))

    def test_malformed_and_nested_fields_refused(self):
        for content in (field()[:-len(END)], field().replace(SEP,''), field(image=field()), field().replace(SEP,SEP+SEP)):
            with self.subTest(content=content), self.assertRaises(ValueError):
                linked.prepare_linked_pictures(package(content))

    def test_unrelated_external_fields_not_removed(self):
        with ZipFile(BytesIO(linked.prepare_linked_pictures(package(field()+field('DDEAUTO data',IMAGE))))) as z:
            self.assertIn(b'DDEAUTO', z.read('word/document.xml'))

    def test_plain_text_and_non_docx_unchanged(self):
        raw=package('<w:r><w:t>INCLUDEPICTURE documentation</w:t></w:r>')
        self.assertEqual(linked.prepare_linked_pictures(raw),raw)
        self.assertEqual(linked.prepare_linked_pictures(b'legacy-doc'),b'legacy-doc')

    def test_converter_receives_fixed_copy(self):
        raw=package(field())
        def convert(path, tmp):
            with ZipFile(path) as z:
                self.assertNotIn(b'INCLUDEPICTURE',z.read('word/document.xml'))
            return b'%PDF-test'
        self.assertEqual(pdf_module._office_to_pdf_with(raw,'.docx',(convert,)),b'%PDF-test')
        with ZipFile(BytesIO(raw)) as z:
            self.assertIn(b'INCLUDEPICTURE',z.read('word/document.xml'))

    def test_missing_image_error_propagates_before_any_converter(self):
        def forbidden(*args):
            self.fail('converter must not run')
        with self.assertRaisesRegex(ValueError,'内嵌图片'):
            pdf_module._office_to_pdf_with(package(field(),image=False),'.docx',(forbidden,))

    def test_formula_preparation_still_accepts_picture_result(self):
        formula=load('docx_formula_validation')
        raw=package(field()+ '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>x</m:t></m:r></m:oMath>')
        fixed=linked.prepare_linked_pictures(raw)
        self.assertEqual(formula.prepare_math_for_conversion(fixed),fixed)

    def test_xml_doctype_refused(self):
        with self.assertRaisesRegex(ValueError,'XML'):
            linked._xml(b'<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///never-read">]><x>&ext;</x>')


if __name__ == '__main__':
    unittest.main()
