"""Derived registration inherits the source scheme and department."""
from copy import deepcopy
import re


def lock_source_scheme(source, detail):
    saved = (source.detail or {}).get("rawSample") or {}
    raw = dict(detail.get("rawSample") or {})
    code = str(saved.get("schemeCode") or "").strip()
    if not code:
        match = re.search(r"(?:^|-)\d{4}([A-Za-z0-9]+)-", source.report_no or "")
        code = match.group(1) if match else ""
    locked = {key: saved.get(key) for key in ("schemeName", "testPlan")}
    locked.update(schemeCode=code, testDept=source.department or saved.get("testDept"),
                  testRoom=source.department or saved.get("testDept") or saved.get("testRoom"))
    for key, value in locked.items():
        if value and raw.get(key) and str(raw[key]).strip() != str(value).strip():
            return "派生报告的检测方案及对应部门不能更改，请重新选择原报告"
        if value:
            raw[key] = deepcopy(value)
    detail["rawSample"] = raw
    for section in detail.get("summary") or []:
        for field in section.get("fields") or []:
            if field[0] in ("检测部门", "检测室") and locked["testDept"]:
                field[1] = locked["testDept"]
    return None
