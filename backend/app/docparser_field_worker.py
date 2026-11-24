"""Isolated adapter for the byte-identical user package. No Flask or DB access."""
from copy import deepcopy
import base64
import binascii
from io import BytesIO
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree

ROOT = Path(__file__).with_name('docparser_original_202609')
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
ALIASES = {'SAMPLENAME': 'SampleName', 'CLIENT': 'Client', 'MANUFACTURER': 'Manufacturer',
           'CATEGORY': 'Category', 'INSPECTEDUNIT': 'InspectedUnit', 'MODEL': 'Model',
           'SERIAL': 'Serial', 'CLIENTADDRESS': 'ClientAddress', 'PLACE': 'Place',
           'ArrivalDate': 'SampleArrivalDate', 'BASIS': 'Basis'}
FILES = {
    'product': (
        'LAB-Report-Product-CN-Standard-202609_tpl.docx',
        'LAB-Report-Product-CN-Extended-202609_tpl.docx',
        'LAB-Report-Product-EN-Standard-202609_tpl.docx',
        'LAB-Report-Product-EN-Extended-202609_tpl.docx',
    ),
    'sampling': (
        'LAB-Report-Sampling-CN-Standard-202609_tpl.docx',
        'LAB-Report-Sampling-CN-Extended-202609_tpl.docx',
        'LAB-Report-Sampling-EN-Standard-202609_tpl.docx',
        'LAB-Report-Sampling-EN-Extended-202609_tpl.docx',
    ),
    'engineering': (
        'LAB-Report-Engineering-CN-Standard-202609_tpl.docx',
        'LAB-Report-Engineering-EN-Standard-202609_tpl.docx',
    ),
    'inspection': (
        'LAB-Report-Inspection-CN-Standard-202609_tpl.docx',
        'LAB-Report-Inspection-EN-Standard-202609_tpl.docx',
    ),
    'calibration': ('LAB-Report-Calibration-CN-Standard-202609_tpl.docx',),
    'entrust-product': ('LAB-Entrust-4204d-202601_tpl.docx',),
    'entrust-engineering': ('LAB-Entrust-4204g-202601_tpl.docx',),
}

REPORT_CONFIG_META = '__DocParserReportConfig'
REPORT_FIXED_KEYS = {
    'CMAText', 'CNASText', 'CoverFooter', 'PageHeader',
    'BusinessTel', 'Fax', 'Email',
}
REPORT_RAW_CONTEXT_KEYS = {
    'ReportNo', 'SampleName', 'Client', 'Manufacturer', 'Trademark', 'Model',
    'Serial', 'Place', 'EngineeringName', 'SampleNo', 'Category', 'Quantity',
    'SampleCondition', 'ManufacturingDate', 'EntrustDate', 'SubmissionDate',
    'TestDate', 'ClientAddress', 'Basis', 'Criteria', 'Items', 'Instruments',
    'Conclusion', 'ReportDate', 'Remark', 'ReportQRCode', 'AccountQRCode',
    'OriginalReportDate', 'SampleArrivalDate', 'SamplingUnit', 'SamplingDate',
    'Sampler', 'SamplingQuantity', 'SamplingPlace', 'SamplingBase',
    'SealingInspector', 'SealingCondition', 'TaskSource', 'SampleGrade',
    'InspectedUnit', 'CalibrationDate', 'Temperature', 'Humidity', 'Pressure',
}


class FieldError(ValueError):
    pass


class FieldCapacityError(FieldError):
    def __init__(self, message, field):
        super().__init__(message)
        self.field = field


def parse(blob):
    return etree.fromstring(blob, parser=etree.XMLParser(resolve_entities=False, no_network=True))


def xml_bytes(root):
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)


def text(node):
    return ''.join(node.xpath('.//w:t/text()', namespaces=NS))


def signature(node, normalize=False):
    attrs = dict(node.attrib)
    if normalize:
        attrs.pop('{http://www.w3.org/XML/1998/namespace}space', None)
        if node.tag.endswith('}docPr'):
            attrs.pop('id', None)
    return (node.tag, tuple(sorted(attrs.items())), node.text or '',
            tuple(signature(child, normalize) for child in node))


