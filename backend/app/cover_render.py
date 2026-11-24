"""按真实模板渲染报告封面+首页（示例中心 2026 版模板）。

模板放在 cover_templates/（由 .doc 转 docx）。按「检测中心 × 报告类型」选模板，
首页是「标签单元格」表格——找到标签格（样品名称/委托单位/检测依据…）后把相邻空格填上委托+样品+检测信息。
差异化规则见 各中心报告封面及首页模板分类&差异化规则汇总表。
"""
import base64
import copy
import glob
import hashlib
import json
import os
import re
from io import BytesIO

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Inches, Pt

from .covers import _field

TPL_DIR = os.path.join(os.path.dirname(__file__), "cover_templates")
TPL_MANIFEST = os.path.join(TPL_DIR, "manifest.json")
COVER_RENDERER_RELEASE = "2026-07-trademark-r1-dates-cn-20261014"

# 报告编号前缀 → 中心名（与模板文件名一致）
PREFIX_CENTER = {
    "NCSA": "空调中心", "NCAS": "空调中心",
    "LAB": "示例中心",
}


def _center_from_report(report):
    prefix = (report.report_no or "").split("-")[0]
    return PREFIX_CENTER.get(prefix, "示例中心")


def _find(*patterns):
    for pat in patterns:
        hits = sorted(glob.glob(os.path.join(TPL_DIR, pat)))
        if hits:
            return hits[0]
    return None


def _cover_center(center):
    return center


def _homepage_center(center):
    return center


def select_templates(center, report_type):
    """按 中心×报告类型 选 (封面, 首页) 模板路径，含规则表的通用/差异化规则。"""
    rt = report_type or "产品报告"
    cover_center = _cover_center(center)
    homepage_center = _homepage_center(center)
    if "工程" in rt:  # 工程报告：6 中心模板统一通用
        return (_find(f"*封面-{cover_center}-工程报告.docx", "*封面-示例中心-工程报告.docx"),
                _find(f"{homepage_center}-工程报告首页*.docx", "示例中心-工程报告首页*.docx"))
    if "校准" in rt:  # 仅院级
        combined = _find("示例中心-校准报告-封面和首页-*.docx",
                         "*能环中心*校准报告*封面和首页*.docx")
        return combined, combined
    if "检验" in rt or "检查" in rt:  # 仅院级
        return (_find("*检验报告封面-示例中心*.docx"), _find("*检验（检查）报告首页*.docx", "*检验*报告首页*.docx"))
    if "抽样" in rt:
        return (_find(f"*封面-{cover_center}-抽样报告.docx", "*封面-空调中心-抽样报告.docx"),
                _find(f"{homepage_center}-抽样报告首页*.docx", "示例中心-抽样报告首页*.docx"))
    return (_find(f"*封面-{cover_center}-产品报告.docx", "*封面-示例中心-产品报告.docx"),
            _find(f"{homepage_center}-产品报告首页*.docx", "示例中心-产品报告首页*.docx"))


def _report_template_paths(report):
    center = _center_from_report(report)
    report_type = _field(report.detail or {}, "送样信息", "报告类型") or "产品报告"
    return select_templates(center, report_type)


def cover_templates_are_combined(report):
    cover_path, homepage_path = _report_template_paths(report)
    return bool(cover_path and cover_path == homepage_path)


def _selected_template_paths(report, part):
    if part not in {"all", "cover", "homepage"}:
        raise ValueError(f"unsupported cover preview part: {part}")
    cover_path, homepage_path = _report_template_paths(report)
    if part == "cover":
        return [cover_path] if cover_path else []
    if part == "homepage":
        return [homepage_path] if homepage_path else []
    paths = []
    for path in (cover_path, homepage_path):
        if path and path not in paths:
            paths.append(path)
    return paths


def template_release_snapshot(report):
    """Return the exact cover/home template release used by a report version."""
    center = _center_from_report(report)
    report_type = _field(report.detail or {}, "送样信息", "报告类型") or "产品报告"
    selected = []
    for path in select_templates(center, report_type):
        if path and path not in selected:
            selected.append(path)

    manifest = {}
    try:
        with open(TPL_MANIFEST, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}
    rows = {row.get("filename"): row for row in manifest.get("templates", [])}

    files = []
    for path in selected:
        filename = os.path.basename(path)
        row = rows.get(filename) or {}
        digest = row.get("sha256")
        if not digest:
            with open(path, "rb") as handle:
                digest = hashlib.sha256(handle.read()).hexdigest()
        files.append({"filename": filename, "sha256": digest})
    return {
        "release": manifest.get("release", "unversioned"),
        "rendererRelease": COVER_RENDERER_RELEASE,
        "effectiveDate": manifest.get("effective_date", ""),
        "files": files,
    }


