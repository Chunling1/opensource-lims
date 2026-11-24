"""把填好的报告封面/首页 docx 转成 PDF，用于网页内忠实预览真实模板。

转换优先级（会议 2.8：LibreOffice 解析复杂 Word 不全，改用 WPS）：
  1. WPS_SERVICE_URL —— 本机 WPS 转换微服务（生产推荐，见 wps-service/）
  2. WPS_CONVERT_CMD / WPS 命令行
  3. WPS COM（Windows 本机装了 WPS 时，KWPS.Application）→ Word COM 兜底
  4. LibreOffice headless（最后兜底；其分页与 Word 不一致，需删空白页补偿）
转换失败返回 None，调用方决定是否允许回退。正式业务单使用 strict WPS 路径，禁止 LibreOffice 回退。
"""
import glob
import os
import shlex
import shutil
import subprocess  # nosec B404
import tempfile
import threading
import logging
import time


def _soffice():
    b = os.environ.get("SOFFICE_BIN")
    if b and os.path.exists(b):
        return b
    for c in ("/usr/bin/soffice", "/usr/bin/libreoffice", "soffice",
              r"C:\Program Files\LibreOffice\program\soffice.exe"):
        if os.path.exists(c) or shutil.which(c):
            return c
    return "soffice"


def _wps():
    b = os.environ.get("WPS_BIN")
    if b and (os.path.exists(b) or shutil.which(b)):
        return b
    for c in ("/opt/kingsoft/wps-office/office6/wps", "wps",
              r"C:\Program Files (x86)\Kingsoft\WPS Office\ksolaunch.exe"):
        if os.path.exists(c) or shutil.which(c):
            return c
    return None