def restore_and_check(before, after):
    templated_rows = set()
    for table in before.xpath('.//w:tbl', namespaces=NS):
        active = False
        for row in table.xpath('./w:tr', namespaces=NS):
            row_text = text(row)
            if re.search(r'{%tr\s+(?:for|if)\b', row_text):
                active = True
            if active:
                templated_rows.add(row)
            if re.search(r'{%tr\s+end(?:for|if)\b', row_text):
                active = False

    def in_templated_row(node):
        return any(ancestor in templated_rows for ancestor in node.iterancestors('{%s}tr' % NS['w']))

    def is_subsequence(left, right):
        iterator = iter(right)
        return all(any(candidate == item for candidate in iterator) for item in left)

    counts = {}
    for tag in ('drawing', 'pict', 'p'):
        fixed = [node for node in before.xpath('.//w:' + tag, namespaces=NS)
                 if not in_templated_row(node)
                 and '{{' not in text(node) and '{%' not in text(node)]
        for node in fixed:
            # Restore only serializer changes made by docxtpl outside slots.
            candidates = after.xpath('.//w:' + tag, namespaces=NS)
            wanted = sum(signature(n) == signature(node) for n in fixed)
            while sum(signature(n) == signature(node) for n in candidates) < wanted:
                replacement = next((n for n in candidates if signature(n, True) == signature(node, True)
                                    and signature(n) != signature(node)), None)
                if replacement is None:
                    sample = text(node).strip()[:30] or '<blank>'
                    raise FieldError(f'模板非字段段落或图形（{tag}:{sample}）发生变化，已阻止生成')
                replacement.getparent().replace(replacement, deepcopy(node))
                candidates = after.xpath('.//w:' + tag, namespaces=NS)
        counts[tag] = len(fixed)
    for tag in ('sectPr', 'tblPr', 'tblGrid', 'trPr', 'tcPr', 'instrText', 'fldChar'):
        left = [signature(n) for n in before.xpath('.//w:' + tag, namespaces=NS)
                if not in_templated_row(n)]
        right = [signature(n) for n in after.xpath('.//w:' + tag, namespaces=NS)]
        if (left != right if not templated_rows else not is_subsequence(left, right)):
            raise FieldError('模板布局或页码域发生变化，已阻止生成')
        counts[tag] = len(left)
    return counts


def merge_image_relationships(original, generated, existing_names, new_names):
    before, after = parse(original), parse(generated)
    if before.tag != after.tag:
        raise FieldError('图片关联格式异常')
    result = deepcopy(before)
    keys = {node.get('Id'): node for node in before}
    for node in after:
        key = node.get('Id')
        if key in keys:
            if signature(node) != signature(keys[key]):
                raise FieldError('原模板图片或外部关联被改写')
            continue
        target = node.get('Target', '')
        full = 'word/' + target
        if (not node.get('Type', '').endswith('/image') or node.get('TargetMode')
                or not target.startswith('media/') or '..' in PurePosixPath(target).parts
                or full not in existing_names | new_names):
            raise FieldError('新字段包含不允许的文件关联')
        result.append(deepcopy(node))
    if not set(keys).issubset({node.get('Id') for node in after}):
        raise FieldError('原模板关联缺失')
    return xml_bytes(result)


def preserve_package(template, generated, output, entity):
    checks, changed = {}, []
    with ZipFile(template) as source, ZipFile(generated) as filled:
        original_names, rendered_names = set(source.namelist()), set(filled.namelist())
        added = rendered_names - original_names
        if original_names - rendered_names or any(not re.fullmatch(r'word/media/[^/]+\.(png|jpe?g)', n) for n in added):
            raise FieldError('原包成员缺失或新增了非字段资源')
        result = {name: source.read(name) for name in source.namelist()}
        for name, blob in list(result.items()):
            if re.fullmatch(r'word/(document|header[0-9]+|footer[0-9]+)\.xml', name) and (b'{{' in blob or b'{%' in blob):
                before, after = parse(blob), parse(filled.read(name))
                checks[name] = restore_and_check(before, after)
                result[name] = xml_bytes(after)
                # Placeholder-looking user text is escaped by docxtpl; only
                # original template field tokens must have been rendered.
                changed.append(name)
            elif name.startswith('word/_rels/') and name.endswith('.rels'):
                if filled.read(name) != blob:
                    result[name] = merge_image_relationships(blob, filled.read(name), original_names, added)
                    changed.append(name)
        if added:
            original_types, rendered_types = parse(result['[Content_Types].xml']), parse(filled.read('[Content_Types].xml'))
            for node in rendered_types:
                if any(signature(node) == signature(n) for n in original_types):
                    continue
                if not node.tag.endswith('}Default') or node.get('Extension') not in ('png', 'jpg', 'jpeg') or node.get('ContentType') not in ('image/png', 'image/jpeg'):
                    raise FieldError('字段资源类型不允许')
                original_types.append(deepcopy(node))
            result['[Content_Types].xml'] = xml_bytes(original_types)
            changed.append('[Content_Types].xml')
        for name in added:
            result[name] = filled.read(name)
        # Page fields are preserved. Request cache recalculation, not hardcoded numbers.
        settings = parse(result['word/settings.xml'])
        field = settings.find('w:updateFields', NS)
        if field is None:
            field = etree.SubElement(settings, '{' + NS['w'] + '}updateFields')
        field.set('{' + NS['w'] + '}val', 'true')
        result['word/settings.xml'] = xml_bytes(settings)
        changed.append('word/settings.xml')
        with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
            for name, blob in result.items():
                archive.writestr(name, blob)
    body_guide = '内容编写说明' in text(parse(result['word/document.xml']))
    return {'checks': checks, 'changedParts': changed, 'addedMedia': sorted(added),
            'templateSha256': hashlib.sha256(template.read_bytes()).hexdigest(),
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'entity': entity, 'bodyGuideRetained': body_guide,
            'completeReport': entity == 'entrust',
            'pageFields': 'preserved; update requested; PDF pagination not yet verified'}


