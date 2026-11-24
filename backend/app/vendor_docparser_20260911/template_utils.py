import math
import os
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal, Sequence
from zipfile import ZipFile

import qrcode
from docxtpl import DocxTemplate, InlineImage, Listing, RichText, RichTextParagraph
from docxtpl.subdoc import Subdoc
from jinja2 import TemplateError
from lxml import etree
from markupsafe import Markup
from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps
from qrcode.exceptions import DataOverflowError

ASSETS_DIR = Path(__file__).resolve().parent / 'assets'


class CmaMarkRenderer:
    """
    Render a dimensionally stable CMA mark with a 12-digit number.
    Self-contained CMA mark renderer for PNG and docxtpl output.

    Example::

        from docxtpl import DocxTemplate
        from cma_mark import CmaMarkRenderer

        renderer = CmaMarkRenderer()
        tpl = DocxTemplate("template.docx")
        tpl.render({
            "cma_mark": renderer.make_inline_image(
                tpl,
                "012345678901",
                width=72,
            ),
        })
        tpl.save("output.docx")

    The template placeholder ``{{ cma_mark }}`` should be the only content in a
    centered paragraph whose spacing before and after is zero.
    """

    DEFAULT_COLOR = "#FF0000"
    DEFAULT_DPI = 1200
    NUMBER_LENGTH = 12

    WIDTH_L = 7.0
    LOGO_HEIGHT_L = 4.0
    NUMBER_GAP_L = 0.2
    NUMBER_HEIGHT_L = 0.65
    HEIGHT_L = LOGO_HEIGHT_L + NUMBER_GAP_L + NUMBER_HEIGHT_L

    _SUPERSAMPLE = 4
    _MAX_WORK_PIXELS = 128_000_000
    _FONT_PATH = ASSETS_DIR / "fonts/LiberationSans-Bold.ttf"

    def __init__(
            self,
            dpi: int = DEFAULT_DPI,
            color: str | Sequence[int] = DEFAULT_COLOR,
    ) -> None:
        """Configure output resolution, solid mark color."""

        self.dpi = self._validate_dpi(dpi)
        self.color = self._parse_color(color)
        self.font_path = self._FONT_PATH
        if not self.font_path.is_file():
            raise FileNotFoundError(f"CMA number font file was not found at {self.font_path}.")
        self._source_font = ImageFont.truetype(str(self.font_path), 2048)
        self._source_glyph_cache: dict[str, Image.Image] = {}
        self._scaled_glyph_height: int | None = None
        self._scaled_glyph_cache: dict[str, Image.Image] = {}

    @classmethod
    def height(cls, width: float) -> float:
        """Return the proportional total image height in points for ``width``."""

        cls._validate_width(width)
        return float(width) * cls.HEIGHT_L / cls.WIDTH_L

    @classmethod
    def _validate_number(cls, number: str) -> None:
        if not isinstance(number, str):
            raise TypeError("number must be a string containing exactly 12 digits")
        if (
                len(number) != cls.NUMBER_LENGTH
                or not number.isascii()
                or not number.isdigit()
        ):
            raise ValueError("number must contain exactly 12 ASCII digits")

    @staticmethod
    def _validate_width(width: float) -> None:
        if isinstance(width, bool) or not isinstance(width, (int, float)):
            raise TypeError("width must be a positive number")
        if not math.isfinite(float(width)) or width <= 0:
            raise ValueError("width must be greater than zero")

    @staticmethod
    def _validate_dpi(dpi: int) -> int:
        if isinstance(dpi, bool) or not isinstance(dpi, int):
            raise TypeError("dpi must be a positive integer")
        if dpi <= 0:
            raise ValueError("dpi must be greater than zero")
        return dpi

    @staticmethod
    def _parse_color(color: str | Sequence[int]) -> tuple[int, int, int]:
        try:
            rgb = ImageColor.getrgb(color) if isinstance(color, str) else tuple(color)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid color: {color!r}") from exc
        if len(rgb) != 3 or any(
                isinstance(channel, bool)
                or not isinstance(channel, int)
                or not 0 <= channel <= 255
                for channel in rgb
        ):
            raise ValueError(
                "color must be a Pillow RGB color string or an RGB integer tuple"
            )
        return tuple(rgb)

    @staticmethod
    def _quadratic_points(
            start: tuple[float, float],
            control: tuple[float, float],
            end: tuple[float, float],
            steps: int = 160,
    ) -> list[tuple[float, float]]:
        points = []
        for index in range(steps + 1):
            t = index / steps
            mt = 1.0 - t
            points.append(
                (
                    mt * mt * start[0]
                    + 2 * mt * t * control[0]
                    + t * t * end[0],
                    mt * mt * start[1]
                    + 2 * mt * t * control[1]
                    + t * t * end[1],
                )
            )
        return points

    @staticmethod
    def _scaled_points(
            points: Sequence[tuple[float, float]], scale: float
    ) -> list[tuple[int, int]]:
        return [(round(x * scale), round(y * scale)) for x, y in points]

    @classmethod
    def _draw_logo_mask(
            cls, scale: float, width: int, logo_height: int
    ) -> Image.Image:
        mask = Image.new("L", (width, logo_height), 0)
        draw = ImageDraw.Draw(mask)

        # The outer C-shaped frame is the C in CMA. Its 0.4L center-line
        # stroke gives exact visible outer bounds of 7L x 4L.
        top = cls._quadratic_points((0.2, 0.8), (3.5, -0.4), (6.8, 0.8))
        bottom = cls._quadratic_points((0.2, 3.2), (3.5, 4.4), (6.8, 3.2))
        frame_path = (
                [(6.8, 1.5), (6.8, 0.8)]
                + list(reversed(top))
                + [(0.2, 3.2)]
                + bottom[1:]
                + [(6.8, 2.5)]
        )
        draw.line(
            cls._scaled_points(frame_path, scale),
            fill=255,
            width=max(1, round(0.4 * scale)),
            joint="curve",
        )

        m_points = [
            (1.2, 3.1),
            (1.2, 0.9),
            (1.6, 0.9),
            (2.3, 1.6),
            (3.0, 0.9),
            (3.4, 0.9),
            (3.4, 3.1),
            (3.0, 3.1),
            (3.0, 1.5),
            (2.3, 2.2),
            (1.6, 1.5),
            (1.6, 3.1),
        ]
        draw.polygon(cls._scaled_points(m_points, scale), fill=255)

        left_leg = [(3.9, 3.1), (4.7, 0.9), (5.1, 0.9), (4.35, 3.1)]
        right_leg = [(4.7, 0.9), (5.1, 0.9), (5.9, 3.1), (5.45, 3.1)]
        crossbar = [(4.32, 2.05), (5.48, 2.05), (5.62, 2.45), (4.18, 2.45)]
        draw.polygon(cls._scaled_points(left_leg, scale), fill=255)
        draw.polygon(cls._scaled_points(right_leg, scale), fill=255)
        draw.polygon(cls._scaled_points(crossbar, scale), fill=255)
        return mask

    @staticmethod
    def _tight_glyph_mask(
            font: ImageFont.FreeTypeFont, digit: str
    ) -> Image.Image:
        bbox = font.getbbox(digit)
        width = max(1, bbox[2] - bbox[0] + 8)
        height = max(1, bbox[3] - bbox[1] + 8)
        canvas = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(canvas)
        draw.text((4 - bbox[0], 4 - bbox[1]), digit, font=font, fill=255)
        tight_bbox = canvas.getbbox()
        if tight_bbox is None:
            raise RuntimeError(f"font produced an empty glyph for {digit!r}")
        return canvas.crop(tight_bbox)

    def _source_glyph(self, digit: str) -> Image.Image:
        glyph = self._source_glyph_cache.get(digit)
        if glyph is None:
            glyph = self._tight_glyph_mask(self._source_font, digit)
            self._source_glyph_cache[digit] = glyph
        return glyph

    def _draw_number_mask(
            self,
            number: str,
            target_width: int,
            target_height: int,
    ) -> Image.Image:
        if target_height != self._scaled_glyph_height:
            self._scaled_glyph_height = target_height
            self._scaled_glyph_cache = {}

        scaled_glyphs = self._scaled_glyph_cache
        glyphs: list[Image.Image] = []
        for digit in number:
            glyph = scaled_glyphs.get(digit)
            if glyph is None:
                source = self._source_glyph(digit)
                glyph_width = max(
                    1, round(source.width * target_height / source.height)
                )
                glyph = source.resize(
                    (glyph_width, target_height), Image.Resampling.LANCZOS
                )
                scaled_glyphs[digit] = glyph
            glyphs.append(glyph)

        ink_width = sum(glyph.width for glyph in glyphs)
        if ink_width > target_width:
            raise ValueError(
                "the selected font cannot fit 12 digits into 7L while "
                "preserving 0.65L height"
            )

        result = Image.new("L", (target_width, target_height), 0)
        gap = (target_width - ink_width) / (len(glyphs) - 1)
        cursor = 0.0
        for index, glyph in enumerate(glyphs):
            x = (
                target_width - glyph.width
                if index == len(glyphs) - 1
                else round(cursor)
            )
            result.paste(glyph, (x, 0))
            cursor += glyph.width + gap
        return result

    def render_png(self, number: str, width: float) -> bytes:
        """Return the CMA mark as PNG bytes at the requested width in points."""

        self._validate_number(number)
        self._validate_width(width)

        pixels_per_l = float(width) * self.dpi / (72.0 * self.WIDTH_L)
        final_width = max(1, round(float(width) * self.dpi / 72.0))
        final_height = max(1, round(self.HEIGHT_L * pixels_per_l))

        scale = pixels_per_l * self._SUPERSAMPLE
        work_width = max(1, round(self.WIDTH_L * scale))
        logo_height = max(1, round(self.LOGO_HEIGHT_L * scale))
        gap_height = max(0, round(self.NUMBER_GAP_L * scale))
        number_height = max(1, round(self.NUMBER_HEIGHT_L * scale))
        work_height = logo_height + gap_height + number_height
        if work_width * work_height > self._MAX_WORK_PIXELS:
            raise ValueError(
                "width and dpi produce an image that is too large; "
                "reduce width or dpi"
            )

        alpha = Image.new("L", (work_width, work_height), 0)
        alpha.paste(self._draw_logo_mask(scale, work_width, logo_height), (0, 0))
        number_mask = self._draw_number_mask(
            number,
            target_width=work_width,
            target_height=number_height,
        )
        alpha.paste(number_mask, (0, logo_height + gap_height))
        alpha = alpha.resize((final_width, final_height), Image.Resampling.LANCZOS)

        result = Image.new("RGBA", (final_width, final_height), (*self.color, 0))
        result.putalpha(alpha)

        output = BytesIO()
        result.save(
            output,
            format="PNG",
            dpi=(self.dpi, self.dpi),
            optimize=False,
            compress_level=6,
        )
        return output.getvalue()

    def save_png(
            self,
            number: str,
            output_path: str | Path,
            width: float,
    ) -> Path:
        """Save a CMA mark of ``width`` points as PNG and return its path."""

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.render_png(number=number, width=width))
        return path

    def make_inline_image(self, template, number: str, width: float):
        """Return a docxtpl ``InlineImage`` at ``width`` points."""

        try:
            from docx.shared import Pt
            from docxtpl import InlineImage
        except ImportError as exc:
            raise RuntimeError(
                "make_inline_image requires docxtpl and python-docx"
            ) from exc

        stream = BytesIO(self.render_png(number=number, width=width))
        return InlineImage(template, stream, width=Pt(float(width)))


