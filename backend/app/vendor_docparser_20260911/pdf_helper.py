from collections import defaultdict
from typing import Literal
from PIL import Image
from dataclasses import dataclass
from io import BytesIO
from itertools import groupby
from math import isfinite
from pathlib import Path
from typing import Iterator
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import pymupdf
from datetime import datetime, timezone, timedelta

# bak: sys.setrecursionlimit(sys.getrecursionlimit() * 5)
ReportCategory = Literal['Product', 'Sampling', 'Engineering', 'Inspection', 'Calibration', 'Entrust']
ReportLanguage = Literal['CN', 'EN']


def resolve_runtime_font(kind: str) -> Path:
    """Resolve Chinese or English TrueType font from env vars, assets, or OS fonts."""
    import os
    if kind == "cn":
        candidates = [
            os.getenv("PDF_PAGE_NUMBER_SIMSUN_FONT_PATH"),
            os.getenv("LIMS_CN_FONT_PATH"),
            ASSETS_DIR / "fonts/simsun.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
            r"C:\Windows\Fonts\msyh.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
    else:
        candidates = [
            os.getenv("PDF_PAGE_NUMBER_TIMES_FONT_PATH"),
            os.getenv("LIMS_EN_FONT_PATH"),
            ASSETS_DIR / "fonts/times.ttf",
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        ]
    for item in candidates:
        if item and Path(item).is_file():
            return Path(item)
    return ASSETS_DIR / "fonts/LiberationSans-Bold.ttf"

ASSETS_DIR = Path(__file__).resolve().parent / 'assets'


@dataclass(frozen=True, slots=True)
class TextPlacement:
    x: float
    y: float
    content: str
    font_size: float
    bold: bool


class PdfTextWriter:
    """Add mixed Chinese/English text to an existing PDF.
    Page indexes are zero-based. Coordinates start at the visible page's
    top-left corner; ``y`` is the distance from the top to the text baseline.
    """
    CHINESE_PUNCTUATION = frozenset("，。！？；：、（）【】《》〈〉〔〕〖〗「」『』“”‘’—…·￥")
    CHINESE_FONT = "SimSun"
    ENGLISH_FONT = "TimesNewRoman"

    def __init__(self, writer: PdfWriter, chinese_font: str | Path | tuple[str | Path, int],
                 english_font: str | Path | tuple[str | Path, int]) -> None:
        self._writer = writer
        self._placements: dict[int, list[TextPlacement]] = {}
        fonts_config = {
            self.CHINESE_FONT: chinese_font,
            self.ENGLISH_FONT: english_font,
        }
        for font_name, font_path in fonts_config.items():
            if isinstance(font_path, tuple):
                pdfmetrics.registerFont(TTFont(font_name, str(font_path[0]), subfontIndex=font_path[1]))
            else:
                pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
        self._supported_code_points = {
            font_name: pdfmetrics.getFont(font_name).face.charWidths
            for font_name in (self.CHINESE_FONT, self.ENGLISH_FONT)
        }

    def add_text(self, page_index: int, x: float, y: float, content: str, font_size: float = 14,
                 bold: bool = False) -> None:
        """Queue one string for the selected page."""
        if content == "":
            return
        if page_index < 0:
            raise ValueError("page_index must be zero or greater")
        if not isfinite(x):
            raise ValueError("x must be finite")
        if not isfinite(y):
            raise ValueError("y must be finite")
        if not isfinite(font_size) or font_size <= 0:
            raise ValueError("font_size must be finite and greater than zero")
        self._validate_content(content)

        self._placements.setdefault(page_index, []).append(TextPlacement(x, y, content, font_size, bold))

    def apply(self) -> None:
        """Merge all queued strings into the configured PDF writer."""
        for page_index in self._placements:
            if page_index >= len(self._writer.pages):
                raise IndexError(f"page_index out of range: {page_index}")
            page_box = self._writer.pages[page_index].cropbox
            if float(page_box.width) <= 0 or float(page_box.height) <= 0:
                raise ValueError(f"page {page_index} crop box must have a positive size")
        for page_index, page_placements in self._placements.items():
            page = self._writer.pages[page_index]
            if page.rotation:
                page.transfer_rotation_to_content()
            page_box = page.cropbox
            page_left = float(page_box.left)
            page_bottom = float(page_box.bottom)
            page_width = float(page_box.width)
            page_height = float(page_box.height)
            with BytesIO() as buffer:
                overlay = canvas.Canvas(buffer, pagesize=(page_width, page_height))
                for p in page_placements:
                    self._draw_text(overlay, p.x, page_height - p.y, p.content, p.font_size, p.bold)
                overlay.save()
                buffer.seek(0)
                page.merge_transformed_page(
                    PdfReader(buffer).pages[0],
                    Transformation().translate(page_left, page_bottom), over=True, expand=False
                )
        self._placements.clear()

    def _font_for_character(self, char: str) -> str:
        code_point = ord(char)
        if 0x3400 <= code_point <= 0x4DBF or 0x4E00 <= code_point <= 0x9FFF or char in self.CHINESE_PUNCTUATION:
            return self.CHINESE_FONT
        return self.ENGLISH_FONT

    def _iter_font_runs(self, content: str) -> Iterator[tuple[str, str]]:
        for font_name, characters in groupby(content, key=self._font_for_character):
            yield font_name, "".join(characters)

    def _validate_content(self, content: str) -> None:
        for char in content:
            font_name = self._font_for_character(char)
            if ord(char) not in self._supported_code_points[font_name]:
                raise ValueError(f"font does not support {char!r} (U+{ord(char):04X})")

    def _draw_text(self, pdf_canvas: canvas.Canvas, x: float, y: float, content: str, font_size: float,
                   bold: bool) -> None:
        pdf_canvas.saveState()
        try:
            text_object = pdf_canvas.beginText(x, y)
            if bold:
                pdf_canvas.setLineWidth(max(font_size * 0.025, 0.2))
                pdf_canvas.setLineJoin(1)
                text_object.setTextRenderMode(2)
            for font_name, text in self._iter_font_runs(content):
                text_object.setFont(font_name, font_size)
                text_object.textOut(text)
            pdf_canvas.drawText(text_object)
        finally:
            pdf_canvas.restoreState()


class PdfHelper:
    COORDINATE_DEFAULT = (430, 20)

    def __init__(self, compose: tuple[int, int], background: str | Path, paginate: tuple[int, int],
                 keyword: str | None | tuple[int, int], page_format: str) -> None:
        # The number of front and back pages that need to be replaced in the uploaded file
        self._compose = compose
        self._background = background
        # The number of pages to be ignored at the beginning and end of the document when numbering pages
        self._paginate = paginate
        self._keyword = keyword
        self._format = page_format

    @staticmethod
    def is_file_with_ext(file_path: str | Path, file_extensions: list[str]) -> bool:
        if not (isinstance(file_path, str) or isinstance(file_path, Path)):
            return False
        path = Path(file_path)
        return path.is_file() and path.suffix.lower() in file_extensions

    @classmethod
    def is_jpg_or_png(cls, file_path: str | Path) -> bool:
        return cls.is_file_with_ext(file_path, [".jpg", ".jpeg", ".png"])

    @classmethod
    def is_pdf(cls, file_path: str | Path) -> bool:
        return cls.is_file_with_ext(file_path, [".pdf"])

    @staticmethod
    def image_to_pdf(stamp_img: str | Path) -> PdfReader:
        img_as_pdf = BytesIO()
        with Image.open(stamp_img) as img:
            img.load()
            img.save(img_as_pdf, "PDF", quality=95, dpi=(300, 300), optimize=True, subsampling=0)
        img_as_pdf.seek(0)
        return PdfReader(img_as_pdf)

    @classmethod
    def watermark(cls, writer: PdfWriter, image: str | Path, page_indices: list[int] | None = None) -> None:
        if not isinstance(writer, PdfWriter):
            raise RuntimeError('Writer is not an instance of PdfWriter.')
        if not cls.is_jpg_or_png(image):
            raise RuntimeError('Image not supported.')
        bg = cls.image_to_pdf(image).pages[0]
        if bg.rotation:
            bg.transfer_rotation_to_content()
        bg_box = bg.cropbox
        bg_left = float(bg_box.left)
        bg_bottom = float(bg_box.bottom)
        bg_width = float(bg_box.width)
        bg_height = float(bg_box.height)
        if bg_width <= 0 or bg_height <= 0:
            raise ValueError("Background page size must be greater than zero.")
        page_count = len(writer.pages)
        if page_indices is None:
            selected_pages = set(range(page_count))
        else:
            selected_pages = set(page_indices)
        for index, page in enumerate(writer.pages):
            if index not in selected_pages:
                continue
            if page.rotation:
                page.transfer_rotation_to_content()
            page_box = page.cropbox
            page_left = float(page_box.left)
            page_bottom = float(page_box.bottom)
            page_width = float(page_box.width)
            page_height = float(page_box.height)
            if page_width <= 0 or page_height <= 0:
                raise ValueError(f"Page {index} size must be greater than zero.")
            scale = max(page_width / bg_width, page_height / bg_height)
            scaled_width = bg_width * scale
            scaled_height = bg_height * scale
            x = page_left + (page_width - scaled_width) / 2
            y = page_bottom + (page_height - scaled_height) / 2
            transform = Transformation().translate(-bg_left, -bg_bottom).scale(scale, scale).translate(x, y)
            page.merge_transformed_page(bg, transform, over=False, expand=False)

    @staticmethod
    def _search_buffer(buffer: BytesIO, keyword: str) -> list[dict]:
        with pymupdf.open(stream=buffer.getvalue(), filetype='pdf') as pdf:
            return [
                {
                    'page': page.number + 1,
                    # 'text': page.get_textbox(rect),
                    'x0': rect.x0,
                    'top': rect.y0,
                    'x1': rect.x1,
                    'bottom': rect.y1,
                }
                for page in pdf
                for match in page.search_for(keyword)
                for rect in [match * page.rotation_matrix]
            ]

    @classmethod
    def find_text(cls, writer: PdfWriter, keyword: str) -> list[dict]:
        with BytesIO() as buffer:
            writer.write(buffer)
            return cls._search_buffer(buffer, keyword)

    def make(self, input_files: list[str], output: str | Path) -> str:
        """
        Input files shall be arranged in the following order:
        1. System-generated files — required.
        2. User-uploaded files — required; leave blank if the user has not uploaded any files.
        3. Other user-uploaded files — optional.
        """
        if len(input_files) < 2 or (input_files[0] == '' and input_files[1] == ''):
            raise RuntimeError('At least 2 files are required.')
        for index, input_file in enumerate(input_files):
            if (index == 0 or index == 1) and input_file == '':
                continue
            if not self.is_pdf(input_file):
                raise RuntimeError('Only PDF files are supported.')
        if input_files[0] == '':
            input_files[0] = input_files[1]
        # check compose
        compose = list(self._compose)
        reader = PdfReader(input_files[0])
        if compose[0] > len(reader.pages):
            compose[0] = len(reader.pages)
        if compose[1] > len(reader.pages):
            compose[1] = len(reader.pages)
        writer = PdfWriter()
        # front
        writer.append(reader, pages=[i for i in range(compose[0])])
        # body
        if self.is_pdf(input_files[1]):
            body_reader = reader if input_files[1] == input_files[0] else PdfReader(input_files[1])
            writer.append(body_reader, pages=(compose[0], len(body_reader.pages) - compose[1]))
            if body_reader is not reader:
                body_reader.close()
        # extra
        if len(input_files) > 2:
            for f in input_files[2:]:
                writer.append(f)
        # back
        if compose[1] > 0:
            writer.append(reader, pages=[i for i in range(-compose[1], 0)])
        reader.close()
        # add page number
        if isinstance(self._keyword, tuple):
            text_writer = PdfTextWriter(
                writer, chinese_font=resolve_runtime_font("cn"), english_font=resolve_runtime_font("en")
            )
            total = len(writer.pages) - self._paginate[0] - self._paginate[1]
            for i in range(total):
                text_writer.add_text(
                    page_index=i + self._paginate[0],
                    x=self._keyword[0],
                    y=self._keyword[1],
                    content=self._format.format(i + 1, total, i + 1, total),
                    font_size=8,
                    bold=False,
                )
            text_writer.apply()
        elif isinstance(self._keyword, str):
            text_writer = PdfTextWriter(
                writer, chinese_font=resolve_runtime_font("cn"), english_font=resolve_runtime_font("en")
            )
            total = len(writer.pages) - self._paginate[0] - self._paginate[1]
            coordinates = self.find_text(writer, self._keyword)
            y = defaultdict(lambda: self.COORDINATE_DEFAULT[1])
            for coord in coordinates:
                if coord['page'] not in y:
                    y[coord['page']] = coord['bottom']
            for i in range(total):
                text_writer.add_text(
                    page_index=i + self._paginate[0],
                    x=self.COORDINATE_DEFAULT[0],
                    y=y[i + self._paginate[0] + 1] - 2,
                    content=self._format.format(i + 1, total, i + 1, total),
                    font_size=10,
                    bold=True,
                )
            text_writer.apply()
        # add watermark
        if self.is_jpg_or_png(self._background):
            self.watermark(writer, self._background)
        # done
        # Merging page numbers/backgrounds decodes compressed vector streams.
        # Restore lossless compression before writing, without rasterizing or
        # changing the platform's PDF size limit.
        for page in writer.pages:
            page.compress_content_streams()
        # Drop unreachable replaced streams without cloning/parsing the whole
        # graph again in Python. Streams were compressed above; MuPDF preserves
        # their decoded contents, forms and annotations without rasterization.
        with BytesIO() as buffer:
            writer.write(buffer)
            with pymupdf.open(stream=buffer.getvalue(), filetype='pdf') as compact:
                compact.save(output, garbage=3)
        writer.close()
        return str(output)


class PdfMaker(PdfHelper):
    def __init__(self, category: ReportCategory, language: ReportLanguage = 'CN', extended: bool = False) -> None:
        if category == 'Product':
            compose = (3 if extended else 2, 1)  # the number of front, back pages
            background = ASSETS_DIR / 'images/report_bg.jpg'
            paginate = (1, 1)
            keyword = '报告编号（No.）：' if language == 'CN' else 'No. of Report:'
            page_format = '第{}页 共{}页(Page {} of {})' if language == 'CN' else 'Page {} of {}'
            self._issue_pages = [2, 3] if extended else [1, 2]  # page index start from 0
            self._issue_keyword = '报告日期Date：' if language == 'CN' else 'Issue Date:'
            self._issue_offset = (4, -2)
            self._issue_format = '%Y 年 %m 月 %d 日' if language == 'CN' else '%Y-%m-%d'
            self._issue_fontsize = 10.5
        elif category == 'Sampling':
            compose = (3 if extended else 2, 1)
            background = ASSETS_DIR / 'images/report_bg.jpg'
            paginate = (1, 1)
            keyword = '报告编号（No.）：' if language == 'CN' else 'No. of Report:'
            page_format = '第{}页 共{}页(Page {} of {})' if language == 'CN' else 'Page {} of {}'
            self._issue_pages = [2, 3] if extended else [1, 2]
            self._issue_keyword = '报告日期Date：' if language == 'CN' else 'Issue Date:'
            self._issue_offset = (4, -2)
            self._issue_format = '%Y 年 %m 月 %d 日' if language == 'CN' else '%Y-%m-%d'
            self._issue_fontsize = 10.5
        elif category == 'Engineering':
            compose = (1, 1)
            background = ASSETS_DIR / 'images/report_bg.jpg'
            paginate = (1, 1)
            keyword = '报告编号（No.）：' if language == 'CN' else 'No. of Report:'
            page_format = '第{}页 共{}页(Page {} of {})' if language == 'CN' else 'Page {} of {}'
            self._issue_pages = [1, -1]
            self._issue_keyword = '签发日期Date：' if language == 'CN' else 'Issue Date:'
            self._issue_offset = (4, -2)
            self._issue_format = '%Y 年 %m 月 %d 日' if language == 'CN' else '%Y-%m-%d'
            self._issue_fontsize = 10.5
        elif category == 'Inspection':
            compose = (1, 1)
            background = ASSETS_DIR / 'images/report_bg.jpg'
            paginate = (1, 1)
            keyword = '报告编号（No.）：' if language == 'CN' else 'No. of Report:'
            page_format = '第{}页 共{}页(Page {} of {})' if language == 'CN' else 'Page {} of {}'
            self._issue_pages = [1, -1]
            self._issue_keyword = '签发日期Date：' if language == 'CN' else 'Issue Date:'
            self._issue_offset = (4, -2)
            self._issue_format = '%Y 年 %m 月 %d 日' if language == 'CN' else '%Y-%m-%d'
            self._issue_fontsize = 10.5
        elif category == 'Calibration':
            compose = (2, 0)
            background = ASSETS_DIR / 'images/calibration_bg.jpg'
            paginate = (0, 0)
            keyword = (420, 800)  # coordinates
            page_format = '第{}页 共{}页(Page {} of {})' if language == 'CN' else 'Page {} of {}'
            self._issue_pages = [0, 1]
            self._issue_keyword = '签 发 日 期'
            self._issue_offset = (140, -2)
            self._issue_format = '%Y 年 %m 月 %d 日'
            self._issue_fontsize = 12
        elif category == 'Entrust':
            compose = (8, 0)
            background = ASSETS_DIR / 'images/report_bg.jpg'
            paginate = (0, 0)
            keyword = None  # Do not add page numbers
            page_format = ''
            self._issue_pages = [0, 0]
            self._issue_keyword = None
            self._issue_offset = (4, -2)
            self._issue_format = '%Y 年 %m 月 %d 日' if language == 'CN' else '%Y-%m-%d'
            self._issue_fontsize = 10.5
        else:
            raise RuntimeError('Category not supported.')
        super().__init__(compose, background, paginate, keyword, page_format)

    def add_issue_date(self, input_file: str | Path, output_file: str | Path, issue_date: str | None = None) -> str:
        if self._issue_keyword is None:
            raise RuntimeError('Category not supported.')
        writer = PdfWriter(clone_from=input_file)
        text_writer = PdfTextWriter(
            writer, chinese_font=resolve_runtime_font("cn"), english_font=resolve_runtime_font("en")
        )
        if self._issue_pages[1] <= 0:
            index_range = [self._issue_pages[0], len(writer.pages) + self._issue_pages[1]]
        else:
            index_range = self._issue_pages
        coordinates = self.find_text(writer, self._issue_keyword)
        coordinate = None
        last_index = None
        for coord in coordinates:
            index = coord['page'] - 1
            if last_index is not None and index != last_index:
                break
            if index_range[0] <= index < index_range[1]:
                coordinate = (coord['x1'], coord['bottom'])
                last_index = index

        if coordinate is None or last_index is None:
            raise RuntimeError('No coordinates found.')
        text_writer.add_text(
            page_index=last_index,
            x=coordinate[0] + self._issue_offset[0],
            y=coordinate[1] + self._issue_offset[1],
            content=issue_date if issue_date else datetime.now(timezone(timedelta(hours=+8))).strftime(
                self._issue_format),
            font_size=self._issue_fontsize,
            bold=False,
        )
        text_writer.apply()
        writer.write(output_file)
        writer.close()
        return str(output_file)
