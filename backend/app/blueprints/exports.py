"""Small dependency-free XLSX export for the currently authorized list result."""

from io import BytesIO
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Blueprint, Response, jsonify, request
from markupsafe import escape

from ..security import require_auth

bp = Blueprint("exports", __name__, url_prefix="/api/exports")


def _xml_text(value):
    text = "" if value is None else str(value)
    return str(escape(text[:32767]))


def _column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _workbook(columns, rows):
    sheet_rows = []
    all_rows = [[column["label"] for column in columns]]
    all_rows.extend([[row.get(column["key"], "") for column in columns] for row in rows])
    for row_index, values in enumerate(all_rows, 1):
        cells = []
        for column_index, value in enumerate(values, 1):
            ref = f"{_column_name(column_index)}{row_index}"
            style = ' s="1"' if row_index == 1 else ""
            cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{_xml_text(value)}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    widths = "".join(
        f'<col min="{index}" max="{index}" width="{min(max(int(column.get("width") or 16), 8), 50)}" customWidth="1"/>'
        for index, column in enumerate(columns, 1)
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<cols>{widths}</cols><sheetData>{"".join(sheet_rows)}</sheetData>'
        '<autoFilter ref="A1:' + _column_name(len(columns)) + str(len(all_rows)) + '"/>'
        '</worksheet>'
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                         '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                         '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                         '</Types>')
        package.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                         '</Relationships>')
        package.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                         '<sheets><sheet name="列表" sheetId="1" r:id="rId1"/></sheets></workbook>')
        package.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                         '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                         '</Relationships>')
        package.writestr("xl/styles.xml", '<?xml version="1.0" encoding="UTF-8"?>'
                         '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                         '<fonts count="2"><font><sz val="10"/><name val="Microsoft YaHei"/></font>'
                         '<font><b/><sz val="10"/><name val="Microsoft YaHei"/></font></fonts>'
                         '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
                         '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
                         '<cellXfs count="2"><xf fontId="0" fillId="0" borderId="0" xfId="0"/>'
                         '<xf fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
                         '</styleSheet>')
        package.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


@bp.post("/xlsx")
@require_auth
def export_xlsx():
    body = request.get_json(silent=True) or {}
    columns = body.get("columns") or []
    rows = body.get("rows") or []
    if not columns or not all(isinstance(item, dict) and item.get("label") and item.get("key") for item in columns):
        return jsonify({"code": 1, "message": "导出列配置无效", "data": None}), 200
    if not isinstance(rows, list) or len(rows) > 5000:
        return jsonify({"code": 1, "message": "单次导出最多 5000 条", "data": None}), 200
    safe_rows = [row for row in rows if isinstance(row, dict)]
    filename = (body.get("filename") or "业务列表").replace("/", "-").replace("\\", "-")[:80] + ".xlsx"
    return Response(
        _workbook(columns[:80], safe_rows),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=list.xlsx; filename*=UTF-8''{quote(filename)}"},
    )