def validate_fields(context, actual, *, capacity_warnings=None):
    image_keys = {'CMAMark', 'CNASMark', 'ReportQRCode', 'AccountQRCode', 'Trademark'}
    for key, value in actual.items():
        if key in image_keys:
            continue
        if key == 'AmountInWords':
            # This is deterministically derived by the unmodified maker from Amount.
            continue
        if key == 'INSTRUMENTS':
            source = context.get('Instruments', '').split('\t')
            expected_rows = [
                dict(zip(('nam', 'rng', 'spc', 'crt', 'trc', 'exp'), source[index:index + 6]))
                for index in range(0, len(source) - len(source) % 6, 6)
            ]
            if not isinstance(value, list) or value[:len(expected_rows)] != expected_rows:
                raise FieldError('字段 Instruments 校准设备表映射不一致；未生成报告')
            if any(any(row.get(name) for name in ('rng', 'spc', 'crt', 'trc', 'exp'))
                   for row in value[len(expected_rows):] if isinstance(row, dict)):
                raise FieldError('字段 Instruments 校准设备表包含非填充行；未生成报告')
            continue
        expected_key = ALIASES.get(key, key)
        expected = context.get(expected_key, '')
        if key == 'Serial' and 'TECHNIQUE' in context:
            expected = '\n'.join((context.get('ManufacturingDate', ''), context.get('Serial', '')))
        elif key == 'Amount':
            try:
                expected = f"{float(context.get('Amount', '0')):.2f}"
            except (TypeError, ValueError):
                expected = '0.00'
        if isinstance(value, bool):
            if value is not bool(expected):
                raise FieldError(f'字段 {key} 布尔值不一致；未生成文件')
            continue
        if isinstance(value, str):
            rendered = value
        else:
            root = parse(('<root xmlns:w="' + NS['w'] + '">' + str(value) + '</root>').encode())
            rendered = '\n'.join(''.join(n.text or '' if n.tag.endswith('}t') else '\n' if n.tag.endswith('}br') else '\t' if n.tag.endswith('}tab') else '' for n in p.iter()) for p in root.xpath('.//w:p', namespaces=NS))
        if rendered != expected.replace('\r\n', '\n').replace('\r', '\n'):
            if capacity_warnings is not None:
                capacity_warnings.append(key)
            else:
                raise FieldCapacityError(f'字段 {key} 超出原模板容量或被截断；未生成报告', key)