def _report_values(report):
    from .report_date_display import format_report_dates, report_date, production_date_text
    """从报告抽取封面/首页字段值。各中心模板标签用词不一（样品名称/产品名称、规格型号/型号规格…），故每个值挂多个别名。"""
    d = report.detail or {}
    def F(sec, k):
        return _field(d, sec, k)
    def any_field(*pairs):
        for sec, key in pairs:
            v = F(sec, key)
            if v and v != "—":
                return v
        return ""
    assoc = F("实验信息", "检测依据") or F("实验信息", "执行标准") or F("实验信息", "标准/判定") or F("送样信息", "评定标准")
    sample_name = F("送样信息", "样品名称") or F("送样信息", "样品/工程名称") or F("送样信息", "工程产品名称")
    spec = F("送样信息", "规格型号")
    client = report.client or F("委托信息", "委托单位")
    manuf = F("送样信息", "生产厂家")
    conclusion = F("原始记录", "结论") or F("原始记录", "检测结论")
    test_date = F("实验信息", "检测日期") or F("实验信息", "试验结束日期")
    project = report.project or F("实验信息", "检测项目")
    instr = F("实验信息", "检测设备") or F("实验信息", "试验设备")
    addr = F("委托信息", "委托单位地址")
    criteria = F("实验信息", "判定标准") or F("送样信息", "评定标准") or assoc
    qty = F("送样信息", "样品数量") or F("抽样信息", "抽样数量")
    sampling_no = any_field(("抽样信息", "抽样编号"), ("抽样信息", "样品/抽样单编号"), ("送样信息", "样品编号"))
    sampling_date = any_field(("抽样信息", "抽样日期"), ("抽样信息", "抽样时间"))
    sample_arrival = any_field(("抽样信息", "样品到达日期"), ("送样信息", "送样日期"))
    from .report_final_fields import approval_date
    release_date = approval_date(report)
    # (值, 该值在各模板中可能用到的所有标签)——用列表避免空值/同值作字典键冲突
    pairs = [
        (report.report_no, ["报告编号", "证书编号"]),  # 校准报告用「证书编号」
        (sample_name, ["样品名称", "产品名称", "样品/产品名称", "样品(产品)名称", "计量器具名称"]),  # 校准用「计量器具名称」
        (report.sample_no or F("送样信息", "样品编号"), ["样品编号", "样品/抽样单编号"]),
        (client, ["委托单位", "委托方", "委托单位名称", "送检单位"]),  # 校准用「送检单位」
        (F("送样信息", "检测类别"), ["检测类别", "检验类别"]),
        (manuf, ["生产单位", "生产厂家", "生产单位名称及联系电话", "生产企业", "制造单位"]),  # 校准用「制造单位」
        (F("抽样信息", "受检单位"), ["受检单位", "受检单位名称及联系电话"]),
        (F("送样信息", "商标"), ["商标"]),
        (qty, ["样品数量", "数量", "送样数量", "抽样数量"]),
        (F("送样信息", "流转状态") or getattr(report, "sample_status", "") or "", ["状态"]),
        (F("送样信息", "单位") or F("送样信息", "数量单位"), ["单位"]),
        (spec, ["规格型号", "型号规格", "规格", "型号"]),
        (F("送样信息", "检测地点") or F("送样信息", "站点"), ["检测地点", "检验地点"]),
        (F("委托信息", "委托日期"), ["委托日期"]),
        (test_date, ["检测日期", "检验日期", "校准日期"]),
        (F("送样信息", "出厂编号"), ["出厂编号"]),
        (F("送样信息", "送样日期"), ["送样日期", "接收日期", "样品到达日期"]),  # 校准用「接收日期」
        (production_date_text(d), ["生产日期", "生产日期/批号"]),
        (addr, ["通讯地址", "地址", "委托单位地址", "联系信息", "联络信息"]),
        (assoc, ["检测依据", "检验依据", "检测标准", "检验标准", "校准依据"]),  # 校准用「校准依据」
        (criteria, ["判定依据", "评定依据"]),
        (project, ["检测项目", "检验项目"]),
        (instr, ["仪器设备", "主要仪器", "检测设备", "主要检测设备", "检测用仪器装置", "检测用仪器、装置", "检测仪器", "主要检测仪器"]),
        (conclusion, ["检测结论", "检验结论", "结论", "测", "检测结论及说明"]),
        (F("原始记录", "备注") or F("项目信息", "报告首页备注"), ["备注"]),
        (report.project_name or F("委托信息", "工程名称"), ["工程名称", "工程项目名称", "项目名称"]),  # 检验报告用「项目名称」
        (F("抽样信息", "抽样单位"), ["抽样单位"]),
        (sampling_no, ["抽样编号"]),
        (F("抽样信息", "抽样人"), ["抽样人", "抽样人员"]),
        (F("抽样信息", "抽样地点"), ["抽样地点"]),
        (F("抽样信息", "基数"), ["抽样基数"]),
        (sampling_date, ["抽样日期"]),
        (F("抽样信息", "任务来源"), ["任务来源"]),
        (F("抽样信息", "样品等级"), ["样品等级"]),
        (F("抽样信息", "封样状态") or F("送样信息", "外观"), ["封样状态"]),
        (F("抽样信息", "检查封样人员"), ["检查封样人员"]),
        (sample_arrival, ["样品到达日期"]),
        (release_date, ["报告日期", "签发日期", "批准日期"]),
    ]
    # 三签字（主检/审核/批准）：取各步骤记录的电子签名，未签留空
    sigs = d.get("signatures") or {}
    for role, labels in (("主检", ["主检", "主检签字", "主检：", "检测", "校准员"]),
                         ("审核", ["审核", "审核签字", "审核：", "校核", "审核员"]),
                         ("批准", ["批准", "批准签字", "批准：", "签发", "批 准", "批准人"])):
        v = sigs.get(role) or ""
        if v and v != "待签":
            pairs.append((v, labels))
    out = {}
    for value, labels in pairs:
        for lab in labels:
            out[lab] = value
    return format_report_dates(out)


