"""Physical sample identity is shared by reports derived from the same sample.

Old registration copied the full report tail into sample_no. Repair only that
provable projection, with explicit lineage; never trim arbitrary sample codes.
This read helper performs no queries and never mutates historical records.
"""

def sample_number(report):
    value = str(getattr(report, "sample_no", None) or "")
    number = str(getattr(report, "report_no", None) or "").strip()
    # Avoid loading deferred JSON for each row of the source picker.
    detail = getattr(report, "__dict__", {}).get("detail") or {}
    raw = detail.get("rawSample") or {}
    main = str(getattr(report, "main_report_no", None) or detail.get("mainReportNo")
               or detail.get("derivedFrom") or raw.get("baseReportNo") or "").strip()
    if not main or main == number or "-" not in main or "-" not in number:
        return value
    # Recognize only a known derived relationship, not an arbitrary prefix.
    report_tail, main_tail = number.split("-", 1)[1], main.split("-", 1)[1]
    suffix = report_tail[len(main_tail):] if report_tail.startswith(main_tail) else ""
    if suffix.upper() not in {"BC", "GZ", "EN", "(E)", "（E）"} and not (suffix.startswith("-") and len(suffix) > 1):
        return value
    return main_tail if value == report_tail else value
