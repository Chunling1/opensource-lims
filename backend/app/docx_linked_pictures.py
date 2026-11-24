"""Freeze saved INCLUDEPICTURE results in conversion copies, never fetch links."""
from copy import copy
from io import BytesIO
import posixpath
import re
from zipfile import ZipFile

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
V = 'urn:schemas-microsoft-com:vml'
ERROR = '外部图片链接缺少完整的内嵌图片，或图片域结构不完整；请在 Word/WPS 中将图片保存到文档并解除链接后重新上传'


def _xml(raw):
    root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
    if root.getroottree().docinfo.doctype:
        raise ValueError('Word 文件包含不允许的 XML 声明')
    return root


def _picture_field(code):
    return bool(re.match(r'^\s*INCLUDEPICTURE\b', code, re.I))


def _verify_images(nodes, package, part):
    relpart = posixpath.join(posixpath.dirname(part), '_rels', posixpath.basename(part) + '.rels')
    try:
        rels = _xml(package.read(relpart))
        relationships = {r.get('Id'): r for r in rels}
        if len(relationships) != len(rels):
            raise ValueError(ERROR)
    except (KeyError, etree.XMLSyntaxError) as exc:
        raise ValueError(ERROR) from exc
    images = [n for n in nodes if n.tag in {f'{{{A}}}blip', f'{{{V}}}imagedata'}]
    if not images:
        raise ValueError(ERROR)
    for image in images:
        rid = image.get(f'{{{R}}}embed') if image.tag == f'{{{A}}}blip' else image.get(f'{{{R}}}id')
        rel = relationships.get(rid)
        if (image.get(f'{{{R}}}link') or rel is None
                or rel.get('TargetMode', 'Internal').lower() != 'internal'
                or rel.get('Type') != R + '/image'):
            raise ValueError(ERROR)
        target = rel.get('Target', '')
        if not re.fullmatch(r'media/[^/\\:%?#]+', target):
            raise ValueError(ERROR)
        name = posixpath.join(posixpath.dirname(part), target)
        try:
            if not package.getinfo(name).file_size:
                raise ValueError(ERROR)
        except KeyError as exc:
            raise ValueError(ERROR) from exc


def _drop(node):
    parent = node.getparent()
    if node.tail:
        previous = node.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or '') + node.tail
        else:
            parent.text = (parent.text or '') + node.tail
    parent.remove(node)


def prepare_linked_pictures(blob):
    """Keep images/text/layout; remove only verified picture field instructions.

    All Word XML parts are checked, including headers and footers. Unrelated
    fields and relationships remain intact and the gateway still validates them.
    No network, file writes, or modification of the uploaded source occurs here.
    """
    if not blob.startswith(b'PK'):
        return blob
    with ZipFile(BytesIO(blob)) as package:
        entries = package.infolist()
        if (len(entries) > 2000 or sum(e.file_size for e in entries) > 100 * 1024 * 1024
                or len({e.filename for e in entries}) != len(entries)):
            raise ValueError('Word 文件解压规模超限或包含重复部件')
        if 'word/document.xml' not in package.namelist():
            return blob
        changes = {}
        for part in package.namelist():
            if not part.startswith('word/') or not part.endswith('.xml'):
                continue
            raw = package.read(part)
            root = _xml(raw)
            # Decode XML before testing so split instructions and XML entities
            # cannot make a picture field invisible to the conversion step.
            instructions = ''.join(n.text or '' for n in root.iter(f'{{{W}}}instrText'))
            simple = list(root.iter(f'{{{W}}}fldSimple'))
            if 'INCLUDEPICTURE' not in instructions.upper() and not any(
                    _picture_field(n.get(f'{{{W}}}instr', '')) for n in simple):
                continue
            stack, fields, malformed = [], [], False
            for node in root.iter():
                if node.tag == f'{{{W}}}fldChar':
                    kind = node.get(f'{{{W}}}fldCharType')
                    if kind == 'begin':
                        for field in stack:
                            field['nested'] = True
                        stack.append(dict(code='', controls=[node], result=[], separated=False,
                                          nested=bool(stack)))
                    elif kind == 'separate':
                        if not stack or stack[-1]['separated']:
                            malformed = True
                        else:
                            stack[-1]['separated'] = True
                            stack[-1]['controls'].append(node)
                    elif kind == 'end':
                        if not stack:
                            malformed = True
                        else:
                            field = stack.pop()
                            field['controls'].append(node)
                            fields.append(field)
                elif node.tag == f'{{{W}}}instrText' and stack:
                    field = stack[-1]
                    if field['separated']:
                        malformed = True
                    field['code'] += node.text or ''
                    field['controls'].append(node)
                for field in stack:
                    if field['separated']:
                        field['result'].append(node)
            if malformed or stack:
                raise ValueError(ERROR)
            changed = False
            for field in fields:
                if not _picture_field(field['code']):
                    continue
                if field['nested'] or not field['separated']:
                    raise ValueError(ERROR)
                _verify_images(field['result'], package, part)
                for node in field['controls']:
                    _drop(node)
                changed = True
            for node in simple:
                if not _picture_field(node.get(f'{{{W}}}instr', '')):
                    continue
                if any(n.tag in {f'{{{W}}}fldSimple', f'{{{W}}}fldChar'} for n in node.iterdescendants()):
                    raise ValueError(ERROR)
                if any(n.tag == f'{{{W}}}fldSimple' for n in node.iterancestors()):
                    raise ValueError(ERROR)
                _verify_images(list(node.iterdescendants()), package, part)
                parent, index = node.getparent(), node.getparent().index(node)
                for child in list(node):
                    parent.insert(index, child)
                    index += 1
                _drop(node)
                changed = True
            if changed:
                changes[part] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        if not changes:
            return blob
        output = BytesIO()
        with ZipFile(output, 'w') as result:
            for entry in package.infolist():
                result.writestr(copy(entry), changes.get(entry.filename, package.read(entry)))
        return output.getvalue()