def _label_key(text):
    """取标签格的中文标签部分并去掉所有空白（模板标签常含换行/空格，如 '检测用\\n仪器、装置'、'检\\n测\\n结\\n论'）。"""
    t = (text or "").replace("　", "")
    out = []
    for ch in t:
        if ch.isascii() and (ch.isalpha() or ch in ".:"):
            break
        out.append(ch)
    # 去掉空白 + 全角/半角冒号（模板标签常形如 "样品编号：" / "规格型\n号："）
    return re.sub(r"[\s：:]", "", "".join(out))


def _replace_inline_label(cell, key, value):
    """处理「批准： Approval」这类标签和值在同一个格子的签名/日期单元格。"""
    if not value or key not in {"主检", "审核", "批准", "校准员", "审核员", "批准人", "报告日期", "签发日期", "批准日期"}:
        return False
    text = cell.text or ""
    if key not in _label_key(text) and key not in text:
        return False
    for p in cell.paragraphs:
        for run in p.runs:
            run.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"{key}: {value}")
    run.font.size = Pt(10)
    try:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    except Exception as exc:
        _ = exc
    return True


_BLANKS = {"", "（以下空白）", "以下空白"}


def _fit_size(text, cell_width_pt, max_pt=12.0, min_pt=6.5):
    """按格宽自适应字号：短文字用合适大小，字多则缩小避免溢出。
    估算字宽：中日韩字≈1个字号宽，英文/数字≈0.55。"""
    units = sum(1.0 if ord(ch) > 0x2E7F else 0.55 for ch in text)
    if units <= 0:
        return max_pt
    avail = max(20.0, (cell_width_pt or 140.0) - 10.0)  # 留左右边距
    return max(min_pt, min(max_pt, avail / units))


def _set_cell(cell, value):
    """字段替换：写入标签相邻格 → 水平/垂直居中、去高亮、按字号规则填。
    字号：保留模板原字号；仅在文字放不下时按格宽缩小，避免填值后改变分页。"""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    except Exception as exc:
        _ = exc
    text = str(value)
    base_pt = None
    if p.runs:
        run = p.runs[0]
        if run.font.size is not None:
            base_pt = run.font.size.pt
        run.text = text
        for r in p.runs[1:]:
            r.text = ""
    else:
        run = p.add_run(text)
    # 去掉填写格自身的高亮
    rpr = run._element.get_or_add_rPr()
    for hl in rpr.findall(qn("w:highlight")):
        rpr.remove(hl)
    # 空白单元格没有直接字号时使用报告表格常用的 10.5pt，不主动放大模板字号。
    target = base_pt if base_pt and 6.0 <= base_pt <= 18.0 else 10.5
    cw = None
    try:
        if cell.width:
            cw = cell.width / 12700.0  # EMU → pt
    except Exception:
        cw = None
    run.font.size = Pt(round(_fit_size(text, cw, max_pt=target), 1))