def run(kind, filename, output, context):
    if filename not in FILES.get(kind, ()):
        raise FieldError('原包模板型号不明确')
    if not isinstance(context, dict):
        raise FieldError('模板字段须为对象')
    context = dict(context)
    report_config = context.pop(REPORT_CONFIG_META, None)
    if not isinstance(context, dict) or any(
            not isinstance(k, str) or not isinstance(v, (str, bool))
            for k, v in context.items()):
        raise FieldError('模板字段须为文本或布尔值')
    # The unmodified demo treats these fields as optional filesystem paths.
    # Public business text must never cause it to read an arbitrary local file.
    trademark_data = context.get('Trademark', '')
    for key in ('Trademark', 'Conclusion'):
        value = context.get(key, '')
        if key == 'Trademark' and value.startswith('data:image/'):
            continue
        if re.search(r'\.(docx|png|jpe?g)$', value, re.I):
            raise FieldError(f'字段 {key} 不接受本地文件路径')
    if trademark_data.startswith('data:image/'):
        match = re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=\r\n]+)', trademark_data)
        if not match:
            raise FieldError('商标图样仅支持 PNG 或 JPEG')
        try:
            image_blob = base64.b64decode(match.group(2), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise FieldError('商标图样数据无效') from exc
        if not image_blob or len(image_blob) > 2 * 1024 * 1024:
            raise FieldError('商标图样须小于 2MB')
        try:
            from PIL import Image
            with Image.open(BytesIO(image_blob)) as opened:
                opened.verify()
            with Image.open(BytesIO(image_blob)) as opened:
                if opened.width < 1 or opened.height < 1 or opened.width * opened.height > 16_000_000:
                    raise FieldError('商标图样尺寸无效')
                normalized = opened.convert('RGBA' if opened.mode in ('RGBA', 'LA') else 'RGB')
                trademark_path = output.with_name('trademark.png')
                normalized.save(trademark_path, format='PNG', optimize=True)
        except FieldError:
            raise
        except Exception as exc:
            raise FieldError('商标图样不是有效的 PNG/JPEG 文件') from exc
        context['Trademark'] = str(trademark_path)
    sys.path.insert(0, str(ROOT))
    from report_maker import ReportProduct, ReportSampling, ReportEngineering, ReportInspection, ReportCalibration
    from entrust_maker import EntrustProduct, EntrustProject
    classes = dict(product=ReportProduct, sampling=ReportSampling, engineering=ReportEngineering,
                   inspection=ReportInspection, calibration=ReportCalibration,
                   **{'entrust-product': EntrustProduct, 'entrust-engineering': EntrustProject})
    entity = 'entrust' if kind.startswith('entrust-') else 'report'
    fixed_context = {}
    if entity == 'report':
        if set(context) - REPORT_RAW_CONTEXT_KEYS:
            raise FieldError('平台仅可替换 report_demo.raw_context 中定义的报告字段')
        if REPORT_FIXED_KEYS & set(context):
            raise FieldError('平台不得覆盖 DocParser 固定机构配置')
        if not isinstance(report_config, dict) or set(report_config) != {
                'center', 'category', 'language', 'extended'}:
            raise FieldError('DocParser 报告配置不完整')
        center = str(report_config['center']).upper()
        center = 'NCSA' if center == 'NCAS' else center
        category = str(report_config['category']).capitalize()
        language = str(report_config['language']).upper()
        extended = report_config['extended']
        if (center not in {'LAB', 'NCSA'}
                or category.lower() != kind
                or language not in {'CN', 'EN'}
                or not isinstance(extended, bool)):
            raise FieldError('DocParser 报告配置与模板选择不一致')
        expected_variant = 'Extended' if extended else 'Standard'
        expected_filename = (
            f'LAB-Report-{category}-{language}-{expected_variant}-202609_tpl.docx'
        )
        if filename != expected_filename:
            raise FieldError('DocParser 报告配置与模板文件不一致')
        from report_demo import ReportConfig
        configured = ReportConfig(center, category, language, extended).context
        if configured is None:
            raise FieldError('DocParser 原始配置不支持该中心与报告类别')
        fixed_context = deepcopy(configured)
        if set(fixed_context) != REPORT_FIXED_KEYS:
            raise FieldError('DocParser 固定机构配置字段发生变化')
        # The original demo applies the fixed ReportConfig first and then only
        # overlays raw_context.  The platform deliberately mirrors that flow;
        # blank business fields can never erase fixed institution settings.
        maker_context = {**fixed_context, **context}
    else:
        if report_config is not None:
            raise FieldError('委托单不接受报告配置')
        maker_context = context
    template = ROOT / 'templates' / filename
    maker = classes[kind](template, **maker_context)
    actual = maker.context
    # The supplied templates and maker use different names for these slots.
    # Adapt the existing names, without editing the user's source/template.
    required = maker._template.get_undeclared_template_variables()
    if 'ArrivalDate' in required:
        actual['ArrivalDate'] = actual['SampleArrivalDate']
    if 'BASIS' in required:
        actual['BASIS'] = maker_context.get('Basis', '')
    validate_fields(maker_context, actual)
    if required - actual.keys():
        raise FieldError('原包字段映射不完整')
    intermediate = output.with_name(output.stem + '-maker.docx')
    maker.render(actual, intermediate)
    audit = preserve_package(template, intermediate, output, entity)
    if entity == 'report':
        audit['contextPolicy'] = {
            'source': 'report_demo.ReportConfig + raw_context',
            'fixedKeys': sorted(fixed_context),
            'rawKeys': sorted(context),
            'blankFixedOverrideBlocked': True,
        }
    with ZipFile(output) as archive:
        for name in archive.namelist():
            if re.fullmatch(r'word/(document|header[0-9]+|footer[0-9]+)\.xml', name):
                source_part = ZipFile(template)
                try:
                    had_number = re.search(r'\{\{\s*ReportNo\s*\}\}', text(parse(source_part.read(name))))
                finally:
                    source_part.close()
                if had_number and maker_context['ReportNo'] not in text(parse(archive.read(name))):
                    raise FieldError('正文或页眉中的报告编号未完整写入')
    return audit


if __name__ == '__main__':
    try:
        result = run(sys.argv[1], sys.argv[2], Path(sys.argv[3]), json.load(sys.stdin))
    except FieldError as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        sys.exit(2)
    except Exception:
        print(json.dumps({'error': '原包字段填充失败，请检查字段容量、模板依赖及文件'}, ensure_ascii=False))
        sys.exit(3)
    print(json.dumps(result, ensure_ascii=False))