def _run_convert(cmd, tmp, strip=False):
    # 参数列表来自服务端配置，不经过 shell，也不接收业务表单输入。
    subprocess.run(  # nosec B603
        cmd, timeout=90, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pdfs = glob.glob(os.path.join(tmp, "*.pdf"))
    if not pdfs:
        return None
    with open(pdfs[0], "rb") as f:
        data = f.read()
    return _strip_blank_pages(data) if strip else data


def _convert_with_wps_service(src, tmp):
    """本机 WPS 转换微服务：POST Word 文件 → PDF（见 wps-service/README）。"""
    url = os.environ.get("WPS_SERVICE_URL")
    if not url:
        return None
    import urllib.request
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        return None
    with open(src, "rb") as f:
        payload = f.read()
    from .docx_formula_validation import prepare_math_for_conversion
    payload = prepare_math_for_conversion(payload)
    req = urllib.request.Request(
        url.rstrip("/") + "/convert", data=payload,
        headers={"Content-Type": "application/octet-stream",
                 "X-WPS-Deadline": str(time.time() + 110)}, method="POST")
    # URL 已限制为本机 HTTP(S) 服务。
    with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310
        data = resp.read()
    return data if data[:5] == b"%PDF-" else None


def _convert_with_wps(src, tmp):
    """WPS 命令行转 PDF。生产可配 WPS_CONVERT_CMD，例如：
      WPS_CONVERT_CMD='wps --headless --convert-to pdf --outdir {outdir} {input}'"""
    tpl = os.environ.get("WPS_CONVERT_CMD")
    if tpl:
        return _run_convert(shlex.split(tpl.format(input=src, outdir=tmp), posix=(os.name != "nt")), tmp)
    wps = _wps()
    if not wps:
        return None
    candidates = [
        [wps, "--headless", "--convert-to", "pdf", "--outdir", tmp, src],
        [wps, "-headless", "-convert-to", "pdf", "-outdir", tmp, src],
    ]
    for cmd in candidates:
        try:
            out = _run_convert(cmd, tmp)
            if out:
                return out
        except Exception as exc:
            _ = exc
            continue
    return None


# COM 单实例串行：并发开多个 WPS/Word 进程会互踩
_COM_LOCK = threading.Lock()


def _convert_with_office_com(src, tmp):
    """Windows 本机 WPS(KWPS.Application) / Word COM 转 PDF。分页与 Word 完全一致。"""
    if os.name != "nt":
        return None
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None
    out = os.path.join(tmp, "out.pdf")
    with _COM_LOCK:
        pythoncom.CoInitialize()
        try:
            for prog in ("KWPS.Application", "Word.Application"):
                app = None
                try:
                    app = win32com.client.DispatchEx(prog)
                    app.Visible = False
                    try:
                        app.DisplayAlerts = 0
                    except Exception as exc:
                        _ = exc
                    doc = app.Documents.Open(os.path.abspath(src), ReadOnly=True)
                    try:
                        doc.ExportAsFixedFormat(os.path.abspath(out), 17)  # 17 = wdExportFormatPDF（WPS 兼容）
                    except Exception:
                        doc.SaveAs(os.path.abspath(out), FileFormat=17)
                    doc.Close(False)
                    if os.path.exists(out):
                        with open(out, "rb") as f:
                            return f.read()
                except Exception as exc:
                    _ = exc
                    continue
                finally:
                    try:
                        if app is not None:
                            app.Quit()
                    except Exception as exc:
                        _ = exc
        finally:
            pythoncom.CoUninitialize()
    return None


def _convert_with_soffice(src, tmp):
    prof = os.path.join(tmp, "prof").replace("\\", "/")
    return _run_convert(
        [_soffice(), "--headless", f"-env:UserInstallation=file:///{prof}",
         "--convert-to", "pdf", "--outdir", tmp, src],
        tmp,
        strip=True,  # LibreOffice 分页与 Word 不一致会排出空白页，需补偿；WPS/Word 路径不删
    )


def _strip_blank_pages(pdf_bytes):
    """删掉无正文的空白页（封面背面/溢出页：LibreOffice 比 Word 每页排得少，会多排出只剩边框的空页）。
    判据：页面文字 <5 字 且 非白像素 <1.5%（只剩装饰边框）。无 PyMuPDF 时原样返回，不报错。"""
    try:
        import fitz
    except Exception:
        return pdf_bytes
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        removed = False
        for i in range(doc.page_count - 1, -1, -1):
            pg = doc[i]
            if len(pg.get_text().strip()) >= 5:
                continue
            pm = pg.get_pixmap(dpi=40, colorspace=fitz.csGRAY)
            s = pm.samples
            ink = sum(1 for b in s if b < 235) / max(1, len(s))
            if ink < 0.015:
                doc.delete_page(i)
                removed = True
        out = doc.tobytes() if removed else pdf_bytes
        doc.close()
        return out
    except Exception:
        return pdf_bytes


def _office_to_pdf_with(file_bytes, suffix, converters):
    # Run before converter fallback handling: actionable missing-image errors
    # must reach the preview UI, and no engine may fetch an external picture.
    from .docx_linked_pictures import prepare_linked_pictures
    file_bytes = prepare_linked_pictures(file_bytes)
    tmp = tempfile.mkdtemp(prefix="cvpdf_")
    try:
        safe_suffix = suffix.lower() if suffix.lower() in (".doc", ".docx") else ".docx"
        src = os.path.join(tmp, "in" + safe_suffix)
        with open(src, "wb") as f:
            f.write(file_bytes)
        for convert in converters:
            started = time.monotonic()
            try:
                pdf = convert(src, tmp)
                if pdf:
                    return pdf
            except Exception as exc:
                # Never log the raw exception: it may contain a temporary path,
                # service URL, customer file name or document content.
                logging.getLogger(__name__).warning('pdf_conversion_failed converter=%s error_type=%s',
                                                     convert.__name__, type(exc).__name__)
                continue
            finally:
                logging.getLogger(__name__).info('pdf_conversion_stage converter=%s elapsed_ms=%.1f',
                                                convert.__name__, (time.monotonic() - started) * 1000)
        return None
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def office_to_pdf(file_bytes, suffix=".docx"):
    """把 doc/docx 文件转换为 PDF，允许兼容性回退。"""
    from .wps_pdf_cache import convert_once
    return convert_once(file_bytes, suffix, lambda: _office_to_pdf_with(
        file_bytes,
        suffix,
        (_convert_with_wps_service, _convert_with_wps, _convert_with_office_com, _convert_with_soffice),
    ), policy='compatible')


def office_to_pdf_wps(file_bytes, suffix=".docx"):
    """只使用 WPS 转换；失败即返回 None，避免用其他引擎产生错误预览。"""
    # A configured service owns the single WPS instance. A timed-out HTTP call
    # does NOT mean its worker stopped. Do not launch a competing CLI fallback.
    converters = ((_convert_with_wps_service,) if os.environ.get('WPS_SERVICE_URL')
                  else (_convert_with_wps_service, _convert_with_wps))
    from .wps_pdf_cache import convert_once
    return convert_once(file_bytes, suffix, lambda: _office_to_pdf_with(file_bytes, suffix, converters))


def docx_to_pdf(docx_bytes):
    return office_to_pdf(docx_bytes, ".docx")


def docx_to_pdf_wps(docx_bytes):
    return office_to_pdf_wps(docx_bytes, ".docx")


def merge_pdf_bytes(pdf_list):
    """按序合并多个 PDF 为一个。"""
    import fitz
    out = fitz.open()
    for data in pdf_list:
        with fitz.open(stream=data, filetype="pdf") as d:
            out.insert_pdf(d)
    data = out.tobytes()
    out.close()
    return data


def image_to_pdf(image_bytes):
    """Place a raster attachment on an A4 PDF page without stretching it."""
    import fitz

    source = fitz.open(stream=image_bytes)
    try:
        if source.page_count < 1:
            raise ValueError("图片没有可转换页面")
        pix = source[0].get_pixmap(alpha=False)
        if pix.width <= 0 or pix.height <= 0:
            raise ValueError("图片尺寸无效")
        page_width, page_height = 595.28, 841.89
        margin = 36.0
        max_width = page_width - margin * 2
        max_height = page_height - margin * 2
        scale = min(max_width / pix.width, max_height / pix.height)
        width, height = pix.width * scale, pix.height * scale
        x0 = (page_width - width) / 2
        y0 = (page_height - height) / 2
        target = fitz.open()
        try:
            page = target.new_page(width=page_width, height=page_height)
            page.insert_image(fitz.Rect(x0, y0, x0 + width, y0 + height), stream=image_bytes)
            return target.tobytes(garbage=4, deflate=True)
        finally:
            target.close()
    finally:
        source.close()


def _page_number_font_paths():
    """Return Chinese/English font files used by report headers (env, OS, or open-source fallback)."""
    from .vendor_docparser_20260911.pdf_helper import resolve_runtime_font

    cn_font = str(resolve_runtime_font("cn"))
    en_font = str(resolve_runtime_font("en"))
    if os.path.isfile(cn_font) and os.path.isfile(en_font):
        return cn_font, en_font
    raise RuntimeError("报告页码字体不可用：未找到可用的中英文字体文件")


def _report_number_line_metrics(page, report_no):
    """Locate the report-number row so the page number shares its baseline."""
    if not report_no:
        return None
    expected = str(report_no).replace("-", "").replace("\u00ad", "").replace("\u00a0", " ")
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            for span in spans:
                actual = str(span.get("text", "")).replace("-", "").replace("\u00ad", "").replace("\u00a0", " ")
                if expected not in actual:
                    continue
                baseline = float(span["origin"][1])
                same_line = [
                    candidate for candidate in spans
                    if abs(float(candidate["origin"][1]) - baseline) <= 2.0
                ]
                left_margin = min(float(candidate["bbox"][0]) for candidate in same_line)
                return baseline, float(span["size"]), left_margin
    return None


def add_top_right_page_numbers(pdf_bytes, skip_first_page=True, report_no=""):
    """Overlay bilingual page numbers on the report-number row.

    The physical cover remains blank when ``skip_first_page`` is true. Chinese
    text is embedded as SimSun and English/digits as Times New Roman so WPS,
    browser and e-sign previews render the same result.
    """
    import fitz

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        start_index = 1 if skip_first_page else 0
        if document.page_count <= start_index:
            return pdf_bytes
        simsun_path, times_path = _page_number_font_paths()
        simsun_font = fitz.Font(fontfile=simsun_path)
        times_font = fitz.Font(fontfile=times_path)
        total = document.page_count - start_index
        default_metrics = None
        for page in document:
            default_metrics = _report_number_line_metrics(page, report_no) or default_metrics
        # The fallback matches the approved report home-page header geometry.
        default_metrics = default_metrics or (91.5, 9.95, 56.7)
        for physical_index in range(start_index, document.page_count):
            page = document[physical_index]
            baseline, font_size, left_margin = (
                _report_number_line_metrics(page, report_no) or default_metrics
            )
            page_number = physical_index - start_index + 1
            pieces = (
                ("第 ", simsun_font, "ReportPageNoSimSun", simsun_path),
                (str(page_number), times_font, "ReportPageNoTimes", times_path),
                ("页 共 ", simsun_font, "ReportPageNoSimSun", simsun_path),
                (str(total), times_font, "ReportPageNoTimes", times_path),
                ("页 ", simsun_font, "ReportPageNoSimSun", simsun_path),
                (f"(Page {page_number} of {total})", times_font, "ReportPageNoTimes", times_path),
            )
            widths = [font.text_length(text, fontsize=font_size) for text, font, _name, _path in pieces]
            x = float(page.rect.width) - left_margin - sum(widths)
            if x <= left_margin:
                raise ValueError(f"第 {physical_index + 1} 张物理页页码区域不足")
            for (text, _font, font_name, font_path), width in zip(pieces, widths):
                page.insert_text(
                    (x, baseline),
                    text,
                    fontname=font_name,
                    fontfile=font_path,
                    fontsize=font_size,
                    color=(0, 0, 0),
                    overlay=True,
                )
                x += width
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()


def docx_list_to_pdf(docx_list):
    """多个 docx（封面/首页各自与模板一比一）分别转 PDF 后合并。任一失败返回 None。"""
    pdfs = []
    for blob in docx_list:
        pdf = docx_to_pdf(blob)
        if not pdf:
            return None
        pdfs.append(pdf)
    if not pdfs:
        return None
    return pdfs[0] if len(pdfs) == 1 else merge_pdf_bytes(pdfs)
