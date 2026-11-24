"""Locate report labels in the exact, immutable PDF being sent for signing."""
import fitz

from .report_seal_layout import _matches


def keyword_positions(pdf, keywords):
    """Keep the keyword-layout contract, including glyph bounds for alignment.

    Spaced Chinese labels (e.g. 主  检) are matched by visible glyphs. Page
    numbers and heights come from this PDF, never from a template or prior flow.
    """
    rows = {word: {"keyword": word, "searchResult": False, "positions": []}
            for word in keywords}
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        for page in doc:
            matches = _matches(page, keywords)
            for word, box in matches:
                rows[word]["searchResult"] = True
                rows[word]["positions"].append({
                    "pageNum": page.number + 1,
                    "coordinates": [{
                        "positionX": box.x0, "positionY": page.rect.height - box.y1,
                        "pdfBounds": list(box), "pageSize": list(page.rect),
                        "pageRotation": page.rotation,
                    }],
                })
    return list(rows.values())


def signature_position(anchor, labels, next_x, offset_x, offset_y):
    """Centre the signature vertically on its bilingual label block."""
    box = fitz.Rect(anchor["pdfBounds"])
    for label in labels:
        other = fitz.Rect(label["pdfBounds"])
        if (label["positionPage"] == anchor["positionPage"]
                and abs(other.x0 - box.x0) < 5
                and abs(other.y0 - anchor["pdfBounds"][1]) < 25):
            box |= other
    page = fitz.Rect(anchor["pageSize"])
    # Preserve the normal horizontal placement, but clear longer labels too.
    # Use the full 72-unit field as a conservative label/column boundary.
    radius = 36
    x = max(float(anchor["positionX"]) + offset_x, box.x1 + 5 + radius)
    y_top = (box.y0 + box.y1) / 2 - offset_y
    field = fitz.Rect(x - radius, y_top - radius, x + radius, y_top + radius)
    if anchor["pageRotation"] or not page.contains(field) or field.x1 > next_x - 5:
        raise ValueError("签字区域超出页面或相邻签字栏，请人工校准位置")
    return {
        "positionPage": anchor["positionPage"], "positionX": round(x, 3),
        "positionY": round(page.height - y_top, 3),
    }, {"labelBounds": list(box), "fieldBounds": list(field), "pageSize": list(page)}