def _strip_highlights(doc):
    """删除模板里的「标黄」：文字高亮(w:highlight) + 黄色单元格底纹(w:shd fill=FFFF00)。"""
    _YELLOWS = {"FFFF00", "FFFF99", "FFFFCC", "FFF200"}

    def clean_runs(container):
        for p in container.paragraphs:
            for run in p.runs:
                rpr = run._element.rPr
                if rpr is None:
                    continue
                for hl in rpr.findall(qn("w:highlight")):
                    rpr.remove(hl)
                for shd in rpr.findall(qn("w:shd")):
                    if (shd.get(qn("w:fill")) or "").upper() in _YELLOWS:
                        rpr.remove(shd)

    clean_runs(doc)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                clean_runs(cell)
                tcpr = cell._tc.tcPr
                if tcpr is not None:
                    for shd in tcpr.findall(qn("w:shd")):
                        if (shd.get(qn("w:fill")) or "").upper() in _YELLOWS:
                            tcpr.remove(shd)


def _fill(doc, values):
    n = 0
    for table in doc.tables:
        for row in table.rows:
            cells = []
            for c in row.cells:  # 去除合并单元格重复
                if cells and cells[-1]._tc is c._tc:
                    continue
                cells.append(c)
            pending = None
            for c in cells:
                key = _label_key(c.text)
                txt = c.text.strip()
                blank = txt in _BLANKS
                for date_key in ("报告日期", "签发日期", "批准日期"):
                    if date_key in txt and values.get(date_key):
                        _replace_inline_label(c, date_key, values[date_key])
                        n += 1
                        break
                # 值格：空格，或紧跟已知标签的「占位示例文字」（短、非另一标签、非勾选框格）也要替换
                placeholder = key not in values and "□" not in c.text and "☐" not in c.text and len(txt) <= 40
                if pending and (blank or placeholder):
                    val = values.get(pending) or ""
                    if val:
                        _set_cell(c, val)
                        n += 1
                    pending = None
                elif key in values:
                    val = values.get(key) or ""
                    if not _replace_inline_label(c, key, val):
                        pending = key
                elif not blank:
                    pending = None
    return n


def _trademark_image(detail):
    """返回当前报告可用的商标图片，兼容旧数据仅保存在 rawSample 的情况。"""
    detail = detail if isinstance(detail, dict) else {}
    raw_sample = detail.get("rawSample")
    candidates = [detail.get("trademarkImage")]
    if isinstance(raw_sample, dict):
        candidates.append(raw_sample.get("trademarkImage"))
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        value = candidate.strip()
        payload = value.split(",", 1)[1] if value.lower().startswith("data:") and "," in value else value
        payload = re.sub(r"\s+", "", payload)
        try:
            blob = base64.b64decode(payload, validate=True)
        except Exception:
            blob = b""
        if not blob or len(blob) > 2 * 1024 * 1024:
            continue
        if blob.startswith(b"\x89PNG\r\n\x1a\n"):
            mime = "image/png"
        elif blob.startswith(b"\xff\xd8\xff"):
            mime = "image/jpeg"
        else:
            continue
        try:
            from docx.image.image import Image as _DocxImage
            meta = _DocxImage.from_blob(blob)
        except Exception:
            meta = None
        if meta is None or not meta.px_width or not meta.px_height:
            continue
        return f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"
    return ""


def _set_cell_image(cell, b64):
    """把 base64 图片插入单元格：清空原内容，按单元格宽度等比缩放、水平+垂直居中。"""
    raw = b64.split(",", 1)[1] if "," in b64 else b64
    try:
        blob = base64.b64decode(raw)
    except Exception:
        return False
    if not blob:
        return False
    try:
        from docx.image.image import Image as _DocxImage
        meta = _DocxImage.from_blob(blob)
        px_w, px_h = meta.px_width or 1, meta.px_height or 1
    except Exception:
        px_w, px_h = 1, 1
    aspect = px_h / px_w
    cw_emu = int(cell.width) if cell.width else int(Inches(1.5))
    w = int(cw_emu * 0.9)
    h = int(w * aspect)
    max_h = int(Inches(1.0))  # 封顶约 1 英寸，避免撑高表格行
    if h > max_h:
        h = max_h
        w = int(h / aspect)
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r.text = ""
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    try:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    except Exception as exc:
        _ = exc
    try:
        p.add_run().add_picture(BytesIO(blob), width=Emu(w), height=Emu(h))
    except Exception:
        return False
    return True