class QrCodeRenderer:
    """QR code renderer for PNG and docxtpl output.

    Example::

        from docxtpl import DocxTemplate
        from qr_code import QrCodeRenderer

        renderer = QrCodeRenderer()
        tpl = DocxTemplate("template.docx")
        tpl.render({
            "qr_code": renderer.make_inline_image(
                tpl,
                "https://example.com",
                width=72,
            ),
        })
        tpl.save("output.docx")

    ``width`` is expressed in points. Pass ``background=None`` for a transparent
    PNG, and place transparent codes only on a plain background that contrasts
    strongly with the foreground. The template placeholder ``{{ qr_code }}``
    should normally be the only content in its paragraph.

    Pass ``logo_path`` to place an image in the center. Logo rendering uses error
    correction level H automatically and preserves the logo's aspect ratio.
    """

    DEFAULT_DPI = 300
    DEFAULT_COLOR = "#000000"
    DEFAULT_BACKGROUND = "#FFFFFF"
    DEFAULT_ERROR_CORRECTION = "M"
    DEFAULT_BORDER = 4

    _MAX_IMAGE_PIXELS = 25_000_000
    _MIN_MODULE_PIXELS = 4
    _MIN_MODULE_SIZE_MM = 0.25
    _MIN_CONTRAST_RATIO = 4.5
    _MAX_LOGO_RATIO = 0.2
    _MAX_LOGO_SOURCE_PIXELS = 25_000_000
    _ERROR_CORRECTION = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }
    _READ_ONLY_CONFIG = frozenset(
        {
            "dpi",
            "color",
            "background",
            "error_correction",
            "border",
            "logo_path",
            "logo_size_ratio",
        }
    )

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._READ_ONLY_CONFIG and hasattr(self, name):
            raise AttributeError(f"{name} is read-only")
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        if name in self._READ_ONLY_CONFIG:
            raise AttributeError(f"{name} is read-only")
        super().__delattr__(name)

    def __init__(
            self,
            dpi: int = DEFAULT_DPI,
            color: str | Sequence[int] = DEFAULT_COLOR,
            background: str | Sequence[int] | None = DEFAULT_BACKGROUND,
            error_correction: str = DEFAULT_ERROR_CORRECTION,
            border: int = DEFAULT_BORDER,
            logo_path: str | os.PathLike[str] | None = None,
            logo_size_ratio: float = _MAX_LOGO_RATIO,
    ) -> None:
        """Configure resolution, colors, correction, quiet zone, and logo."""

        self.dpi = self._validate_dpi(dpi)
        self.color = self._parse_color(color, "color")
        self.background = (
            None
            if background is None
            else self._parse_color(background, "background")
        )
        if self.background is not None:
            self._validate_contrast(self.color, self.background)
        configured_correction = self._validate_error_correction(error_correction)
        self.border = self._validate_border(border)
        self.logo_size_ratio = self._validate_logo_size_ratio(logo_size_ratio)
        self.logo_path, self._logo_image = self._load_logo(logo_path)
        self.error_correction = "H" if self._logo_image is not None else configured_correction

    @staticmethod
    def _validate_data(data: str | bytes) -> None:
        if not isinstance(data, (str, bytes)):
            raise TypeError("data must be a non-empty string or bytes")
        if not data:
            raise ValueError("data must not be empty")

    @staticmethod
    def _validate_width(width: float) -> None:
        if isinstance(width, bool) or not isinstance(width, (int, float)):
            raise TypeError("width must be a positive number")
        if not math.isfinite(float(width)) or width <= 0:
            raise ValueError("width must be greater than zero")

    @staticmethod
    def _validate_dpi(dpi: int) -> int:
        if isinstance(dpi, bool) or not isinstance(dpi, int):
            raise TypeError("dpi must be a positive integer")
        if dpi <= 0:
            raise ValueError("dpi must be greater than zero")
        return dpi

    @classmethod
    def _validate_error_correction(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("error_correction must be one of L, M, Q, or H")
        normalized = value.upper()
        if normalized not in cls._ERROR_CORRECTION:
            raise ValueError("error_correction must be one of L, M, Q, or H")
        return normalized

    @staticmethod
    def _validate_border(border: int) -> int:
        if isinstance(border, bool) or not isinstance(border, int):
            raise TypeError("border must be an integer of at least 4 modules")
        if border < 4:
            raise ValueError("border must be at least 4 modules")
        return border

    @classmethod
    def _validate_logo_size_ratio(cls, ratio: float) -> float:
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
            raise TypeError("logo_size_ratio must be a positive number")
        if not math.isfinite(float(ratio)) or not 0 < ratio <= cls._MAX_LOGO_RATIO:
            raise ValueError(f"logo_size_ratio must be greater than zero and no greater than {cls._MAX_LOGO_RATIO}")
        return float(ratio)

    @classmethod
    def _load_logo(cls, logo_path: str | os.PathLike[str] | None) -> tuple[Path | None, Image.Image | None]:
        if logo_path is None:
            return None, None
        if isinstance(logo_path, bool) or not isinstance(logo_path, (str, os.PathLike)):
            raise TypeError("logo_path must be a file path or None")

        path = Path(logo_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"logo image was not found at {path}")
        try:
            with Image.open(path) as source:
                if source.width * source.height > cls._MAX_LOGO_SOURCE_PIXELS:
                    raise ValueError("logo image is too large")
                logo = ImageOps.exif_transpose(source).convert("RGBA")
                logo.load()
        except OSError as exc:
            raise ValueError(f"logo image could not be read from {path}") from exc
        return path, logo

    @staticmethod
    def _parse_color(value: str | Sequence[int], parameter: str) -> tuple[int, int, int]:
        try:
            rgb = ImageColor.getrgb(value) if isinstance(value, str) else tuple(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid {parameter}: {value!r}") from exc
        if len(rgb) != 3 or any(
                isinstance(channel, bool)
                or not isinstance(channel, int)
                or not 0 <= channel <= 255
                for channel in rgb
        ):
            raise ValueError(f"{parameter} must be a Pillow RGB color string or an RGB integer tuple")
        return tuple(rgb)

    @staticmethod
    def _relative_luminance(color: tuple[int, int, int]) -> float:
        channels = []
        for channel in color:
            normalized = channel / 255.0
            channels.append(normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    @classmethod
    def _validate_contrast(cls, color: tuple[int, int, int], background: tuple[int, int, int]) -> None:
        foreground_luminance = cls._relative_luminance(color)
        background_luminance = cls._relative_luminance(background)
        if foreground_luminance >= background_luminance:
            raise ValueError("color must be darker than background")
        contrast = (background_luminance + 0.05) / (foreground_luminance + 0.05)
        if contrast < cls._MIN_CONTRAST_RATIO:
            raise ValueError(f"color and background contrast ratio must be at least {cls._MIN_CONTRAST_RATIO}:1")

    def _make_code(self, data: str | bytes) -> qrcode.QRCode:
        code = qrcode.QRCode(
            version=None,
            error_correction=self._ERROR_CORRECTION[self.error_correction],
            box_size=1,
            border=self.border
        )
        code.add_data(data)
        try:
            code.make(fit=True)
        except (DataOverflowError, ValueError) as exc:
            raise ValueError("data is too large for a QR code") from exc
        return code

    def _required_module_pixels(self) -> int:
        physical_minimum = math.ceil(self._MIN_MODULE_SIZE_MM * self.dpi / 25.4)
        return max(self._MIN_MODULE_PIXELS, physical_minimum)

    def _embed_logo(self, image: Image.Image, active_module_count: int, module_pixels: int) -> Image.Image:
        if self._logo_image is None:
            return image

        logo_box_pixels = max(1, round(active_module_count * module_pixels * self.logo_size_ratio))
        plaque_modules = math.ceil(logo_box_pixels / module_pixels) + 2
        if plaque_modules % 2 == 0:
            plaque_modules += 1
        plaque_pixels = plaque_modules * module_pixels
        plaque_left = (image.width - plaque_pixels) // 2

        result = image.convert("RGBA")
        plaque_color = ((0, 0, 0, 0) if self.background is None else (*self.background, 255))
        plaque = Image.new("RGBA", (plaque_pixels, plaque_pixels), plaque_color)
        result.paste(plaque, (plaque_left, plaque_left))

        logo = ImageOps.contain(self._logo_image, (logo_box_pixels, logo_box_pixels), method=Image.Resampling.LANCZOS)
        logo_position = ((result.width - logo.width) // 2, (result.height - logo.height) // 2)
        result.alpha_composite(logo, logo_position)
        return result if self.background is None else result.convert("RGB")

    def render_png(self, data: str | bytes, width: float) -> bytes:
        """Return QR code PNG bytes at the requested square width in points."""

        self._validate_data(data)
        self._validate_width(width)

        pixel_size = max(1, round(float(width) * self.dpi / 72.0))
        if pixel_size * pixel_size > self._MAX_IMAGE_PIXELS:
            raise ValueError("width and dpi produce an image that is too large; reduce width or dpi")

        code = self._make_code(data)
        module_count = code.modules_count + 2 * self.border
        required_module_pixels = self._required_module_pixels()
        module_pixels = pixel_size // module_count
        if module_pixels < required_module_pixels:
            minimum_width = (module_count * required_module_pixels * 72.0 / self.dpi)
            raise ValueError(f"width is too small for this data and dpi; use at least {minimum_width:.3f} points")

        code.box_size = module_pixels
        transparent = self.background is None
        rendered = code.make_image(fill_color=self.color,
                                   back_color="transparent" if transparent else self.background).get_image()
        mode = "RGBA" if transparent else "RGB"
        rendered = rendered.convert(mode)
        rendered = self._embed_logo(rendered, active_module_count=code.modules_count, module_pixels=module_pixels)

        canvas_color = (0, 0, 0, 0) if transparent else self.background
        image = Image.new(mode, (pixel_size, pixel_size), canvas_color)
        offset = (pixel_size - rendered.width) // 2
        image.paste(rendered, (offset, offset))

        output = BytesIO()
        image.save(output, format="PNG", dpi=(self.dpi, self.dpi), optimize=False, compress_level=6)
        return output.getvalue()

    def save_png(self, data: str | bytes, output_path: str | os.PathLike[str], width: float) -> Path:
        """Save a QR code of ``width`` points as PNG and return its path."""

        path = Path(output_path)
        png = self.render_png(data=data, width=width)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
        return path

    def make_inline_image(self, template, data: str | bytes, width: float):
        """Return a square docxtpl ``InlineImage`` at ``width`` points."""

        try:
            from docx.shared import Pt
            from docxtpl import InlineImage
        except ImportError as exc:
            raise RuntimeError("make_inline_image requires docxtpl and python-docx") from exc

        stream = BytesIO(self.render_png(data=data, width=width))
        return InlineImage(template, stream, width=Pt(float(width)))


HeightRule = Literal["auto", "atLeast", "exact"]
WidthSource = Literal["cell", "percentage", "grid", "unknown"]


@dataclass(frozen=True)
class FieldCell:
    """Location and declared geometry of one field-containing cell."""

    field: str
    part: str
    table: int
    row: int
    cell: int
    column: int
    column_span: int
    width: int | None
    height: int | None
    height_rule: HeightRule
    width_source: WidthSource

    @property
    def width_pt(self) -> float | None:
        return None if self.width is None else self.width / 20

    @property
    def height_pt(self) -> float | None:
        return None if self.height is None else self.height / 20


class TemplateGeometry:
    """Inspect table-cell geometry for fields in a docxtpl DOCX template.

    Typical use::

        geometry = TemplateGeometry("template.docx")
        client = geometry.get("Client")
        print(client.width_pt, client.height_pt)
    """

    _WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _NS = {"w": _WORD_NS}
    _W = f"{{{_WORD_NS}}}"
    _FIELD_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}", re.DOTALL)
    _NAME_RE = re.compile(r"[A-Za-z_]\w*")
    _PART_RE = re.compile(
        r"word/(?:document|header\d+|footer\d+)\.xml$"
    )

    def __init__(self, docx_path: str | Path) -> None:
        self.path = Path(docx_path)
        if not self.path.is_file():
            raise FileNotFoundError(f"Word template not found: {self.path}")
        self._cells = self._scan()

    @property
    def fields(self) -> tuple[str, ...]:
        """Field names found inside table cells, sorted case-insensitively."""
        return tuple(sorted((items[0].field for items in self._cells.values()), key=str.casefold))

    def find(self, field: str) -> tuple[FieldCell, ...]:
        """Return all cells containing ``field``; return an empty tuple if absent."""
        # Jinja fields are case-sensitive: SAMPLENAME is the cover field,
        # while SampleName is a separate, narrower cell on the first page.
        return self._cells.get(self._field_name(field), ())

    def get(self, field: str, occurrence: int = 0) -> FieldCell:
        """Return one occurrence of ``field`` or raise a descriptive exception."""
        matches = self.find(field)
        if not matches:
            raise KeyError(f"Field {field!r} is not inside a table cell")
        try:
            return matches[occurrence]
        except IndexError:
            raise IndexError(
                f"Field {field!r} has {len(matches)} occurrence(s); index {occurrence} is out of range") from None

    def _scan(self) -> dict[str, tuple[FieldCell, ...]]:
        index: defaultdict[str, list[FieldCell]] = defaultdict(list)
        with ZipFile(self.path) as archive:
            parts = (name for name in archive.namelist() if self._PART_RE.fullmatch(name))
            for part in parts:
                root = etree.fromstring(archive.read(part))
                tables = root.xpath(".//w:tbl", namespaces=self._NS)
                for table_number, table in enumerate(tables, 1):
                    self._scan_table(index, part, table_number, table)
        return {name: tuple(cells) for name, cells in index.items()}

    @classmethod
    def _scan_table(cls, index: defaultdict[str, list[FieldCell]], part: str, table_number: int,
                    table: etree._Element) -> None:
        grid = [
            cls._attribute_int(item, "w", 0) or 0
            for item in table.xpath("./w:tblGrid/w:gridCol", namespaces=cls._NS)
        ]
        table_width = cls._table_width(table, grid)

        for row_number, row in enumerate(table.xpath("./w:tr", namespaces=cls._NS), 1):
            height, height_rule = cls._row_height(row)
            column = cls._attribute_int(row.find("./w:trPr/w:gridBefore", cls._NS), "val", 0) or 0

            for cell_number, cell in enumerate(row.xpath("./w:tc", namespaces=cls._NS), 1):
                span = cls._attribute_int(cell.find("./w:tcPr/w:gridSpan", cls._NS), "val", 1) or 1
                width, width_source = cls._cell_width(cell, grid, column, span, table_width)

                for field in cls._cell_fields(cell):
                    index[field].append(
                        FieldCell(
                            field=field,
                            part=part,
                            table=table_number,
                            row=row_number,
                            cell=cell_number,
                            column=column + 1,
                            column_span=span,
                            width=width,
                            height=height,
                            height_rule=height_rule,
                            width_source=width_source,
                        )
                    )
                column += span

    @classmethod
    def _field_name(cls, value: str) -> str:
        """Normalize ``Client`` or ``{{p Client}}`` to ``Client``."""
        value = value.strip()
        tag = cls._FIELD_RE.fullmatch(value)
        expression = tag.group(1).strip() if tag else value
        expression = re.sub(
            r"^[pr]\s+",
            "",
            expression,
            flags=re.IGNORECASE,
        )
        match = cls._NAME_RE.match(expression)
        if not match:
            raise ValueError(f"Invalid field name: {value!r}")
        return match.group()

    @classmethod
    def _cell_fields(cls, cell: etree._Element) -> set[str]:
        """Read fields belonging to this cell, excluding nested-table cells."""
        text_nodes = []
        for text_node in cell.xpath(".//w:t", namespaces=cls._NS):
            nearest_cell = next(text_node.iterancestors(tag=cls._W + "tc"), None)
            if nearest_cell is cell:
                text_nodes.append(text_node.text or "")

        fields = set()
        for expression in cls._FIELD_RE.findall("".join(text_nodes)):
            try:
                fields.add(cls._field_name(expression))
            except ValueError:
                pass
        return fields

    @classmethod
    def _attribute_int(cls, element: etree._Element | None, attribute: str, default: int | None = None) -> int | None:
        if element is None:
            return default
        value = element.get(cls._W + attribute)
        return int(value) if value and value.lstrip("-").isdigit() else default

    @classmethod
    def _table_width(cls, table: etree._Element, grid: list[int]) -> int | None:
        width = table.find("./w:tblPr/w:tblW", cls._NS)
        if width is not None and width.get(cls._W + "type", "dxa") == "dxa":
            return cls._attribute_int(width, "w")
        return sum(grid) or None

    @classmethod
    def _cell_width(cls, cell: etree._Element, grid: list[int], column: int, span: int, table_width: int | None) -> \
            tuple[int | None, WidthSource]:
        width = cell.find("./w:tcPr/w:tcW", cls._NS)
        value = cls._attribute_int(width, "w")
        width_type = width.get(cls._W + "type", "dxa") if width is not None else None

        if value is not None and width_type == "dxa":
            return value, "cell"
        if value is not None and width_type == "pct" and table_width is not None:
            return round(table_width * value / 5000), "percentage"
        if column + span <= len(grid):
            return sum(grid[column: column + span]), "grid"
        return None, "unknown"

    @classmethod
    def _row_height(cls, row: etree._Element) -> tuple[int | None, HeightRule]:
        heights = row.xpath("./w:trPr/w:trHeight", namespaces=cls._NS)
        if not heights:
            return None, "auto"
        height = heights[-1]
        rule = height.get(cls._W + "hRule", "atLeast")
        if rule not in {"atLeast", "exact"}:
            rule = "atLeast"
        return cls._attribute_int(height, "val"), rule


_TagKind = Literal["plain", "r", "p"]


@dataclass(frozen=True)
class _ValidationDetail:
    """One internal validation failure."""

    code: str
    message: str
    part: str
    paragraph: int
    tag: str | None = None
    field: str | None = None

    def __str__(self) -> str:
        location = f"{self.part}, paragraph {self.paragraph}"
        return f"{self.code}: {self.message} ({location})"


class ValidationError(ValueError):
    """Raised with every failure found during one validation pass."""

    def __init__(self, details: tuple[_ValidationDetail, ...]) -> None:
        self.details = details
        super().__init__("\n".join(str(detail) for detail in details))


@dataclass(frozen=True)
class _TagLocation:
    """Location of one simple variable tag in a Word XML part."""

    field: str
    kind: _TagKind
    tag: str
    part: str
    paragraph: int


@dataclass(frozen=True)
class _FieldRequirement:
    """Tag-kind requirement aggregated across every occurrence of one field."""

    field: str
    kinds: frozenset[_TagKind]
    locations: tuple[_TagLocation, ...]

    @property
    def kind(self) -> _TagKind | None:
        """Return the single required kind, or ``None`` when kinds conflict."""
        return next(iter(self.kinds)) if len(self.kinds) == 1 else None


class TemplateValidator:
    """Parse a DOCX once and validate its tags against any render context.
    Reusable preflight validation for Jinja/docxtpl Word templates.

    Typical use::

        validator = TemplateValidator("template.docx")
        validator.validate()  # once per template version
        validator.validate(context, autoescape=True)  # before every render

    ``TemplateValidator`` parses the DOCX only once, so the same template can be
    checked efficiently against multiple render contexts.
    """

    _WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    _REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    _NS = {"w": _WORD_NS}
    _W = f"{{{_WORD_NS}}}"
    _PART_RE = re.compile(r"word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml$")
    _VARIABLE_TAG_RE = re.compile(r"{{\s*(?:(?P<kind>[pr])\s+)?(?P<expression>(?:(?!}}).)*?)\s*}}", re.DOTALL)
    _SIMPLE_NAME_RE = re.compile(r"[A-Za-z_]\w*")

    def __init__(self, docx_path: str | Path) -> None:
        self.path = Path(docx_path)
        if not self.path.is_file():
            raise FileNotFoundError(f"Word template not found: {self.path}")
        static_issues, occurrences = self._scan_template()
        requirements = self._build_field_requirements(occurrences)
        static_issues += tuple(self._inconsistent_field_issues(requirements))
        self._requirements = requirements
        self._template_errors = static_issues

    def validate(self, context: Mapping[str, object] | None = None, *, autoescape: bool = True) -> None:
        """Validate the template, or validate a supplied render context.

        Cached template errors are always checked. With a context, field value
        types are also checked without repeating the template scan. Fields
        missing from either side are ignored. ``autoescape`` must match the
        value passed to ``DocxTemplate.render``.
        """
        errors = self._template_errors
        if context is not None:
            errors += tuple(
                error
                for requirement in self._requirements.values()
                if (error := self._context_issue(context, requirement, autoescape=autoescape)) is not None
            )

        if errors:
            raise ValidationError(errors)

    def _scan_template(self) -> tuple[tuple[_ValidationDetail, ...], tuple[_TagLocation, ...]]:
        issues: list[_ValidationDetail] = []
        occurrences: list[_TagLocation] = []

        with ZipFile(self.path) as archive:
            for part in archive.namelist():
                if not self._PART_RE.fullmatch(part):
                    continue
                root = etree.fromstring(archive.read(part))
                paragraphs = root.xpath(".//w:p", namespaces=self._NS)
                for paragraph_number, paragraph in enumerate(paragraphs, 1):
                    text = self._paragraph_text(paragraph)
                    if not text:
                        continue
                    paragraph_issues, paragraph_occurrences = self._check_paragraph(text, part, paragraph_number)
                    issues.extend(paragraph_issues)
                    occurrences.extend(paragraph_occurrences)

        # Let docxtpl/Jinja perform its own grammar check after docxtpl has
        # joined tags that Word split across text nodes.
        try:
            DocxTemplate(str(self.path)).get_undeclared_template_variables()
        except TemplateError as error:
            issues.append(_ValidationDetail(code="JINJA_SYNTAX", message=str(error), part="template", paragraph=0))

        return tuple(issues), tuple(occurrences)

    @classmethod
    def _paragraph_text(cls, paragraph: etree._Element) -> str:
        text_parts: list[str] = []

        for text_node in paragraph.xpath(".//w:t", namespaces=cls._NS):
            # A drawing/text box can contain another paragraph. Do not mix its
            # text into the outer paragraph while validating tag boundaries.
            nearest_paragraph = next(text_node.iterancestors(tag=cls._W + "p"), None)
            if nearest_paragraph is not paragraph:
                continue

            value = text_node.text or ""
            text_parts.append(value)

        return "".join(text_parts)

    @classmethod
    def _check_paragraph(cls, text: str, part: str, paragraph: int) -> tuple[
        list[_ValidationDetail], list[_TagLocation]]:
        issues: list[_ValidationDetail] = []
        occurrences: list[_TagLocation] = []

        for match in cls._VARIABLE_TAG_RE.finditer(text):
            tag = match.group(0)
            kind: _TagKind = match.group("kind") or "plain"
            expression = match.group("expression").strip()
            field = cls._simple_field_name(expression)

            if not expression:
                issues.append(
                    _ValidationDetail(
                        code="EMPTY_VARIABLE_TAG",
                        message=f"{tag} has no expression. Add a context field or remove the empty tag.",
                        part=part,
                        paragraph=paragraph,
                        tag=tag,
                    )
                )
            elif field is not None:
                occurrences.append(_TagLocation(kind=kind, field=field, tag=tag, part=part, paragraph=paragraph))
            elif kind in {"p", "r"}:
                issues.append(
                    _ValidationDetail(
                        code="RICH_TAG_EXPRESSION_NOT_CHECKABLE",
                        message=(
                            f"{tag} uses a complex expression. Its result type "
                            "cannot be verified safely; use a simple context field for p/r tags."
                        ),
                        part=part,
                        paragraph=paragraph,
                        tag=tag,
                    )
                )

            if kind == "p":
                outside = text[: match.start()] + text[match.end():]
                if outside.strip():
                    issues.append(
                        _ValidationDetail(
                            code="P_TAG_NOT_ALONE",
                            message=(
                                "A {{p ...}} tag replaces its entire Word "
                                "paragraph and must be the paragraph's only visible content."
                            ),
                            part=part,
                            paragraph=paragraph,
                            tag=tag,
                            field=field,
                        )
                    )

        return issues, occurrences

    @staticmethod
    def _build_field_requirements(occurrences: tuple[_TagLocation, ...]) -> dict[str, _FieldRequirement]:
        by_field: defaultdict[str, list[_TagLocation]] = defaultdict(list)
        for occurrence in occurrences:
            by_field[occurrence.field].append(occurrence)

        return {
            field: _FieldRequirement(
                field=field,
                kinds=frozenset(item.kind for item in items),
                locations=tuple(items),
            )
            for field, items in by_field.items()
        }

    @staticmethod
    def _inconsistent_field_issues(requirements: Mapping[str, _FieldRequirement]) -> list[_ValidationDetail]:
        issues: list[_ValidationDetail] = []
        kind_order = {"plain": 0, "r": 1, "p": 2}
        for field, requirement in requirements.items():
            if requirement.kind is not None:
                continue

            first = requirement.locations[0]
            kind_list = ", ".join(
                sorted(requirement.kinds, key=kind_order.__getitem__)
            )
            locations = "; ".join(
                f"{location.kind} at {location.part} paragraph {location.paragraph}"
                for location in requirement.locations[:8]
            )
            if len(requirement.locations) > 8:
                locations += f"; and {len(requirement.locations) - 8} more"
            issues.append(
                _ValidationDetail(
                    code="INCONSISTENT_FIELD_TAG_KIND",
                    message=(
                        f"Field {field!r} uses inconsistent tag kinds "
                        f"({kind_list}). One context value cannot satisfy all "
                        f"required OOXML types. Occurrences: {locations}."
                    ),
                    part=first.part, paragraph=first.paragraph, tag=first.tag, field=field
                )
            )
        return issues

    @classmethod
    def _simple_field_name(cls, expression: str) -> str | None:
        match = cls._SIMPLE_NAME_RE.fullmatch(expression)
        return None if match is None else match.group(0)

    @classmethod
    def _context_issue(cls, context: Mapping[str, object], requirement: _FieldRequirement, *,
                       autoescape: bool) -> _ValidationDetail | None:
        kind = requirement.kind
        if kind is None:
            return None
        field = requirement.field
        first = requirement.locations[0]
        occurrence_count = len(requirement.locations)

        if field not in context:
            return None

        value = context[field]
        if kind == "p":
            valid = cls._is_subdoc(value) or (
                    isinstance(value, RichTextParagraph) and cls._valid_rich_fragment_top_level(str(value), kind="p")
            )
            expected = "RichTextParagraph with top-level w:p elements, or a docxtpl Subdoc"
        elif kind == "r":
            valid = isinstance(value, RichText) and cls._valid_rich_fragment_top_level(str(value), kind="r")
            expected = "RichText with top-level w:r/w:hyperlink elements"
        else:
            valid = (
                    isinstance(value, (InlineImage, Listing))
                    or (isinstance(value, Markup) and not cls._plain_text_requires_escaping(str(value)))
                    or (
                            not isinstance(value, (RichText, RichTextParagraph)) and not cls._is_subdoc(value)
                            and not callable(getattr(value, "__html__", None))
                    )
            )
            expected = (
                "a normal value, safely escaped Markup, docxtpl InlineImage, "
                "or docxtpl Listing (use {{r ...}} for RichText and {{p ...}} for RichTextParagraph/Subdoc)"
            )

        if not valid:
            return _ValidationDetail(
                code="TAG_VALUE_TYPE_MISMATCH",
                message=(
                    f"Field {field!r} uses {first.tag} and occurs {occurrence_count} time(s); it requires {expected}, "
                    f"but the context value is {type(value).__name__}."
                ),
                part=first.part, paragraph=first.paragraph, tag=first.tag, field=field
            )

        if (
                kind == "plain" and not autoescape and not isinstance(value, (InlineImage, Listing, Markup))
                and cls._plain_text_requires_escaping(str(value))
        ):
            return _ValidationDetail(
                code="PLAIN_TEXT_REQUIRES_AUTOESCAPE",
                message=(
                    f"Field {field!r} contains unescaped XML metacharacters "
                    "or invalid XML text while autoescape is disabled. Enable "
                    "autoescape, use the |e filter, or escape the value before rendering."
                ),
                part=first.part, paragraph=first.paragraph, tag=first.tag, field=field
            )

        return None

    @staticmethod
    def _is_subdoc(value: object) -> bool:
        """Return whether *value* is a Subdoc without requiring its extra."""
        return Subdoc is not None and isinstance(value, Subdoc)

    @staticmethod
    def _plain_text_requires_escaping(value: str) -> bool:
        """Check whether text is unsafe in the XML text node used by docxtpl.

        Parsing, instead of merely looking for ``&``, accepts correctly escaped
        XML entities produced by :func:`html.escape` and ``Markup.escape`` while
        still rejecting raw markup, incomplete entities, and invalid controls.
        A literal ``>`` is rejected to match docxtpl's documented escaping
        contract even though XML permits it in most text-node positions.
        """
        if "<" in value or ">" in value:
            return True
        try:
            root = etree.fromstring(f"<root>{value}</root>".encode("utf-8"))
        except (UnicodeEncodeError, etree.XMLSyntaxError):
            return True

        return bool(list(root))

    @classmethod
    def _valid_rich_fragment_top_level(cls, fragment: str, kind: Literal["p", "r"]) -> bool:
        if kind == "p" and not fragment.strip():
            return False

        wrapper = f'<root xmlns:w="{cls._WORD_NS}" xmlns:r="{cls._REL_NS}">{fragment}</root>'
        try:
            root = etree.fromstring(wrapper.encode("utf-8"))
        except etree.XMLSyntaxError:
            return False

        if root.text and root.text.strip():
            return False
        if any(child.tail and child.tail.strip() for child in root):
            return False

        allowed = {cls._W + "p"} if kind == "p" else {cls._W + "r", cls._W + "hyperlink"}
        children = list(root)
        if kind == "p" and not children:
            return False
        return all(child.tag in allowed for child in children)


__all__ = [
    "CmaMarkRenderer",
    "QrCodeRenderer",
    "HeightRule",
    "WidthSource",
    "FieldCell",
    "TemplateGeometry",
    "ValidationError",
    "TemplateValidator",
]
