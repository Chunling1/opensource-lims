"""Strict, source-traceable import of CNAS capability PDF attachments."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import (
    CapabilityEntry,
    CapabilityImportBatch,
    Department,
    Project,
    Standard,
    StdLibraryItem,
)

CAPABILITY_WORDS = ("检测能力范围", "检验能力范围", "校准和测量能力范围")
KNOWN_SITES = ("示例站点E", "示例站点F", "示例站点A", "示例站点B", "示例站点C", "示例站点G", "示例站点H", "示例站点I", "示例站点D")
STANDARD_CODE_RE = re.compile(
    r"(?<![A-Z0-9])("
    r"DB\s*\d{2}(?:/T|/)?\s*\d+(?:\.\d+)*(?:-\d+)*"
    r"|DBJ\s*\d{2}/T-?\s*\d+(?:-\d+)*"
    r"|DG/TJ\s*\d+(?:-\d+)*"
    r"|DGJ\s*\d+(?:-\d+)*"
    r"|AAMA/WDMA/CSA\s+\d+(?:/I\.?S\.?\d+)?/A\d+(?:-\d{2,4})?"
    r"|AMMA/WDMA/CSA\s+\d+(?:/I\.?S\.?\d+)?/A\d+(?:-\d{2,4})?"
    r"|T/[A-Z0-9]+\s+\d+(?:\.\d+)*(?:-\d{2,4})?"
    r"|ASTM\s+[A-Z]\d+(?:/[A-Z]\d+)?M?(?:-\d{2,4})?"
    r"|(?:BS\s+EN\s+)?ISO(?:/IEC)?\s*\d+(?:-\d+)?(?::\d{4})?"
    r"|BS\s+EN\s+\d+(?:-\d+)*(?::\d{4})?(?:\(\d{4}\))?"
    r"|MS\s*\d+\s*:?\s*PART\s*\d+\s*[:-]\s*\d{4}"
    r"|ANSI/ASHRAE\s+Standard\s+\d+(?:\.\d+)*(?:-\d{2,4})?"
    r"|ANSI/AMCA\s+Standard\s+\d+(?:-[A-Z0-9]+)+"
    r"|Edition\s+\d{2}/\d{4}"
    r"|LAB-\d+[A-Z]?"
    r"|AC-\d+-[A-Z]+-\d{4}-\d+"
    r"|ГОСТР\s*\d+(?:-\d{4})?"
    r"|卫办医政发\s*〔\d{4}〕\s*\d+号"
    r"|卫法监\s*【\d{4}】\s*\d+号"
    r"|卫生部\s*\d{4}年版"
    r"|JJF\s*[（(][^）)]+[）)]\s*\d+"
    r"|(?:[A-Z]{1,6}(?:/[A-Z]{1,3})?)"
    r"\s*-?\s*\d+(?:\.\d+)*(?:-\d{2,4}|:\d{4})?(?:\s*[（(]\d{4}年版[）)])?"
    r")",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"(20\d{2})\s*[-年]\s*(\d{1,2})\s*[-月]\s*(\d{1,2})")
CERT_RE = re.compile(r"CNAS\s+(L\d+|IB\d+)", re.IGNORECASE)


def _clean(value) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split())


def normalize_standard_code(value: str) -> str:
    # Spreadsheet text markers are presentation, not an edition or record identity.
    # Keep source rows unchanged; selected-record ID gates still apply separately.
    return (
        re.sub(r"\s+", "", _clean(value))
        .strip("`'\"")
        .upper()
        .replace("—", "-")
        .replace("－", "-")
        .replace("∕", "/")
    )


def _crosscheck_code_key(value: str) -> str:
    """Normalize language-only presentation differences for CN/EN comparison."""
    code = normalize_standard_code(value).replace("（", "(").replace("）", ")")
    code = re.sub(r"^JJF\([^)]*\)", "JJF", code)
    code = re.sub(
        r"^(MS\d+):?PART(\d+)[:-](\d{4})$",
        r"\1:PART\2:\3",
        code,
    )
    if code.startswith(("ISO", "BSENISO")):
        code = re.sub(r"-(20\d{2})$", r":\1", code)
    return code


def _compact(value: str) -> str:
    return re.sub(r"[（）()\s·/、，,：:；;-]", "", value or "")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_sha256(path: Path) -> str:
    if path.is_file():
        return _sha256(path)
    digest = hashlib.sha256()
    for child in sorted(row for row in path.rglob("*") if row.is_file()):
        digest.update(str(child.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(child).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _date(value: str) -> date | None:
    match = DATE_RE.search(value or "")
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups()))
    except ValueError:
        return None


@dataclass
class ParsedCapability:
    capability_type: str
    certificate_no: str
    site: str
    section_path: str
    object_seq: str
    object_name: str
    item_seq: str
    item_name: str
    standard_code: str
    standard_name: str
    method_clause: str
    restriction: str
    effective_date: date | None
    expires_on: date | None
    source_file: str
    source_page: int
    source_row: int
    source_sha256: str
    raw_cells: list[str]


@dataclass
class ImportInspection:
    source_name: str
    source_sha256: str
    attachment_count: int = 0
    chinese_capability_files: int = 0
    chinese_page_count: int = 0
    english_capability_files: int = 0
    english_page_count: int = 0
    english_checks: list[dict] = field(default_factory=list)
    entries: list[ParsedCapability] = field(default_factory=list)
    anomalies: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    item_counts: dict[str, int] = field(default_factory=dict)

    def report(self) -> dict:
        standards = {normalize_standard_code(row.standard_code) for row in self.entries}
        file_rows = []
        for file_row in self.files:
            name = file_row["file"]
            entries = [row for row in self.entries if row.source_file == name]
            anomalies = [
                row for row in self.anomalies if row.get("file") == name
            ]
            file_rows.append({
                **file_row,
                "entryCount": len(entries),
                "itemCount": self.item_counts.get(name, 0),
                "standardCount": len({
                    normalize_standard_code(row.standard_code) for row in entries
                }),
                "anomalyCount": len(anomalies),
                "anomalyRows": anomalies,
            })
        return {
            "sourceName": self.source_name,
            "sourceSha256": self.source_sha256,
            "attachmentCount": self.attachment_count,
            "chineseCapabilityFiles": self.chinese_capability_files,
            "chinesePageCount": self.chinese_page_count,
            "englishCapabilityFiles": self.english_capability_files,
            "englishPageCount": self.english_page_count,
            "englishChecks": self.english_checks,
            "entryCount": len(self.entries),
            "standardCount": len(standards),
            "anomalyCount": len(self.anomalies),
            "anomalies": self.anomalies,
            "files": file_rows,
            "attachments": self.attachments,
        }


def _extract_source(source: Path, target: Path) -> Path:
    if source.is_dir():
        return source
    errors = []
    candidates = (
        ["tar", "-xf", str(source), "-C", str(target)],
        ["7z", "x", "-y", f"-o{target}", str(source)],
        ["7za", "x", "-y", f"-o{target}", str(source)],
    )
    for command in candidates:
        if shutil.which(command[0]) is None:
            continue
        try:
            # The executable is selected from the fixed allowlist above and
            # shell execution is deliberately disabled (the argument vector is
            # passed directly). Source/target are Path values, never commands.
            subprocess.run(command, check=True, capture_output=True, timeout=180)  # nosec B603
            return target
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"{command[0]}: {exc}")
    raise RuntimeError("无法解压能力附件；需要 bsdtar/tar 或 7z：" + "；".join(errors))


def _capability_type(path: Path) -> str:
    name = path.name
    if "校准和测量能力范围" in name:
        return "校准"
    if "检验能力范围" in name:
        return "检验"
    return "检测"


def _site(path: Path, first_page_text: str) -> str:
    for site in KNOWN_SITES:
        if site in path.name or site in first_page_text:
            return site
    address_rules = (
        ("北京市示例站点B区", "示例站点B"),
        ("北京市示例站点C区", "示例站点C"),
        ("北京市示例站点D区", "示例站点D"),
        ("北京市朝阳区", "示例站点A"),
    )
    for token, site in address_rules:
        if token in first_page_text:
            return site
    return ""


def _standard_parts(method: str, *, allow_named: bool = False) -> list[tuple[str, str, str]]:
    """Return (code, title, clause), preserving one relationship per method code."""
    text = (
        _clean(method)
        .replace("∕", "/")
        .replace("—", "-")
        .replace("－", "-")
        .replace("IBS EN", "BS EN")
    )
    text = re.sub(r"\b([A-Z]{1,6})\s*/\s*([A-Z]{1,3})\b", r"\1/\2", text)
    text = re.sub(r"[-—]\s+(?=\d{1,4}\b)", "-", text)
    matches = [
        match for match in STANDARD_CODE_RE.finditer(text)
        if not normalize_standard_code(match.group(1)).startswith(("AMD", "PART"))
        and not re.fullmatch(r"R\d{4}", normalize_standard_code(match.group(1)))
        and not re.fullmatch(
            r"[A-Z]\d+(?:\.\d+)*",
            normalize_standard_code(match.group(1)),
        )
    ]
    if not matches and allow_named:
        titles = [_clean(value) for value in re.findall(r"《([^》]+)》", text) if _clean(value)]
        if titles:
            trailing = _clean(text[text.rfind("》") + 1 :]).strip("，,；; ")
            return [
                (f"名称:{title}", title, trailing if index == len(titles) - 1 else "")
                for index, title in enumerate(titles)
            ]
    rows = []
    for index, match in enumerate(matches):
        code = _clean(match.group(1))
        prefix_start = matches[index - 1].end() if index else 0
        before = _clean(text[prefix_start : match.start()]).strip("，,；;：: ")
        titles = re.findall(r"《([^》]+)》", before)
        title = _clean(titles[-1]) if titles else before.strip("《》 ")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        trailing = _clean(text[match.end() : end]).strip("，,；; ")
        if index + 1 < len(matches):
            bracket = trailing.rfind("《")
            clause = trailing[:bracket].strip("，,；; ") if bracket >= 0 else ""
        else:
            clause = trailing
        rows.append((code, title, clause))
    return rows


def _method_needs_continuation(method: str) -> bool:
    """Identify a method cell that is visibly split at a page boundary."""
    text = _clean(method).upper()
    return text.endswith(("-", "—", "/", "/T")) or bool(
        re.search(r"\b(?:BS\s+EN|ISO(?:/IEC)?|GB|DB\d{2})\s*$", text)
    )


def _is_clause_fragment(method: str) -> bool:
    """Return true only for a standalone list of method-clause references."""
    text = _clean(method)
    if not text:
        return False
    parts = [part for part in re.split(r"[,，]\s*|\s+", text) if part]
    return bool(parts) and all(
        re.fullmatch(
            r"(?:\d{1,3}|(?:附录\s*)?[A-Z]?\d+(?:\.\d+)+(?:-\d+)?)",
            part,
            re.IGNORECASE,
        )
        for part in parts
    )


def _looks_like_heading(cells: list[str]) -> bool:
    joined = "".join(cells)
    return (
        "检测对象" in joined
        or "检验对象" in joined
        or "测量仪器名称" in joined
        or ("项目/参数" in joined and "生效日期" in joined)
        or (
            len(cells) >= 5
            and _compact(cells[2]) == "序号"
            and _compact(cells[3]) == "名称"
            and not cells[4]
        )
    )


def _parse_pdf(path: Path, relative_name: str, inspection: ImportInspection) -> None:
    import pdfplumber

    file_hash = _sha256(path)
    with pdfplumber.open(path) as pdf:
        first_text = pdf.pages[0].extract_text() or ""
        capability_type = _capability_type(path)
        site = _site(path, first_text)
        certificate_match = CERT_RE.search(first_text)
        certificate_no = f"CNAS {certificate_match.group(1).upper()}" if certificate_match else ""
        expiry_match = re.search(r"截止日期[:：]?\s*([20\d年月日\-\s]+)", first_text)
        expires_on = _date(expiry_match.group(1)) if expiry_match else None
        inspection.files.append({
            "file": relative_name,
            "sha256": file_hash,
            "pages": len(pdf.pages),
            "type": capability_type,
            "site": site,
            "certificateNo": certificate_no,
        })
        inspection.chinese_page_count += len(pdf.pages)
        if not site or not certificate_no:
            inspection.anomalies.append({
                "kind": "missing_metadata",
                "file": relative_name,
                "site": site,
                "certificateNo": certificate_no,
            })

        section = ""
        object_seq = object_name = item_seq = item_name = ""
        last_effective = None
        pending_method = None
        last_entry = None
        calibration_method = ""

        def flush_pending():
            nonlocal pending_method
            if pending_method:
                named = _standard_parts(pending_method["method"], allow_named=True)
                if named:
                    emit_standards(named, pending_method)
                else:
                    inspection.anomalies.append({
                        "kind": "unparsed_standard",
                        "file": relative_name,
                        "page": pending_method["page"],
                        "row": pending_method["row"],
                        "method": pending_method["method"],
                    })
                pending_method = None

        def emit_standards(standards, meta):
            nonlocal last_entry
            for code, title, clause in standards:
                last_entry = ParsedCapability(
                    capability_type=capability_type,
                    certificate_no=certificate_no,
                    site=site,
                    section_path=meta["section"],
                    object_seq=meta["object_seq"],
                    object_name=meta["object_name"],
                    item_seq=meta["item_seq"],
                    item_name=meta["item_name"],
                    standard_code=code,
                    standard_name=title,
                    method_clause=clause,
                    restriction=meta["note"],
                    effective_date=meta["effective_date"],
                    expires_on=expires_on,
                    source_file=relative_name,
                    source_page=meta["page"],
                    source_row=meta["row"],
                    source_sha256=file_hash,
                    raw_cells=meta["cells"],
                )
                inspection.entries.append(last_entry)

        for page_no, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                inspection.anomalies.append({
                    "kind": "page_without_table",
                    "file": relative_name,
                    "page": page_no,
                })
                continue
            for table_no, table in enumerate(tables, 1):
                for row_no, raw in enumerate(table, 1):
                    cells = [_clean(value) for value in (raw or [])]
                    if not cells or _looks_like_heading(cells):
                        continue
                    seq = obj = item_number = item = effective = ""
                    if capability_type == "校准":
                        cells += [""] * max(0, 8 - len(cells))
                        seq, obj, measured, method, _measure_range, _uncertainty, note, effective = cells[:8]
                        populated = [value for value in cells if value]
                        if len(populated) == 1 and not method:
                            flush_pending()
                            section = populated[0]
                            continue
                        if pending_method and (seq or obj or measured):
                            flush_pending()
                        if seq:
                            object_seq = seq
                        if obj:
                            object_name = obj
                        if measured:
                            item_seq = ""
                            item_name = measured
                            inspection.item_counts[relative_name] = (
                                inspection.item_counts.get(relative_name, 0) + 1
                            )
                        if method:
                            calibration_method = method
                        elif measured and calibration_method:
                            # The official calibration appendix suppresses a repeated
                            # calibration method when one instrument has multiple
                            # measurands. Each measurand is still an independent
                            # capability relation and must inherit that method.
                            method = calibration_method
                    else:
                        cells += [""] * max(0, 8 - len(cells))
                        seq, obj, item_number, item, method = cells[:5]
                        # CNAS inspection PDFs repeat a footer in the first cell. At a
                        # page break it can contain the next line's year/code while the
                        # real continuation is correctly present in the method cell.
                        # It must not be interpreted as a new inspection object.
                        if method and "NO. CNAS" in seq.upper():
                            seq = ""
                        if (
                            not method
                            and "NO. CNAS" in seq.upper()
                            and not any(cells[1:5])
                        ):
                            continue
                        if capability_type == "检验":
                            note, effective = cells[6], cells[7]
                        else:
                            note, effective = cells[5], cells[6]
                        populated = [value for value in cells if value]
                        if len(populated) == 1 and not method:
                            flush_pending()
                            section = populated[0]
                            continue
                        continuation = bool(
                            pending_method
                            and not item_number
                            and not effective
                            and (method or obj or item)
                        )
                        if pending_method and not continuation and (seq or obj or item_number or item):
                            flush_pending()
                        if seq:
                            object_seq = seq
                        if obj:
                            object_name = (
                                _clean(f"{object_name} {obj}") if continuation else obj
                            )
                            if continuation:
                                pending_method["object_name"] = object_name
                        if item_number:
                            item_seq = item_number
                            if re.fullmatch(
                                r"\d+(?:\.\d+)*",
                                _compact(item_number),
                            ):
                                inspection.item_counts[relative_name] = (
                                    inspection.item_counts.get(relative_name, 0) + 1
                                )
                        if item:
                            item_name = (
                                _clean(f"{item_name} {item}") if continuation else item
                            )
                            if continuation:
                                pending_method["item_name"] = item_name
                    if effective:
                        last_effective = _date(effective) or last_effective
                    if not method:
                        continue
                    if not object_name or not item_name:
                        inspection.anomalies.append({
                            "kind": "orphan_continuation",
                            "file": relative_name,
                            "page": page_no,
                            "row": row_no,
                            "cells": cells,
                        })
                        continue
                    meta = {
                        "section": section,
                        "object_seq": object_seq,
                        "object_name": object_name,
                        "item_seq": item_seq,
                        "item_name": item_name,
                        "note": note,
                        "effective_date": last_effective,
                        "page": page_no,
                        "row": (table_no * 1000) + row_no,
                        "cells": cells,
                    }
                    combined = f"{pending_method['method']} {method}".strip() if pending_method else method
                    standards = _standard_parts(combined)
                    incomplete = _method_needs_continuation(combined)
                    clause_fragment = bool(
                        obj
                        or item
                        or _is_clause_fragment(method)
                    )
                    bare_continuation = bool(
                        not standards
                        and not pending_method
                        and last_entry
                        and capability_type != "校准"
                        and not seq
                        and not item_number
                        and not effective
                        and clause_fragment
                    )
                    if bare_continuation:
                        if obj:
                            object_name = _clean(
                                f"{last_entry.object_name} {obj}"
                            )
                            last_entry.object_name = object_name
                        if item:
                            item_name = _clean(
                                f"{last_entry.item_name} {item}"
                            )
                            last_entry.item_name = item_name
                        last_entry.method_clause = _clean(
                            f"{last_entry.method_clause} {method}"
                        )
                        last_entry.raw_cells = [*last_entry.raw_cells, *cells]
                        continue
                    if not standards or incomplete:
                        if pending_method:
                            pending_method["method"] = combined
                            pending_method["cells"] = [*pending_method["cells"], *cells]
                            pending_method["note"] = pending_method["note"] or note
                            pending_method["effective_date"] = last_effective or pending_method["effective_date"]
                        else:
                            pending_method = {**meta, "method": method}
                        continue
                    if pending_method:
                        pending_method["method"] = combined
                        pending_method["cells"] = [*pending_method["cells"], *cells]
                        pending_method["note"] = pending_method["note"] or note
                        pending_method["effective_date"] = last_effective or pending_method["effective_date"]
                        emit_standards(standards, pending_method)
                        pending_method = None
                    else:
                        emit_standards(standards, meta)
            page.close()
        flush_pending()
        names_by_code = {
            normalize_standard_code(entry.standard_code): entry.standard_name
            for entry in inspection.entries
            if entry.source_file == relative_name and entry.standard_name
        }
        for entry in inspection.entries:
            if entry.source_file == relative_name and not entry.standard_name:
                entry.standard_name = names_by_code.get(
                    normalize_standard_code(entry.standard_code),
                    "",
                )
                if not entry.standard_name:
                    inspection.anomalies.append({
                        "kind": "standard_name_missing",
                        "file": relative_name,
                        "page": entry.source_page,
                        "row": entry.source_row,
                        "standardCode": entry.standard_code,
                    })


def _inspect_english_pdf(path: Path, relative_name: str) -> dict:
    """Extract only cross-check evidence; English attachments are never business data."""
    import pdfplumber
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    first_text = reader.pages[0].extract_text() or ""
    codes = set()
    for page in reader.pages:
        text = (
            _clean(page.extract_text() or "")
            .replace("∕", "/")
            .replace("—", "-")
            .replace("－", "-")
            .replace("：", ":")
        )
        text = re.sub(r"\s*-\s*(?=\d{1,4}(?::\d{4})?\b)", "-", text)
        text = re.sub(
            r"[（(]\s*(\d{4})\s*(?:年|YEAR)?\s*(?:版|EDITION)\s*[）)]",
            r"(\1年版)",
            text,
            flags=re.IGNORECASE,
        )
        for match in STANDARD_CODE_RE.finditer(text):
            code = normalize_standard_code(match.group(1))
            if code and not code.startswith(("IB", "CNASL")) and code != "ISO/IEC17020":
                codes.add(code)
    capability_type = _capability_type(path)
    item_count = 0
    header_tokens = {
        "",
        "№",
        "NO",
        "NO.",
        "序号",
        "MEASURAND",
        "ITEMPARAMETER",
        "ITEMPARAMETERS",
        "TYPEANDRANGEOFINSPECTION",
        "NAME",
    }
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    cells = [_clean(value) for value in (raw or [])]
                    cells += [""] * max(0, 4 - len(cells))
                    if capability_type == "校准":
                        measured = _compact(cells[2]).upper()
                        if measured not in header_tokens:
                            item_count += 1
                    else:
                        item_number = _compact(cells[2]).upper()
                        if re.fullmatch(r"\d+(?:\.\d+)*", item_number):
                            item_count += 1
            page.close()
    certificate_match = CERT_RE.search(first_text)
    return {
        "file": relative_name,
        "pages": len(reader.pages),
        "type": capability_type,
        "site": _site(path, first_text),
        "certificateNo": (
            f"CNAS {certificate_match.group(1).upper()}" if certificate_match else ""
        ),
        "standardCodes": codes,
        "itemCount": item_count,
    }


def inspect_capability_source(source: str | Path) -> ImportInspection:
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    source_hash = _source_sha256(source_path)
    result = ImportInspection(source_path.name, source_hash)
    with tempfile.TemporaryDirectory(prefix="cnas-capabilities-") as temp:
        root = _extract_source(source_path, Path(temp))
        pdfs = sorted(root.rglob("*.pdf"))
        result.attachment_count = len(pdfs)
        from pypdf import PdfReader

        for path in pdfs:
            relative_name = str(path.relative_to(root))
            is_capability = any(word in path.name for word in CAPABILITY_WORDS)
            language = "中文" if "中文" in relative_name else (
                "英文" if "英文" in relative_name else "未知"
            )
            result.attachments.append({
                "file": relative_name,
                "sha256": _sha256(path),
                "pages": len(PdfReader(str(path)).pages),
                "language": language,
                "role": "能力范围" if is_capability else "授权签字人留档",
            })
        chinese = [
            path for path in pdfs
            if "中文" in str(path) and any(word in path.name for word in CAPABILITY_WORDS)
        ]
        english = [
            path for path in pdfs
            if "中文" not in str(path) and any(word in path.name for word in CAPABILITY_WORDS)
        ]
        result.chinese_capability_files = len(chinese)
        for path in chinese:
            _parse_pdf(path, str(path.relative_to(root)), result)
        english_rows = [
            _inspect_english_pdf(path, str(path.relative_to(root)))
            for path in english
        ]
        result.english_capability_files = len(english_rows)
        result.english_page_count = sum(row["pages"] for row in english_rows)

        chinese_groups: dict[tuple[str, str], dict] = {}
        for entry in result.entries:
            group = chinese_groups.setdefault(
                (entry.capability_type, entry.site),
                {
                    "certificateNos": set(),
                    "standardCodes": set(),
                    "sourceFiles": set(),
                },
            )
            group["certificateNos"].add(entry.certificate_no)
            normalized_code = normalize_standard_code(entry.standard_code)
            if not normalized_code.startswith("名称:"):
                group["standardCodes"].add(normalized_code)
            group["sourceFiles"].add(entry.source_file)
        for english_row in english_rows:
            key = (english_row["type"], english_row["site"])
            chinese_row = chinese_groups.get(key)
            if not chinese_row and not english_row["site"]:
                same_type = [
                    (candidate_key, candidate)
                    for candidate_key, candidate in chinese_groups.items()
                    if candidate_key[0] == english_row["type"]
                ]
                if len(same_type) == 1:
                    key, chinese_row = same_type[0]
            if not chinese_row:
                result.anomalies.append({
                    "kind": "english_counterpart_missing",
                    "file": english_row["file"],
                    "type": english_row["type"],
                    "site": english_row["site"],
                })
                continue
            chinese_codes = chinese_row["standardCodes"]
            english_codes = english_row["standardCodes"]
            chinese_keys = {_crosscheck_code_key(code) for code in chinese_codes}
            english_keys = {_crosscheck_code_key(code) for code in english_codes}
            missing_codes = sorted(
                code for code in chinese_codes
                if _crosscheck_code_key(code) not in english_keys
            )
            extra_codes = sorted(
                code for code in english_codes
                if _crosscheck_code_key(code) not in chinese_keys
            )
            shared_count = len(chinese_codes) - len(missing_codes)
            coverage = round(shared_count / len(chinese_codes), 4) if chinese_codes else 1.0
            check = {
                "file": english_row["file"],
                "pages": english_row["pages"],
                "type": english_row["type"],
                "site": key[1],
                "certificateNo": english_row["certificateNo"],
                "chineseStandardCount": len(chinese_codes),
                "englishStandardCount": len(english_codes),
                "sharedStandardCount": shared_count,
                "codeCoverage": coverage,
                "missingStandardCount": len(missing_codes),
                "missingStandardExamples": missing_codes[:100],
                "extraEnglishStandardCount": len(extra_codes),
                "extraEnglishStandardExamples": extra_codes[:100],
                "chineseItemCount": sum(
                    result.item_counts.get(name, 0)
                    for name in chinese_row["sourceFiles"]
                ),
                "englishItemCount": english_row["itemCount"],
            }
            result.english_checks.append(check)
            if english_row["certificateNo"] not in chinese_row["certificateNos"]:
                result.anomalies.append({
                    "kind": "english_certificate_mismatch",
                    **check,
                    "chineseCertificateNos": sorted(chinese_row["certificateNos"]),
                })
            if missing_codes:
                result.anomalies.append({
                    "kind": "english_standard_coverage",
                    **check,
                })
            if check["chineseItemCount"] != check["englishItemCount"]:
                result.anomalies.append({
                    "kind": "english_item_count_mismatch",
                    **check,
                })
    if result.attachment_count != 42:
        result.anomalies.append({
            "kind": "attachment_count",
            "expected": 42,
            "actual": result.attachment_count,
        })
    if result.chinese_page_count != 791:
        result.anomalies.append({
            "kind": "chinese_page_count",
            "expected": 791,
            "actual": result.chinese_page_count,
        })
    if result.english_capability_files != 11:
        result.anomalies.append({
            "kind": "english_capability_file_count",
            "expected": 11,
            "actual": result.english_capability_files,
        })
    return result


def _department_maps():
    departments = Department.query.all()
    by_compact = {_compact(row.name): row for row in departments}
    standards = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all()
    standard_depts: dict[str, set[int]] = {}
    for item in standards:
        ids = {
            by_compact[_compact(name)].id
            for name in re.split(r"[;；]", item.use_depts or "")
            if _compact(name) in by_compact
        }
        if ids:
            standard_depts.setdefault(normalize_standard_code(item.code), set()).update(ids)
    project_depts: dict[str, set[int]] = {}
    for project in Project.query.filter(Project.active.is_(True)).all():
        if project.department_id:
            project_depts.setdefault(_compact(project.name), set()).add(project.department_id)
    return by_compact, standard_depts, project_depts


def _mapping_preview(entries: list[ParsedCapability]) -> dict:
    _by_compact, standard_depts, project_depts = _department_maps()
    unresolved = []
    resolved = 0
    for parsed in entries:
        dept_ids = set(
            standard_depts.get(normalize_standard_code(parsed.standard_code), set())
        )
        dept_ids.update(project_depts.get(_compact(parsed.item_name), set()))
        dept_ids.update(project_depts.get(_compact(parsed.object_name), set()))
        if dept_ids:
            resolved += 1
        else:
            unresolved.append({
                "type": parsed.capability_type,
                "site": parsed.site,
                "objectName": parsed.object_name,
                "itemName": parsed.item_name,
                "standardCode": parsed.standard_code,
                "sourceFile": parsed.source_file,
                "sourcePage": parsed.source_page,
            })
    return {
        "resolvedMappings": resolved,
        "unresolvedMappings": len(unresolved),
        "unresolvedMappingRows": unresolved,
    }


def _append_auth_kind(value: str, token: str) -> str:
    parts = [part for part in re.split(r"[+、,\s]+", value or "") if part]
    if token not in parts:
        parts.append(token)
    return "+".join(parts)


def _remove_auth_kind(value: str, token: str) -> str:
    return "+".join(
        part for part in re.split(r"[+、,\s]+", value or "")
        if part and part != token
    )


def activate_capability_batch(batch_id: int) -> CapabilityImportBatch:
    """Atomically switch the active capability snapshot; caller owns commit/rollback."""
    from .applications.quality_resources.testing_locations import require_legacy_catalog_write_allowed
    require_legacy_catalog_write_allowed()
    batch = db.session.get(CapabilityImportBatch, batch_id)
    if not batch:
        raise ValueError("CNAS 能力批次不存在")
    if (batch.summary or {}).get('schema') == 'lims.internal-parameter.v1':
        raise ValueError('内部维护参数不能作为资质来源激活，请通过正式来源更新')
    anomaly_count = int((batch.summary or {}).get("anomalyCount") or 0)
    if anomaly_count:
        raise ValueError(f"预检仍有 {anomaly_count} 项异常，不能激活")
    if batch.attachment_count != 42 or batch.chinese_page_count != 791:
        raise ValueError("附件数或中文能力表页数未通过严格校验，不能激活")
    pending = CapabilityEntry.query.filter_by(batch_id=batch.id).filter(
        db.or_(
            CapabilityEntry.mapping_status != "confirmed",
            ~CapabilityEntry.departments.any(),
        )
    ).count()
    if pending:
        raise ValueError(f"仍有 {pending} 条部门映射未确认，不能激活")

    for old in CapabilityImportBatch.query.filter_by(status="active").all():
        old.status = "retired"
    CapabilityEntry.query.filter(
        CapabilityEntry.batch_id != batch.id,
        CapabilityEntry.active.is_(True),
    ).update({"active": False}, synchronize_session=False)
    for item in StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all():
        item.auth_kind = _remove_auth_kind(item.auth_kind or "", "CNAS")
    entries = CapabilityEntry.query.filter_by(batch_id=batch.id).all()
    for entry in entries:
        if (entry.raw_cells or {}).get('parameterSupersededBy'):
            entry.active = False
            continue
        entry.active = True
        if entry.standard_item:
            entry.standard_item.auth_kind = _append_auth_kind(
                entry.standard_item.auth_kind or "",
                "CNAS",
            )
            assigned_names = {
                name.strip()
                for name in re.split(r"[;；]", entry.standard_item.use_depts or "")
                if name.strip()
            }
            assigned_names.update(
                department.name for department in entry.departments
            )
            entry.standard_item.use_depts = ";".join(sorted(assigned_names))
    batch.status = "active"
    batch.activated_at = datetime.utcnow()
    return batch


def activate_confirmed_capability_entries(
    batch_id: int,
    entry_ids: list[int],
    *,
    review_note: str,
) -> list[CapabilityEntry]:
    """Activate only explicitly reviewed entries while their batch remains in review."""
    from .applications.quality_resources.testing_locations import require_legacy_catalog_write_allowed
    require_legacy_catalog_write_allowed()
    batch = db.session.get(CapabilityImportBatch, batch_id)
    if not batch or batch.status == "retired":
        raise ValueError("CNAS 能力批次不存在或已停用")
    if (batch.summary or {}).get('schema') == 'lims.internal-parameter.v1':
        raise ValueError('内部维护参数不能作为资质来源激活，请通过正式来源更新')
    ids = sorted({int(value) for value in entry_ids})
    if not ids:
        raise ValueError("至少选择一条能力记录")
    note = str(review_note or "").strip()
    if not note:
        raise ValueError("逐条启用必须填写复核依据")
    entries = CapabilityEntry.query.filter(
        CapabilityEntry.batch_id == batch.id,
        CapabilityEntry.id.in_(ids),
    ).order_by(CapabilityEntry.id).all()
    if len(entries) != len(ids):
        raise ValueError("部分能力记录不存在或不属于当前批次")
    for entry in entries:
        if (entry.raw_cells or {}).get('parameterSupersededBy'):
            raise ValueError(f'能力记录 {entry.id} 已有新修订，不能重新启用历史记录')
        if entry.mapping_status != "confirmed" or not entry.departments:
            raise ValueError(f"能力记录 {entry.id} 的部门映射尚未确认")
        entry.active = True
        if entry.standard_item:
            entry.standard_item.auth_kind = _append_auth_kind(
                entry.standard_item.auth_kind or "",
                "CNAS",
            )
            assigned_names = {
                name.strip()
                for name in re.split(r"[;；]", entry.standard_item.use_depts or "")
                if name.strip()
            }
            assigned_names.update(
                department.name for department in entry.departments
            )
            entry.standard_item.use_depts = ";".join(sorted(assigned_names))
    summary = dict(batch.summary or {})
    activations = list(summary.get("selectiveActivations") or [])
    activations.append({
        "entryIds": ids,
        "reviewNote": note,
        "activatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    })
    summary["selectiveActivations"] = activations
    batch.summary = summary
    return entries


def import_capability_source(
    source: str | Path,
    *,
    apply_changes: bool = False,
    activate: bool = False,
    report_path: str | Path | None = None,
) -> dict:
    if activate and not apply_changes:
        raise ValueError("--activate requires --apply")
    if apply_changes:
        from .applications.quality_resources.testing_locations import require_legacy_catalog_write_allowed
        require_legacy_catalog_write_allowed()
    inspection = inspect_capability_source(source)
    result = inspection.report()
    result.update(_mapping_preview(inspection.entries))
    if report_path:
        report_file = Path(report_path)
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if not apply_changes:
        result["dryRun"] = True
        return result

    try:
        existing = CapabilityImportBatch.query.filter_by(
            source_sha256=inspection.source_sha256
        ).first()
        if existing:
            result.update({
                "dryRun": False,
                "batchId": existing.id,
                "idempotent": True,
                "activated": existing.status == "active",
            })
            if activate and existing.status != "active":
                activate_capability_batch(existing.id)
                existing.summary = {**(existing.summary or {}), **result, "activated": True}
                db.session.commit()
                result["activated"] = True
            return result

        batch = CapabilityImportBatch(
            source_name=inspection.source_name,
            source_sha256=inspection.source_sha256,
            status="review",
            attachment_count=inspection.attachment_count,
            chinese_page_count=inspection.chinese_page_count,
            summary=result,
        )
        db.session.add(batch)
        db.session.flush()

        by_compact, standard_depts, project_depts = _department_maps()
        library_rows = StdLibraryItem.query.filter(StdLibraryItem.deleted_at.is_(None)).all()
        library_by_code = {}
        for item in library_rows:
            library_by_code.setdefault(normalize_standard_code(item.code), item)
        standards_by_code = {
            normalize_standard_code(item.code): item
            for item in Standard.query.filter(Standard.deleted_at.is_(None)).all()
        }
        unresolved = 0
        for parsed in inspection.entries:
            code_key = normalize_standard_code(parsed.standard_code)
            std_item = library_by_code.get(code_key)
            if std_item is None:
                standard = standards_by_code.get(code_key)
                if standard is None:
                    standard = Standard(
                        code=parsed.standard_code,
                        name=parsed.standard_name,
                        auth_kind="",
                        status="现行",
                        expired=False,
                    )
                    db.session.add(standard)
                    db.session.flush()
                    standards_by_code[code_key] = standard
                std_item = StdLibraryItem(
                    standard_id=standard.id,
                    code=parsed.standard_code,
                    name=parsed.standard_name,
                    auth_kind="",
                    out_of_scope=False,
                    # 能力附件生效/截止日期属于认可能力快照，不能冒充标准本身
                    # 的实施/作废日期；二者分别保存在 CapabilityEntry。
                    impl_date="",
                    void_date="",
                    remark=f"CNAS能力附件导入：{parsed.source_file} 第{parsed.source_page}页",
                )
                db.session.add(std_item)
                db.session.flush()
                library_by_code[code_key] = std_item
            dept_ids = set(standard_depts.get(code_key, set()))
            dept_ids.update(project_depts.get(_compact(parsed.item_name), set()))
            dept_ids.update(project_depts.get(_compact(parsed.object_name), set()))
            mapped_departments = [
                db.session.get(Department, dept_id) for dept_id in sorted(dept_ids)
            ]
            mapped_departments = [row for row in mapped_departments if row]
            if mapped_departments:
                # Keep review-batch standards out of business selection. Department
                # assignment is applied to the standard only during activation.
                standard_depts.setdefault(code_key, set()).update(dept_ids)
            entry = CapabilityEntry(
                batch_id=batch.id,
                standard_item_id=std_item.id,
                capability_type=parsed.capability_type,
                certificate_no=parsed.certificate_no,
                site=parsed.site,
                section_path=parsed.section_path,
                object_seq=parsed.object_seq,
                object_name=parsed.object_name,
                item_seq=parsed.item_seq,
                item_name=parsed.item_name,
                standard_code=parsed.standard_code,
                standard_name=parsed.standard_name,
                method_clause=parsed.method_clause,
                restriction=parsed.restriction,
                effective_date=parsed.effective_date,
                expires_on=parsed.expires_on,
                source_file=parsed.source_file,
                source_page=parsed.source_page,
                source_row=parsed.source_row,
                source_sha256=parsed.source_sha256,
                raw_cells=parsed.raw_cells,
                mapping_status="confirmed" if dept_ids else "pending",
                active=False,
            )
            entry.departments = mapped_departments
            db.session.add(entry)
            unresolved += int(not dept_ids)
        db.session.flush()

        result["unresolvedMappings"] = unresolved
        result["batchId"] = batch.id
        result["dryRun"] = False
        if activate:
            activate_capability_batch(batch.id)
            result["activated"] = True
        else:
            result["activated"] = False
        batch.summary = result
        db.session.commit()
        return result
    except IntegrityError:
        db.session.rollback()
        existing = CapabilityImportBatch.query.filter_by(
            source_sha256=inspection.source_sha256
        ).first()
        if not existing:
            raise
        result.update({
            "dryRun": False,
            "batchId": existing.id,
            "idempotent": True,
            "activated": existing.status == "active",
        })
        if activate and existing.status != "active":
            activate_capability_batch(existing.id)
            db.session.commit()
            result["activated"] = True
        return result
    except Exception:
        db.session.rollback()
        raise


__all__ = [
    "activate_capability_batch",
    "activate_confirmed_capability_entries",
    "import_capability_source",
    "inspect_capability_source",
    "normalize_standard_code",
]