def _fill_image(doc, label, b64, values):
    """找到标签格（如「商标」）后，把相邻值格替换成图片（覆盖文字填充）。"""
    if not b64:
        return 0
    key_target = _label_key(label)
    n = 0
    for table in doc.tables:
        for row in table.rows:
            cells = []
            for c in row.cells:
                if cells and cells[-1]._tc is c._tc:
                    continue
                cells.append(c)
            pending = False
            for c in cells:
                key = _label_key(c.text)
                if pending:
                    if key in values and key != key_target:
                        pending = False  # 相邻是另一个标签，跳过
                        continue
                    if _set_cell_image(c, b64):
                        n += 1
                    pending = False
                elif key == key_target:
                    pending = True
    return n


# 报告编号占位符：兼容旧星号格式（LAB-2025**-0001 / LAB-2026**-**）与
# 2026 版模板的具体样例格式（LAB-2026YP-0001 / NCSA-2026YP-0001，无星号）。
_RNO_PLACEHOLDER = re.compile(r"[A-Za-z]{2,6}[-－]20\d{2}[A-Za-z]{0,4}[*＊]{0,4}[-－][\d*＊]{2,4}")


def _fill_report_no(doc, report_no):
    """替换报告编号占位（LAB-2025**-0001 之类）。按 w:p 段落聚合 w:t 文本，覆盖正文/表格/文本框/页眉。"""
    if not report_no:
        return
    WP, WT = qn("w:p"), qn("w:t")

    def own_text_nodes(paragraph):
        nodes = []

        def walk(element):
            for child in element:
                if child.tag == WP:
                    continue
                if child.tag == WT:
                    nodes.append(child)
                else:
                    walk(child)

        walk(paragraph)
        return nodes

    def replace_matches(nodes):
        chunks = [node.text or "" for node in nodes]
        full = "".join(chunks)
        matches = list(_RNO_PLACEHOLDER.finditer(full))
        if not matches:
            return
        for match in reversed(matches):
            positions = []
            offset = 0
            for index, chunk in enumerate(chunks):
                positions.append((index, offset, offset + len(chunk)))
                offset += len(chunk)
            touched = [item for item in positions if item[1] < match.end() and item[2] > match.start()]
            if not touched:
                continue
            first, first_start, _ = touched[0]
            last, last_start, _ = touched[-1]
            prefix = chunks[first][:match.start() - first_start]
            suffix = chunks[last][match.end() - last_start:]
            chunks[first] = prefix + report_no + (suffix if first == last else "")
            for index, _, _ in touched[1:-1]:
                chunks[index] = ""
            if last != first:
                chunks[last] = suffix
        for node, value in zip(nodes, chunks, strict=True):
            node.text = value

    def fix_element(root):
        for p_el in root.iter(WP):
            replace_matches(own_text_nodes(p_el))
    fix_element(doc.element.body)  # 正文 + 文本框 + 表格
    # 仅处理包中已经存在的页眉页脚。访问 section.first_page_header 等属性会
    # 自动创建空部件和引用，进而改变 WPS 分页。
    for part in doc.part.package.parts:
        name = str(part.partname)
        if not (name.startswith("/word/header") or name.startswith("/word/footer")):
            continue
        element = getattr(part, "element", None)
        if element is not None:
            fix_element(element)


def _is_blank_p(el):
    """空段落：无文字、无图片、且自身不带分节符/分页符（分页符段落不能当空段删）。"""
    if el.tag != qn("w:p"):
        return False
    # w:t 嵌在 w:r 里，必须用 .// 后代查找 + 看真实文本，否则会把有字的段落误判为空段删掉
    if "".join(t.text or "" for t in el.findall(".//" + qn("w:t"))).strip():
        return False
    if el.findall(".//" + qn("w:drawing")) or el.findall(".//" + qn("w:pict")):
        return False
    if any(b.get(qn("w:type")) == "page" for b in el.findall(".//" + qn("w:br"))):
        return False
    ppr = el.find(qn("w:pPr"))
    if ppr is not None and (ppr.find(qn("w:sectPr")) is not None or ppr.find(qn("w:pageBreakBefore")) is not None):
        return False
    return True


