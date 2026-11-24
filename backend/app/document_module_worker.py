"""Private worker protocol; never a web upload endpoint or business CLI.

Calls the manifest-verified helper APIs. No monkeypatches, sys.path changes in the
web process, or global cwd changes in the web process.
"""
import sys
from pathlib import Path

# The backend app/platform package must not shadow Python's stdlib platform.
# Load the existing pure validator by exact file, never add app/ to import paths.
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
sys.path[:] = [entry for entry in sys.path if Path(entry or '.').resolve() != SCRIPT_DIRECTORY]
import importlib.util
_validator_spec = importlib.util.spec_from_file_location(
    '_lims_existing_field_validation', SCRIPT_DIRECTORY / 'docparser_field_worker.py')
_validator = importlib.util.module_from_spec(_validator_spec)
_validator_spec.loader.exec_module(_validator)
FieldError = _validator.FieldError
FieldCapacityError = _validator.FieldCapacityError
validate_fields = _validator.validate_fields

import ast
import base64
from contextlib import redirect_stdout
from io import StringIO
import json
import re
import socket


def denied(*args, **kwargs):
    raise RuntimeError('document worker network disabled')


def raw_fields(path):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'raw_context' for t in node.targets):
            if isinstance(node.value, ast.Dict):
                return {ast.literal_eval(key) for key in node.value.keys}
    raise ValueError('raw_context is missing')


def trademark_image_layout(template, context, actual, report):
    """Reserve line/padding room around the inline image, not just its pixels."""
    value = context.get('Trademark')
    if 'Trademark' not in actual or not isinstance(value, str) or not report.is_jpg_or_png(value):
        return None
    from template_utils import TemplateGeometry
    cells = TemplateGeometry(template).find('Trademark')
    if len(cells) != 1 or not cells[0].width_pt or not cells[0].height_pt:
        raise FieldError('字段 Trademark（商标图样）尺寸不明确；未生成报告')
    cell = cells[0]
    if cell.width_pt <= 8 or cell.height_pt <= 10:
        raise FieldError('字段 Trademark（商标图样）空间不足；未生成报告')
    actual['Trademark'] = report.inline_image(value, width=cell.width_pt-8, height=cell.height_pt-10)
    return cell


def apply_trademark_image_layout(output, cell):
    if cell is None:
        return
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    w='{'+ns['w']+'}'
    with ZipFile(output) as archive:
        root=etree.fromstring(archive.read(cell.part))
        target=root.xpath('.//w:tbl',namespaces=ns)[cell.table-1].findall(w+'tr')[cell.row-1].findall(w+'tc')[cell.cell-1]
        if len(target.findall('.//'+w+'drawing')) != 1:
            raise FieldError('字段 Trademark（商标图样）输出定位不一致；未生成报告')
        def child(parent,name):
            node=parent.find(w+name)
            if node is None:
                node=etree.Element(w+name);parent.insert(0,node)
            return node
        child(child(target,'tcPr'),'vAlign').set(w+'val','center')
        for paragraph in target.findall(w+'p'):
            props=child(paragraph,'pPr')
            spacing=child(props,'spacing')
            for key,value in dict(before=0,after=0,line=240,lineRule='auto').items():
                spacing.set(w+key,str(value))
            child(props,'snapToGrid').set(w+'val','0')
        buffer=BytesIO()
        with ZipFile(buffer,'w') as result:
            for item in archive.infolist():
                result.writestr(item,etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
                                if item.filename==cell.part else archive.read(item.filename))
    output.write_bytes(buffer.getvalue())


