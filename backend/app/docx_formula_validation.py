"""Read-only DOCX checks: permit embedded MathType equations, not arbitrary OLE."""
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
import re
import struct
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree
from ._vendor_olefile import OleFileIO, DEFECT_INCORRECT

O_NS = 'urn:schemas-microsoft-com:office:office'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
EQUATION_CLSID = '0002CE03-0000-0000-C000-000000000046'
ERROR = 'Word 文件含不支持或损坏的嵌入对象；仅支持普通 MathType 公式，请将其他对象转为图片或原生 Word 内容'


def _xml(package, name):
    root = etree.fromstring(package.read(name), etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False))
    if root.getroottree().docinfo.doctype:
        raise ValueError('Word 文件包含不允许的 XML 声明')
    return root


def _equation(blob):
    if len(blob) > 2 * 1024 * 1024:
        raise ValueError(ERROR)
    try:
        with OleFileIO(BytesIO(blob), raise_defects=DEFECT_INCORRECT) as ole:
            required = {'\x01CompObj', 'Equation Native'}
            allowed = required | {'\x01Ole', '\x03ObjInfo'}
            paths = ole.listdir(streams=True, storages=True)
            if (ole.root.clsid != EQUATION_CLSID
                    or any(len(p) != 1 or p[0] not in allowed for p in paths)
                    or not required <= {p[0] for p in paths}):
                raise ValueError(ERROR)
            # Validate every stream chain, not just the container signature.
            streams = {p[0]: ole.openstream(p).read() for p in paths}
            comp = streams['\x01CompObj']
            if b'Equation.DSMT4\x00' not in comp or b'MathType' not in comp:
                raise ValueError(ERROR)
            native = streams['Equation Native']
            # MathType's EQNOLEFILEHDR precedes MTEF equation data.
            if (len(native) < 29 or struct.unpack_from('<I', native)[0] != 28
                    or struct.unpack_from('<I', native, 8)[0] != len(native) - 28
                    or native[28] not in (3, 4, 5)):
                raise ValueError(ERROR)
    except Exception as exc:
        raise ValueError(ERROR) from exc


def validate_embedded_members(package):
    """Do not execute or rewrite embedded objects; return verified part names."""
    entries = package.infolist()
    names = [e.filename for e in entries]
    if not names or len(names) > 4096 or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
        raise ValueError('Word 文件解压规模超过模块处理上限')
    if len(set(names)) != len(names):
        raise ValueError('Word 文件含重复部件')
    for name in names:
        lower = name.lower()
        if (name.startswith('/') or '..' in PurePosixPath(name).parts or '\\' in name
                or 'vbaproject' in lower or lower.startswith('word/activex/')
                or lower.endswith(('.vba', '.exe', '.js', '.dll', '.com', '.bat', '.cmd'))):
            raise ValueError('上传的 DOCX 包含不允许的成员')
    objects = {n for n in names if n.lower().startswith('word/embeddings/') and not n.endswith('/')}
    binaries = {n for n in names if n.lower().endswith('.bin')}
    if binaries - objects:
        raise ValueError('上传的 DOCX 包含不允许的成员')
    verified = set()
    try:
        for name in names:
            if not name.startswith('word/') or not name.endswith('.xml'):
                continue
            root = _xml(package, name)
            ole_objects = list(root.iter('{%s}OLEObject' % O_NS))
            if not ole_objects:
                continue
            rel_name = posixpath.join(posixpath.dirname(name), '_rels', posixpath.basename(name) + '.rels')
            rels = _xml(package, rel_name)
            relationships = {}
            for rel in rels:
                key = rel.get('Id')
                if key in relationships:
                    raise ValueError(ERROR)
                relationships[key] = rel
            for obj in ole_objects:
                if obj.get('ProgID') != 'Equation.DSMT4' or obj.get('Type') != 'Embed':
                    raise ValueError(ERROR)
                rel = relationships.get(obj.get('{%s}id' % R_NS))
                if (rel is None or rel.tag != '{%s}Relationship' % P_NS
                        or rel.get('TargetMode', 'Internal') != 'Internal'
                        or rel.get('Type') != R_NS + '/oleObject'):
                    raise ValueError(ERROR)
                target = rel.get('Target', '')
                if not re.fullmatch(r'embeddings/[^/\\:%?#]+\.bin', target):
                    raise ValueError(ERROR)
                part = posixpath.join(posixpath.dirname(name), target)
                if part not in objects:
                    raise ValueError(ERROR)
                if part not in verified:
                    _equation(package.read(part))
                    verified.add(part)
        if objects != verified:
            raise ValueError(ERROR)
    except (KeyError, etree.XMLSyntaxError) as exc:
        raise ValueError(ERROR) from exc
    return verified