def _trim_blank_before_breaks(body):
    """删掉每个分节符段落之前、以及正文末尾 sectPr 之前的连续空段。
    模板里这些留白空段会被分页推出空白页（封面背面空白页、首页表格溢出只剩页眉那页）。"""
    children = list(body)
    to_remove = []
    for idx, el in enumerate(children):
        is_break = el.tag == qn("w:sectPr")
        if not is_break and el.tag == qn("w:p"):
            ppr = el.find(qn("w:pPr"))
            is_break = ppr is not None and ppr.find(qn("w:sectPr")) is not None
        if not is_break:
            continue
        j = idx - 1
        while j >= 0 and _is_blank_p(children[j]):
            to_remove.append(children[j])
            j -= 1
    for el in to_remove:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)


def _append(dst, src):
    """把 src（首页）接到 dst（封面）之后：用一个分页符接首页内容，且必须插在 body 末尾 sectPr
    之前（早期实现追加在 sectPr 之后，结构非法 → 空白/多余页）。留白空段由 _trim_blank_before_breaks 统一清。"""
    body = dst.element.body
    sectpr = body.find(qn("w:sectPr"))  # body 末尾节属性，必须保持在最后
    pb = OxmlElement("w:p")  # 封面与首页之间分页
    r = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    r.append(br)
    pb.append(r)
    items = [pb]
    for el in src.element.body:
        if el.tag == qn("w:sectPr"):
            continue
        items.append(copy.deepcopy(el))
    for it in items:
        if sectpr is not None:
            sectpr.addprevious(it)  # 插到 body sectPr 之前（合法位置）
        else:
            body.append(it)