def align_extended_entrust_item_labels(output):
    """Center the fixed-height Extended Items label without moving copy marks.

    WPS ignores vAlign=center when this cell contains the floating copy mark.
    Changing layoutInCell also moves that mark, so keep the drawing untouched.
    For the supplier's fixed-height single-line label only, express centering as
    half the remaining row height in paragraph spacing (twips). The 324-twip
    line box is the validated 12pt supplier label line, not a page coordinate.
    No business text, table geometry or immutable supplier asset is changed.
    """
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
          'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'}
    with ZipFile(output) as archive:
        root = etree.fromstring(archive.read('word/document.xml'))
        changed = False
        for cell in root.findall('.//w:tc', ns):
            # Direct paragraph text only: exclude text nested in floating shapes.
            text = ''.join(cell.xpath('./w:p/w:r/w:t/text()', namespaces=ns))
            if re.sub(r'\s+', '', text) != '检验项目':
                continue
            w = '{' + ns['w'] + '}'
            height = cell.getparent().find('w:trPr/w:trHeight', ns)
            paragraphs = cell.findall('w:p', ns)
            if (height is None or height.get(w + 'hRule') != 'exact'
                    or len(paragraphs) != 1 or int(height.get(w + 'val', '0')) < 324):
                continue
            for anchor in cell.findall('.//wp:anchor', ns):
                horizontal = anchor.find('wp:positionH', ns)
                vertical = anchor.find('wp:positionV', ns)
                if (horizontal is not None and vertical is not None
                        and horizontal.get('relativeFrom') == 'page'
                        and vertical.get('relativeFrom') == 'page'
                        and anchor.find('wp:wrapNone', ns) is not None
                        and anchor.get('layoutInCell') == '1'):
                    cell.find('w:tcPr/w:vAlign', ns).set(w + 'val', 'top')
                    paragraph = paragraphs[0]
                    properties = paragraph.find('w:pPr', ns)
                    if properties is None:
                        properties = etree.Element(w + 'pPr')
                        paragraph.insert(0, properties)
                    spacing = properties.find('w:spacing', ns)
                    if spacing is None:
                        spacing = etree.SubElement(properties, w + 'spacing')
                    spacing.set(w + 'before', str((int(height.get(w + 'val')) - 324) // 2))
                    spacing.set(w + 'after', '0')
                    spacing.set(w + 'line', '324')
                    spacing.set(w + 'lineRule', 'exact')
                    changed = True
        if not changed:
            return
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as result:
            for item in archive.infolist():
                result.writestr(item, etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                                if item.filename == 'word/document.xml' else archive.read(item.filename))
    output.write_bytes(buffer.getvalue())


def fit_calibration_equipment_table(output, language):
    """Repair generated calibration rows only; keep the pinned vendor unchanged."""
    if language != 'CN':
        return
    from io import BytesIO
    from zipfile import ZipFile
    from lxml import etree
    w = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    with ZipFile(output) as archive:
        root = etree.fromstring(archive.read('word/document.xml'))
        for table in root.iter(w + 'tbl'):
            rows = table.findall(w + 'tr')
            headers = [row for row in rows if len(row.findall(w + 'tc')) == 6
                       and '名称/编号' in ''.join(row.itertext()) and '溯源机构' in ''.join(row.itertext())]
            if len(headers) != 1:
                continue
            header = headers[0]
            # The source generates spacer rows between instruments; they waste
            # a page and let an individual instrument split at the page boundary.
            for row in rows[rows.index(header):]:
                if row is not header and not ''.join(row.itertext()).strip() and not row.findall('.//' + w + 'drawing'):
                    table.remove(row)
                    continue
                props = row.find(w + 'trPr')
                if props is None:
                    props = etree.Element(w + 'trPr'); row.insert(0, props)
                if props.find(w + 'cantSplit') is None:
                    etree.SubElement(props, w + 'cantSplit')
                for height in props.findall(w + 'trHeight'):
                    props.remove(height)
                for index, cell in enumerate(row.findall(w + 'tc')):
                    cp = cell.find(w + 'tcPr')
                    if cp is None:
                        cp = etree.Element(w + 'tcPr'); cell.insert(0, cp)
                    borders = cp.find(w + 'tcBorders')
                    if borders is None:
                        borders = etree.SubElement(cp, w + 'tcBorders')
                    for side in ('top', 'bottom'):
                        edge = borders.find(w + side)
                        if edge is None:
                            edge = etree.SubElement(borders, w + side)
                        edge.set(w + 'val', 'single'); edge.set(w + 'sz', '4')
                    if row is header and index == 2:
                        texts = list(cell.iter(w + 't'))
                        if texts:
                            texts[0].text = '不确定度/准确度等级'
                            for text in texts[1:]: text.text = ''
                    for paragraph in cell.findall(w + 'p'):
                        pp = paragraph.find(w + 'pPr')
                        if pp is None:
                            pp = etree.Element(w + 'pPr'); paragraph.insert(0, pp)
                        spacing = pp.find(w + 'spacing')
                        if spacing is None: spacing = etree.SubElement(pp, w + 'spacing')
                        for key, value in {'before':'40', 'after':'40', 'line':'240', 'lineRule':'auto'}.items():
                            spacing.set(w + key, value)
                        for run in paragraph.findall(w + 'r'):
                            rp = run.find(w + 'rPr')
                            if rp is None:
                                rp = etree.Element(w + 'rPr'); run.insert(0, rp)
                            for key in ('sz', 'szCs'):
                                size = rp.find(w + key)
                                if size is None: size = etree.SubElement(rp, w + key)
                                size.set(w + 'val', '20' if row is header else '18')
        buffer = BytesIO()
        with ZipFile(buffer, 'w') as result:
            for item in archive.infolist():
                result.writestr(item, etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                                if item.filename == 'word/document.xml' else archive.read(item.filename))
    output.write_bytes(buffer.getvalue())


def isolate_pdf_page_objects(writer):
    """Detach mutable page data before supplier watermark/pagination overlays.

    WPS and PyMuPDF may deduplicate identical page streams. pypdf's overlay
    replaces the referenced stream in place, so a shared stream otherwise
    accumulates several pages' numbers and affects their original contents.
    Keep every page's drawing bytes and geometry; make only the mutable
    contents and resource dictionaries private to the page being updated.
    """
    from pypdf.generic import DecodedStreamObject, NameObject
    for page in writer.pages:
        content = page.get_contents()
        if content is not None:
            detached = DecodedStreamObject()
            detached.set_data(content.get_data())
            page[NameObject('/Contents')] = detached
        resources = page.get('/Resources')
        if resources is not None:
            page[NameObject('/Resources')] = resources.get_object().clone(
                writer, force_duplicate=True)


def fit_calibration_pagination(output, language):
    """Move only an identified, out-of-bounds vendor footer text object.

    No redaction, scaling, page resizing or vendor mutation. The pinned vendor
    appends one isolated text object last; refuse unfamiliar output rather than
    changing arbitrary document text. In-bounds pages keep their content stream.
    """
    from io import BytesIO
    import pdfplumber
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ContentStream, FloatObject

    data = output.read_bytes()
    reader = PdfReader(BytesIO(data))
    updates = {}
    with pdfplumber.open(BytesIO(data)) as pdf:
        total = len(pdf.pages)
        for index, page in enumerate(pdf.pages):
            expected = f'Page {index + 1} of {total}'
            pattern = (rf'第\s*{index + 1}\s*页\s*共\s*{total}\s*页\s*\(Page\s+{index + 1}\s+of\s+{total}\)'
                       if language == 'CN' else rf'Page\s+{index + 1}\s+of\s+{total}')
            matches = page.search(pattern, return_chars=False)
            if len(matches) != 1:
                raise ValueError('Calibration pagination cannot be uniquely identified')
            box = matches[0]
            if 0 <= box['x0'] <= box['x1'] <= page.width and 0 <= box['top'] <= box['bottom'] <= page.height:
                continue
            if box['x1'] - box['x0'] > page.width - 40 or box['bottom'] - box['top'] > page.height - 40:
                raise ValueError('Page is too small for the original footer')
            dx = max(20 - box['x0'], min(0, page.width - 20 - box['x1']))
            dy = max(20 - box['top'], min(0, page.height - 20 - box['bottom']))
            stream = ContentStream(reader.pages[index].get_contents(), reader)
            starts = [i for i, (_, op) in enumerate(stream.operations) if op == b'BT']
            if not starts or reader.pages[index].rotation:
                raise ValueError('Unrecognized footer content stream')
            start = starts[-1]
            end = next((i for i in range(start + 1, len(stream.operations)) if stream.operations[i][1] == b'ET'), None)
            if end is None or any(op != b'Q' for _, op in stream.operations[end + 1:]):
                raise ValueError('Unrecognized footer suffix')
            block = stream.operations[start + 1:end]
            if any(op not in {b'Tm', b'Tf', b'TL', b'Tj'} for _, op in block):
                raise ValueError('Unrecognized footer operators')
            texts = ''.join(str(args[0]) for args, op in block if op == b'Tj')
            suffix = '(' + expected + ')' if language == 'CN' else expected
            matrices = [args for args, op in block if op == b'Tm']
            if (not texts.endswith(suffix) or len(matrices) != 1
                    or any(float(args[1]) != 8 for args, op in block if op == b'Tf')):
                raise ValueError('Unrecognized footer text')
            matrix = matrices[0]
            if (list(map(float, matrix[:4])) != [1, 0, 0, 1]
                    or abs(float(matrix[4]) - 420) > .01
                    or abs(float(matrix[5]) - (float(reader.pages[index].cropbox.height) - 800)) > .01):
                raise ValueError('Unrecognized footer matrix')
            matrix[4] = FloatObject(float(matrix[4]) + dx)
            matrix[5] = FloatObject(float(matrix[5]) - dy)
            updates[index] = stream
    if not updates:
        return
    writer = PdfWriter(clone_from=reader)
    for index, stream in updates.items():
        writer.pages[index].replace_contents(stream)
    result = BytesIO()
    writer.write(result)
    writer.close()
    output.write_bytes(result.getvalue())


TRADEMARK_MAX_EDGE = 1600


def run(payload):
    root = Path(__file__).with_name('vendor_docparser_20260911').resolve()
    if Path.cwd().resolve() != root:
        raise ValueError('wrong vendor directory')
    # Existing platform's pinned third-party directory; never a caller path.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_vendor'))
    sys.path.insert(0, str(root))
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied
    operation = payload['operation']
    profile = payload['profile']
    output = Path(payload['output'])
    if operation == 'issue_date':
        spec = importlib.util.spec_from_file_location('_pdf_issue_date', SCRIPT_DIRECTORY / 'pdf_issue_date.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            return {'issueDate': module.finalize(payload['inputs'][0], output, profile,
                                                payload['context'].get('approvalDate'))}
        except ValueError as exc:
            raise FieldError('报告日期核查失败：' + str(exc)) from exc
    if operation == 'pdf':
        from pdf_helper import PdfMaker
        class IsolatedPdfMaker(PdfMaker):
            @classmethod
            def watermark(cls, writer, image, page_indices=None):
                isolate_pdf_page_objects(writer)
                return super().watermark(writer, image, page_indices)

        class WpsEnglishPdfMaker(IsolatedPdfMaker):
            """Caller-owned compatibility; vendor classes and files stay intact."""
            @staticmethod
            def find_text(writer, keyword):
                if keyword == 'No. of Report:':
                    # WPS may omit one/both spaces; the new supplier API is literal.
                    matches = []
                    for text in ('No. of Report:', 'No.of Report:', 'No. ofReport:', 'No.ofReport:'):
                        matches.extend(PdfMaker.find_text(writer, text))
                    unique = {(m['page'], round(m['x0'], 2), round(m['top'], 2),
                               round(m['x1'], 2), round(m['bottom'], 2)): m for m in matches}
                    return [unique[k] for k in sorted(unique)]
                return PdfMaker.find_text(writer, keyword)

        maker = WpsEnglishPdfMaker if profile['language'] == 'EN' else IsolatedPdfMaker
        maker(profile['category'], profile['language'], extended=profile['extended']).make(payload['inputs'], output)
        if profile['category'] == 'Calibration':
            fit_calibration_pagination(output, profile['language'])
        return
    if operation == 'issuance_record':
        from template_helper import IssuanceRecordProduct, IssuanceRecordEngineering
        category = profile['kind']
        code = 'c' if category == 'engineering' else 'a'
        template = root / f'assets/templates/LAB-Record-4229{code}-Standard-202611_tpl.docx'
        cls = IssuanceRecordEngineering if category == 'engineering' else IssuanceRecordProduct
        record = cls(template, IssuanceRecords=payload['context']['IssuanceRecords'])
        record.render(record.context, output)
        return
    demo = root / ('report_demo.py' if operation == 'report' else 'entrust_demo.py')
    allowed = raw_fields(demo)
    # Fixed institutional configuration is absent from raw_context. Empty values
    # cannot erase vendor configuration. False and zero remain meaningful.
    context = {k: v for k, v in payload['context'].items()
               if k in allowed and v is not None and v != ''}
    for field in ('Trademark', 'Signature'):
        value = context.get(field)
        if not isinstance(value, str):
            continue
        if value.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,')):
            raw = base64.b64decode(value.split(',', 1)[1], validate=True)
            if len(raw) > 5 * 1024 * 1024:
                raise ValueError('image too large')
            from PIL import Image
            from io import BytesIO
            with Image.open(BytesIO(raw)) as im:
                im.verify()
            target = output.parent / (field + ('.png' if 'image/png;' in value else '.jpg'))
            if field == 'Trademark':
                # Decode pixels rather than passing legacy EXIF text to python-docx.
                # Stored uploads and reviewer signatures remain unchanged.
                from PIL import ImageOps
                with Image.open(BytesIO(raw)) as im:
                    oriented = ImageOps.exif_transpose(im)
                    oriented.load()
                    has_alpha = 'A' in oriented.getbands() or 'transparency' in oriented.info
                    clean = oriented.convert('RGBA' if has_alpha else 'RGB')
                    clean.info.clear()
                    # The template sizes the picture to its cell, so a bounded
                    # long edge keeps print quality while avoiding oversized files.
                    if max(clean.size) > TRADEMARK_MAX_EDGE:
                        clean.thumbnail((TRADEMARK_MAX_EDGE, TRADEMARK_MAX_EDGE), Image.LANCZOS)
                    dpi = im.info.get('dpi', (72, 72))
                    if not isinstance(dpi, (tuple, list)) or len(dpi) != 2:
                        dpi = (72, 72)
                    dpi = tuple(float(v) if isinstance(v, (int, float)) and 0 < v < 100000 else 72 for v in dpi)
                    if im.getexif().get(274) in (5, 6, 7, 8):
                        dpi = dpi[::-1]
                    if has_alpha or im.format == 'PNG':
                        target = output.parent / 'Trademark.png'
                        clean.save(target, format='PNG', dpi=dpi, optimize=True)
                    else:
                        target = output.parent / 'Trademark.jpg'
                        clean.save(target, format='JPEG', dpi=dpi, quality=92)
            else:
                target.write_bytes(raw)
            context[field] = str(target)
        elif re.search(r'\.(png|jpe?g)$', value, re.I):
            raise ValueError('caller supplied a local asset path')
    if operation == 'report':
        from report_demo import ReportConfig
        center = 'NCSA' if profile['center'] == 'NCAS' else ('LAB' if profile['center'] == 'LAB' else profile['center'])
        # The supplied demo asks for lowercase standard/extended while its
        # immutable assets use Standard/Extended. Resolve only that path here;
        # context and rendering still belong to the vendor's public classes.
        category = profile['kind'].title()
        config = ReportConfig(center, category, profile['language'],
                              profile['variant'] == 'Extended')
        ctx = config.context
        if ctx is None:
            raise RuntimeError('Unknow context')
        ctx.update(context)
        # An explicit NCSA sample choice may omit only CMA. Institution names,
        # CNAS and vendor assets stay fixed; absent historical choices retain
        # their original output. Never accept arbitrary raw CMAText overrides.
        if center == 'NCSA' and (profile.get('requirements') or {}).get('seal') == 'CNAS':
            ctx['CMAText'] = ''
        template = config.template
        if not template:
            candidate = root / 'assets/templates' / (
                f"LAB-Report-{category}-{profile['language']}-{profile['variant']}-202609_tpl.docx")
            if candidate.is_file():
                template = str(candidate)
        if not template:
            raise RuntimeError('The template does not exist')
        if payload.get('conclusion'):
            # Preserve the uploaded DOCX; layout belongs to the vendor subdocument API.
            ctx['Conclusion'] = payload['conclusion']
        if config.instance is None:
            raise RuntimeError('Unknow instance')
        maker = config.instance
        if not payload.get('conclusion'):
            # The protocol distinguishes text from an uploaded DOCX already.
            # Use the vendor's text API instead of stat() on arbitrary prose.
            from template_helper import FontSize
            class TextConclusionMaker(maker):
                @property
                def _conclusion(self):
                    return self.field_paragraph('Conclusion', font_range=(FontSize.L, FontSize.XXXXS))
            maker = TextConclusionMaker
        report = maker(template, **ctx)
        actual = report.context
        capacity_warnings = []
        # Date paragraphs now retain all text; equality alone cannot detect
        # overflow. Use the vendor geometry for a notice, never refit or block.
        if category in ('Product', 'Sampling'):
            from template_helper import TemplateHelper, FontSize
            from template_utils import TemplateGeometry
            geometry = TemplateGeometry(template)
            for field in ('TestDate', 'ManufacturingDate'):
                cells = geometry.find(field)
                value = str(ctx.get(field, ''))
                if len(cells) == 1 and TemplateHelper.get_parastyle(
                        value, cells[0], (FontSize.L, FontSize.XXXXS)) is None:
                    capacity_warnings.append(field)
        if category == 'Calibration':
            # Preserve the existing template alias, using the vendor result.
            actual['BASIS'] = actual['Basis']
        trademark_layout = trademark_image_layout(template, ctx, actual, report)
        if category == 'Sampling':
            # DocParser(7)'s four sampling templates use ArrivalDate, while
            # its public context exposes the formatted SampleArrivalDate.
            # Alias only the rendered value; never substitute another date or
            # edit the immutable vendor templates/business sample data.
            actual['ArrivalDate'] = actual['SampleArrivalDate']
        # Compare the vendor result for notices only; never cut or refit text.
        # A supplied conclusion is a subdocument, not plain text to compare.
        comparable = {k: v for k, v in actual.items()
                      if not (payload.get('conclusion') and k == 'Conclusion')}
        validate_fields(ctx, comparable, capacity_warnings=capacity_warnings)
        report.render(actual, output)
        apply_trademark_image_layout(output, trademark_layout)
        if category == 'Calibration':
            fit_calibration_equipment_table(output, profile['language'])
        return {'capacityWarnings': list(dict.fromkeys(capacity_warnings or [])),
                'noticeCodes': []}
    elif operation == 'entrust':
        from entrust_demo import EntrustConfig
        config = EntrustConfig(profile['kind'].title(), profile.get('variant') == 'Extended')
        if not config.template or config.instance is None:
            raise ValueError('The entrust template does not exist')

        # Quantity/Category now use the supplier's paragraph layout rather
        # than the obsolete fixed 20-display-unit Quantity limit.
        entrust = config.instance(config.template, **context)
        rendered = entrust.context
        if profile.get('outputLanguage', 'CN') != 'CN' and 'SubmissionDate' in rendered:
            # The supplier's 14-unit limit only fits one language.
            rendered['SubmissionDate'] = context.get('SubmissionDate', '')
            from reportlab.pdfbase.pdfmetrics import stringWidth
            from template_helper import FontSize
            from template_utils import TemplateGeometry

            # Allow for cell padding and the Office renderer's line-breaking margin.
            width = min(cell.width_pt for cell in TemplateGeometry(config.template).find('Category')) - 14
            line_width = max(
                sum(stringWidth(char, 'Times-Roman', 1) if char.isascii() else 1 for char in line)
                for line in context.get('Category', '').split('\n')
            )
            category_font = next(
                (font for font in FontSize if font.value <= 10 and font.value * line_width <= width),
                FontSize.XXXS,
            )
            rendered['Category'] = entrust.field_paragraph(
                'Category', font_range=(category_font, FontSize.XXXXS),
            )
        entrust.render(rendered, output)
        if profile.get('variant') == 'Extended':
            align_extended_entrust_item_labels(output)
    else:
        raise ValueError('unsupported operation')


if __name__ == '__main__':
    try:
        with redirect_stdout(StringIO()):
            result = run(json.load(sys.stdin))
        print(json.dumps(result or {}, ensure_ascii=False))
    except FieldError as error:
        # Only known validation messages are returned; vendor logs remain hidden.
        print(json.dumps({'validationError': str(error)}, ensure_ascii=False))
        sys.exit(2)