def prepare_math_for_conversion(blob):
    """Use the saved equation display for PDF only; retain the uploaded original.

    The remote WPS gateway deliberately rejects OLE. A verified MathType object
    is therefore replaced by its own stored VML image in this transient copy.
    Never synthesize a formula, execute OLE, or accept an object without a display.
    """
    if not blob.startswith(b'PK'):
        return blob
    with ZipFile(BytesIO(blob)) as package:
        names = package.namelist()
        if 'word/document.xml' not in names:
            return blob
        if not any(n.lower().startswith('word/embeddings/') and not n.endswith('/') for n in names):
            return blob
        verified = validate_embedded_members(package)
        changes = {}
        used = set()
        w_ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        v_ns = 'urn:schemas-microsoft-com:vml'
        for name in names:
            if not name.startswith('word/') or not name.endswith('.xml'):
                continue
            root = _xml(package, name)
            objects = list(root.iter('{%s}OLEObject' % O_NS))
            if not objects:
                continue
            rel_name = posixpath.join(posixpath.dirname(name), '_rels', posixpath.basename(name) + '.rels')
            rels = _xml(package, rel_name)
            relationships = {r.get('Id'): r for r in rels}
            remove_ids = set()
            for obj in objects:
                container = obj.getparent()
                if container.tag != '{%s}object' % w_ns:
                    raise ValueError('MathType 公式缺少可用于 PDF 的显示图，请用 Word 或 WPS 更新公式显示后保存')
                shapes = [c for c in container if c.tag == '{%s}shape' % v_ns]
                if len(shapes) != 1 or shapes[0].get('id') != obj.get('ShapeID'):
                    raise ValueError('MathType 公式显示图与公式对象不一致')
                images = list(shapes[0].iter('{%s}imagedata' % v_ns))
                if len(images) != 1:
                    raise ValueError('MathType 公式缺少显示图，请更新公式显示后保存')
                image_rel = relationships.get(images[0].get('{%s}id' % R_NS))
                if (image_rel is None or image_rel.get('TargetMode', 'Internal') != 'Internal'
                        or image_rel.get('Type') != R_NS + '/image'):
                    raise ValueError('MathType 公式显示图必须保存在文档内部')
                target = image_rel.get('Target', '')
                if not re.fullmatch(r'media/[^/\\:%?#]+\.(?:wmf|emf|png|jpe?g)', target, re.I):
                    raise ValueError('MathType 公式显示图格式不受支持')
                image_part = posixpath.join(posixpath.dirname(name), target)
                if image_part not in names or not package.getinfo(image_part).file_size:
                    raise ValueError('MathType 公式显示图丢失')
                rid = obj.get('{%s}id' % R_NS)
                used.add(posixpath.join(posixpath.dirname(name), relationships[rid].get('Target')))
                remove_ids.add(rid)
                picture = etree.Element('{%s}pict' % w_ns)
                for child in container:
                    if child is not obj:
                        picture.append(deepcopy(child))
                picture.tail = container.tail
                container.getparent().replace(container, picture)
            for rel in list(rels):
                if rel.get('Id') in remove_ids:
                    rels.remove(rel)
            changes[name] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            changes[rel_name] = etree.tostring(rels, xml_declaration=True, encoding='UTF-8', standalone=True)
        if used != verified:
            raise ValueError('MathType 公式显示图不完整，已停止转换')
        types = _xml(package, '[Content_Types].xml')
        for content_type in list(types):
            if (content_type.get('PartName', '').lstrip('/') in verified
                    or content_type.get('Extension', '').lower() == 'bin'):
                types.remove(content_type)
        changes['[Content_Types].xml'] = etree.tostring(types, xml_declaration=True, encoding='UTF-8', standalone=True)
        out = BytesIO()
        with ZipFile(out, 'w', ZIP_DEFLATED) as result:
            for entry in package.infolist():
                if entry.filename not in verified and not (entry.is_dir() and entry.filename.lower().startswith('word/embeddings/')):
                    result.writestr(entry, changes.get(entry.filename, package.read(entry)))
        return out.getvalue()
