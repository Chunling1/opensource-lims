"""Project localized entrust values and fill the supplier's testing-location cell.

The original maker has no public TestPlace field. No template/source mutation,
no table geometry changes, and no silent clipping or reuse of signed output.
"""
from io import BytesIO
from math import ceil
from zipfile import ZipFile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
_ENTRUST_CATEGORY_EN = {'抽样': 'Sampling', '校准': 'Calibration',
                        '委托型式检验': 'Commissioned Type Inspection'}


def localized_entrust_fields(detail, category, send_date, language, *, category_separator=' / '):
    from .report_date_display import production_date_text, report_date
    from .report_english_fields import english_category

    def display(chinese, english, separator=' / '):
        if language == 'EN':
            return english
        return separator.join(dict.fromkeys(filter(None, (chinese, english))))

    chinese_production = production_date_text(detail)
    english_production = production_date_text(detail, language='EN')
    if not ((detail or {}).get('rawSample') or {}).get('productionDates'):
        chinese_production = report_date(chinese_production)
        english_production = report_date(english_production, language='EN')
    return {
        'Category': display(category, _ENTRUST_CATEGORY_EN.get(category) or english_category(category),
                            category_separator),
        'ManufacturingDate': '\n'.join(display(cn, en) for cn, en in
                                      zip(chinese_production.split('\n'), english_production.split('\n'))),
        'SubmissionDate': display(send_date, report_date(send_date, language='EN')),
    }


def fill_testing_location(blob, location):
    location = str(location or '').strip()
    if not location:
        return blob, {'changedParts': [], 'locationCells': 0}
    with ZipFile(BytesIO(blob)) as source:
        infos = source.infolist()
        parts = {info.filename: source.read(info.filename) for info in infos}
    root = etree.fromstring(parts['word/document.xml'], parser=etree.XMLParser(resolve_entities=False))
    found = []
    for row in root.xpath('.//w:tr', namespaces=NS):
        cells = row.xpath('./w:tc', namespaces=NS)
        for index, cell in enumerate(cells[:-1]):
            label = ''.join(cell.xpath('.//w:t/text()', namespaces=NS))
            if ''.join(label.split()) == '检测地点':
                target = cells[index + 1]
                if ''.join(target.xpath('.//w:t/text()', namespaces=NS)).strip():
                    raise ValueError('委托单检测地点目标不为空，请核对新版模板接口')
                paragraphs = target.xpath('./w:p', namespaces=NS)
                if len(paragraphs) != 1:
                    raise ValueError('委托单检测地点结构已变化')
                width = float(target.xpath('./w:tcPr/w:tcW/@w:w', namespaces=NS)[0]) / 20 - 12
                height = float(row.xpath('./w:trPr/w:trHeight/@w:val', namespaces=NS)[0]) / 20 - 4
                # Conservative full-width bound; fail rather than omit addresses.
                font = next((size / 2 for size in range(21, 11, -1)
                             if sum(max(1, ceil(len(line) * (size / 2) / width))
                                    for line in location.split('\n')) * size / 2 * 1.2 <= height), None)
                if font is None:
                    raise ValueError('委托单检测地点过长，固定区域无法完整显示；请核对地址或使用合适模板')
                p = paragraphs[0]
                props = p.find(f'{{{W}}}pPr')
                if props is None:
                    props = etree.Element(f'{{{W}}}pPr'); p.insert(0, props)
                for old in props.findall(f'{{{W}}}spacing'):
                    props.remove(old)
                spacing = etree.SubElement(props, f'{{{W}}}spacing')
                for name, value in [('before','0'), ('after','0'), ('line','240'), ('lineRule','auto')]:
                    spacing.set(f'{{{W}}}{name}', value)
                run = etree.SubElement(p, f'{{{W}}}r')
                rpr = etree.SubElement(run, f'{{{W}}}rPr')
                for name in ('sz', 'szCs'):
                    etree.SubElement(rpr, f'{{{W}}}{name}').set(f'{{{W}}}val', str(int(font * 2)))
                for n, line in enumerate(location.split('\n')):
                    if n: etree.SubElement(run, f'{{{W}}}br')
                    text = etree.SubElement(run, f'{{{W}}}t')
                    text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                    text.text = line
                found.append(font)
    if len(found) != 1:
        raise ValueError('委托单检测地点栏无法唯一定位')
    parts['word/document.xml'] = etree.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)
    output = BytesIO()
    with ZipFile(output, 'w') as target:
        for info in infos: target.writestr(info, parts[info.filename])
    return output.getvalue(), {'changedParts': ['word/document.xml'], 'locationCells': len(found), 'fontSizes': found}