def cover_preview_html(report, part="all"):
    """网页内预览：用委托+样品信息渲染指定的封面或首页。"""
    if part not in {"all", "cover", "homepage"}:
        raise ValueError(f"unsupported cover preview part: {part}")
    vals = _report_values(report)
    trademark_img = _trademark_image(report.detail or {})
    center = _center_from_report(report)
    report_type = _field(report.detail or {}, "送样信息", "报告类型") or "产品报告"
    seal = _field(report.detail or {}, "委托信息", "盖章要求") or ""
    rows = [
        ("样品编号", report.sample_no), ("样品名称", vals.get("样品名称")),
        ("规格型号", vals.get("规格型号")), ("商标", vals.get("商标")),
        ("委托单位", vals.get("委托单位")), ("生产单位", vals.get("生产单位")),
        ("委托单位地址", vals.get("通讯地址")), ("检测类别", vals.get("检测类别")),
        ("样品数量", vals.get("样品数量")), ("送样日期", vals.get("送样日期")),
        ("出厂编号", vals.get("出厂编号")), ("生产日期", vals.get("生产日期")),
        ("检测依据", vals.get("检测依据")), ("判定依据", vals.get("判定依据")),
        ("检测项目", vals.get("检测项目")), ("检测设备", vals.get("仪器设备")),
        ("检测日期", vals.get("检测日期")), ("检测结论", vals.get("检测结论")),
    ]
    def esc(v):
        return (str(v) if v else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
    rendered_rows = []
    for key, value in rows:
        cell = esc(value)
        if key == "商标" and trademark_img:
            cell = (
                f"<img class='cv-trademark-image' src='{trademark_img}' alt='{esc(value or '商标')}' "
                "style='display:block;max-width:100%;max-height:96px;width:auto;height:auto;object-fit:contain;margin:0 auto'>"
            )
        rendered_rows.append(f"<tr><th>{esc(key)}</th><td>{cell}</td></tr>")
    trs = "".join(rendered_rows)
    seal_chips = "".join(f"<span class='cv-seal'>{s}</span>" for s in seal.replace("+", " ").split() if s)
    cover = f"""
  <div class="cv-cover">
    <div class="cv-seals">{seal_chips}</div>
    <div class="cv-center">{esc(center)}质量检验检测中心</div>
    <h1 class="cv-title">检 测 报 告</h1>
    <div class="cv-en">TEST&nbsp;&nbsp;REPORT</div>
    <div class="cv-no">{esc(report.report_no)}</div>
    <div class="cv-type">{esc(report_type)}</div>
  </div>
"""
    homepage = f"""
  <div class="cv-home">
    <div class="cv-home-title">报告首页</div>
    <table class="cv-tbl">{trs}</table>
  </div>
"""
    content = cover + homepage if part == "all" else cover if part == "cover" else homepage
    return f"""
<div class="cover-preview">
{content}
</div>
"""


def _compress_notice(doc, line=216):
    """把封面「注意事项/院介绍」段落行距压到 0.9×（封面那一段不动），
    让 LibreOffice 的分页贴回 Word 的两页（否则院介绍联系方式会溢出到第三页）。"""
    def is_break(el):
        if el.tag == qn("w:sectPr"):
            return True
        if el.tag == qn("w:p"):
            if any(b.get(qn("w:type")) == "page" for b in el.findall(".//" + qn("w:br"))):
                return True
            ppr = el.find(qn("w:pPr"))
            if ppr is not None and (ppr.find(qn("w:sectPr")) is not None or ppr.find(qn("w:pageBreakBefore")) is not None):
                return True
        return False
    seen = False
    for el in list(doc.element.body):
        if not seen:
            if is_break(el):
                seen = True
            continue
        if el.tag != qn("w:p"):
            continue
        ppr = el.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            el.insert(0, ppr)
        sp = ppr.find(qn("w:spacing"))
        if sp is None:
            sp = OxmlElement("w:spacing")
            ppr.append(sp)
        sp.set(qn("w:line"), str(line))
        sp.set(qn("w:lineRule"), "auto")


def _fill_one_template(path, report, values, trademark_img):
    """单个模板原样打开→只做字段替换→保存。不合并、不改版式/行距/分页，保证与模板一比一。"""
    doc = Document(path)
    # 先替换报告编号占位，再填字段：否则随后填入的「出厂编号」等含年份值（如 CX-2026-01）会被报告号正则误判覆盖
    _fill_report_no(doc, report.report_no)
    _fill(doc, values)
    _strip_highlights(doc)
    _fill_image(doc, "商标", trademark_img, values)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def build_cover_parts(report, part="all"):
    """按模板渲染封面/首页为独立 docx（每个文件与模板一比一）。
    返回 [封面bytes, 首页bytes]（可能只有其一）；无模板返回 []。
    PDF 预览用：各文件单独转 PDF 后合并，版式绝对忠实（会议 2.8 方案）。"""
    values = _report_values(report)
    trademark_img = _trademark_image(report.detail or {})
    parts = []
    for path in _selected_template_paths(report, part):
        parts.append(_fill_one_template(path, report, values, trademark_img))
    return parts


def build_cover_from_template(report):
    """按模板渲染封面+首页合并为一个 docx（Word 下载用）；找不到模板返回 None（调用方回退程序生成封面）。
    优先 docxcompose 合并（保留双方样式/节设置/图片关系，一比一）；缺库时回退旧的分页符拼接。"""
    center = _center_from_report(report)
    report_type = _field(report.detail or {}, "送样信息", "报告类型") or "产品报告"
    cover_path, home_path = select_templates(center, report_type)
    if not home_path and not cover_path:
        return None
    values = _report_values(report)
    trademark_img = _trademark_image(report.detail or {})
    paths = []
    for p in (cover_path, home_path):
        if p and p not in paths:
            paths.append(p)
    if len(paths) == 1:
        return _fill_one_template(paths[0], report, values, trademark_img)
    try:
        from docxcompose.composer import Composer
        docs = []
        for p in paths:
            d = Document(p)
            _fill_report_no(d, report.report_no)
            _fill(d, values)
            _strip_highlights(d)
            _fill_image(d, "商标", trademark_img, values)
            docs.append(d)
        composer = Composer(docs[0])
        for d in docs[1:]:
            composer.append(d)
        bio = BytesIO()
        composer.save(bio)
        return bio.getvalue()
    except ImportError:
        pass
    # 旧路径兜底：拼接进同一文档（docxcompose 未安装时）
    doc = Document(paths[0])
    _fill_report_no(doc, report.report_no)
    _fill(doc, values)
    _strip_highlights(doc)
    _compress_notice(doc)
    home = Document(paths[1])
    _fill_report_no(home, report.report_no)
    _fill(home, values)
    _strip_highlights(home)
    _append(doc, home)
    _fill_image(doc, "商标", trademark_img, values)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()
