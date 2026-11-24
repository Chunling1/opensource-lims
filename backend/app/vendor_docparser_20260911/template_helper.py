import math
import unicodedata
import cn2an
from typing import Any
from enum import Enum, unique
from pathlib import Path
from docxtpl import DocxTemplate, RichTextParagraph, InlineImage
from docx.shared import Pt
from PIL import Image, ImageOps
from template_utils import TemplateGeometry, FieldCell, TemplateValidator, CmaMarkRenderer, QrCodeRenderer

ASSETS_DIR = Path(__file__).resolve().parent / 'assets'


@unique
class FontSize(Enum):
    XL = 12  # pt
    L = 11
    M = 10
    S = 9
    XS = 8
    XXS = 7
    XXXS = 6
    XXXXS = 5


class TemplateHelper:
    IMAGE_DEFAULT_DPI = 96.0

    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        self._geometry = TemplateGeometry(docx_path)
        self._content = kwargs
        self._validator = TemplateValidator(docx_path)
        if check_docx:
            self._validator.validate()
        self._template = DocxTemplate(docx_path)

    def paragraph(self, text_name: str, styles: list[str], *, sep: str | None = None) -> RichTextParagraph:
        text = self._content.get(text_name, '')
        rtp = RichTextParagraph()
        length = len(styles)
        if sep is None or sep == '':
            rtp.add(text, styles[0])
        else:
            texts = text.split(sep)
            for i, txt in enumerate(texts):
                rtp.add(txt, styles[i % length])
        return rtp

    def get_field_paragraph(self, text: str, field_name: str, field_index: int,
                            font_range: tuple[FontSize, FontSize]) -> RichTextParagraph:
        cell = self._geometry.get(field_name, field_index)
        p = self.build_paragraph(text, cell, font_range)
        rtp = RichTextParagraph()
        rtp.add(p[0], parastyle=p[1])
        return rtp

    def field_paragraph(self, text_name: str, field_name: str | None = None, field_index: int = 0, *,
                        font_range: tuple[FontSize, FontSize] = (FontSize.XL, FontSize.XXXXS)) -> RichTextParagraph:
        text = self._content.get(text_name, '')
        return self.get_field_paragraph(text, text_name if field_name is None else field_name, field_index, font_range)

    def fields_paragraph(self, text_names: list[str], field_name: str, field_index: int = 0, *, sep: str = '\n',
                         font_range: tuple[FontSize, FontSize] = (FontSize.XL, FontSize.XXXXS)) -> RichTextParagraph:
        text = sep.join([self._content.get(text_name, '') for text_name in text_names])
        return self.get_field_paragraph(text, field_name, field_index, font_range)

    def plaintext(self, text_name: str, max_length: int = 0) -> str:
        text = str(self._content.get(text_name, ''))
        return self.strip_text(text, max_length)

    def plaintext_from_fields(self, text_names: list[str], max_length: int = 0, *, sep: str = '\n') -> str:
        text = sep.join([str(self._content.get(text_name, '')) for text_name in text_names])
        return self.strip_text(text, max_length)

    def boolean(self, text_name: str) -> bool:
        if self._content.get(text_name, False):
            return True
        return False

    @classmethod
    def get_valid_dpi(cls, value: object) -> float:
        try:
            dpi = float(value)
        except (TypeError, ValueError):
            return cls.IMAGE_DEFAULT_DPI

        return dpi if dpi > 0 else cls.IMAGE_DEFAULT_DPI

    @classmethod
    def get_image_size(cls, image_path: str | Path) -> dict[str, float]:
        with Image.open(image_path) as image:
            width_px, height_px = ImageOps.exif_transpose(image).size
            dpi = image.info.get("dpi")

        if not isinstance(dpi, (tuple, list)) or len(dpi) != 2:
            dpi = (cls.IMAGE_DEFAULT_DPI, cls.IMAGE_DEFAULT_DPI)

        dpi_x, dpi_y = map(cls.get_valid_dpi, dpi)

        return {"width_pt": width_px * 72 / dpi_x, "height_pt": height_px * 72 / dpi_y}

    @staticmethod
    def scaled_size(src_width: float, src_height: float, dst_width: float | None, dst_height: float | None, *,
                    allow_upscale: bool = True) -> tuple[float, float]:
        scales = []
        if dst_width is not None:
            scales.append(dst_width / src_width)
        if dst_height is not None:
            scales.append(dst_height / src_height)

        scale = min(scales, default=1.0)
        if not allow_upscale:
            scale = min(scale, 1.0)
        return src_width * scale, src_height * scale

    def inline_image(self, image_path: str | Path, *, mode: str = "scale-down", width: float | None = None,
                     height: float | None = None) -> InlineImage:
        """Return an image value sized for insertion into a docxtpl template.
        ``width`` and ``height`` are measured in points.
        - ``fill`` uses the requested dimensions exactly and may distort the image.
        - ``contain`` scales proportionally to fit inside the requested bounds.
        - ``none`` ignores requested bounds and uses the image's physical size.
        - ``scale-down`` behaves like ``contain`` but never enlarges the image.
        """
        image_path = Path(image_path)
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")

        size = self.get_image_size(image_path)
        src_width = size["width_pt"]
        src_height = size["height_pt"]

        if mode == "fill":
            dst_width = width
            dst_height = height
        elif mode == "contain":
            dst_width, dst_height = self.scaled_size(src_width, src_height, width, height)
        elif mode == "none":
            dst_width, dst_height = src_width, src_height
        else:  # scale-down
            dst_width, dst_height = self.scaled_size(src_width, src_height, width, height, allow_upscale=False)
        return InlineImage(self._template, str(image_path), width=None if dst_width is None else Pt(dst_width),
                           height=None if dst_height is None else Pt(dst_height))

    @staticmethod
    def get_display_length(text: str, tab_width: int = 4) -> int:
        width = 0
        for char in text:
            if char == "\t":
                width += tab_width - width % tab_width
            elif unicodedata.combining(char):
                continue
            elif unicodedata.east_asian_width(char) in {"F", "W"}:
                width += 2
            elif not unicodedata.category(char).startswith("C"):
                width += 1
        return width

    @classmethod
    def strip_text(cls, text: str, max_length: int) -> str:
        length = cls.get_display_length(text)
        if max_length > 0:
            while length > max_length:
                text = text[:-(length - max_length + 1) // 2]
                length = cls.get_display_length(text)
        return text

    @staticmethod
    def format_parastyle(font: FontSize, line_height: int) -> str:
        return '{}-{}-left'.format(font.name.lower(), line_height)

    @staticmethod
    def normalize_rich_text(text: str) -> str:
        return text.replace('\r\n', '\n').replace('\r', ' ').replace('\a', '\n')

    @classmethod
    def cell_line_count(cls, value: str, line_width: int) -> int:
        physical_lines = cls.normalize_rich_text(value).split('\n')
        if line_width < 1:
            line_width = 1
        return sum(
            max(1, math.ceil(cls.get_display_length(line) / line_width))
            for line in physical_lines
        )

    @classmethod
    def get_lines(cls, text: str, font: FontSize, cell: FieldCell) -> int | None:
        if cell.width_pt is None:
            return None
        text = cls.normalize_rich_text(text)
        if '\f' in text:
            return None
        capacity = max(1, int(cell.width_pt / font.value) * 2 - 5)
        return cls.cell_line_count(text, capacity)

    @classmethod
    def get_parastyle(cls, text: str, cell: FieldCell, font_range: tuple[FontSize, FontSize]) -> str | None:
        if cell.width_pt is None:
            return None
        if cell.height_rule in ('exact', 'atLeast'):
            if cell.height_pt is None:
                return None
            height_limit = cell.height_pt
        else:
            height_limit = float('inf')
        if font_range[0].value > font_range[1].value:
            max_font = font_range[0].value
            min_font = font_range[1].value
        else:
            max_font = font_range[1].value
            min_font = font_range[0].value
        for font in FontSize:
            if font.value > max_font or font.value < min_font:
                continue
            lines = cls.get_lines(text, font, cell)
            if lines is None:
                return None
            for line_height in range(font.value + 3, font.value - 1, -1):
                if lines * line_height <= height_limit:
                    return cls.format_parastyle(font, line_height)
        return None

    @classmethod
    def build_paragraph(cls, text: str, cell: FieldCell, font_range: tuple[FontSize, FontSize]) -> tuple[str, str]:
        """Return normalized text and a style that fits ``cell``."""
        text = cls.normalize_rich_text(text)

        if cell.width_pt is None:
            raise ValueError("Cannot fit paragraph: cell width is unknown")
        if cell.height_rule in ('exact', 'atLeast') and cell.height_pt is None:
            raise ValueError("Cannot fit paragraph: declared cell height is unknown")
        if "\f" in text:
            raise ValueError("Cannot fit paragraph: page breaks (\\f) are not supported in a cell")

        parastyle = cls.get_parastyle(text, cell, font_range)
        if parastyle is None:
            min_font = min(font_range, key=lambda font: font.value)
            parastyle = cls.format_parastyle(min_font, min_font.value)
        return text, parastyle

    def render(self, context: dict[str, object], output_path: str | Path, autoescape: bool = True) -> str | Path:
        self._validator.validate(context, autoescape=autoescape)
        self._template.render(context, autoescape=autoescape)
        self._template.save(Path(output_path))
        return output_path


class EntrustMaker(TemplateHelper):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @staticmethod
    def is_jpg_or_png(file_path: str) -> bool:
        if not isinstance(file_path, str):
            return False

        path = Path(file_path)
        return path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}

    @staticmethod
    def format_amount(value):
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return "0.00"

    @property
    def _center(self):
        return self.plaintext('Center', 56)

    @property
    def _sample_no(self):
        return self.plaintext('SampleNo', 24)

    @property
    def _entrust_date(self):
        return self.plaintext('EntrustDate', 14)

    @property
    def _client(self):
        return self.field_paragraph('Client')

    @property
    def _sample_name(self):
        return self.field_paragraph('SampleName')

    @property
    def _model(self):
        return self.field_paragraph('Model')

    @property
    def _manufacturer(self):
        return self.field_paragraph('Manufacturer')

    @property
    def _manufacturing_date(self):
        return self.plaintext('ManufacturingDate', 14)

    @property
    def _serial(self):
        return self.field_paragraph('Serial')

    @property
    def _manufacturing_date_with_serial(self):
        return self.fields_paragraph(['ManufacturingDate', 'Serial'], 'Serial')

    @property
    def _submission_date(self):
        return self.plaintext('SubmissionDate', 14)

    @property
    def _category(self):
        return self.field_paragraph('Category')

    @property
    def _quantity(self):
        return self.field_paragraph('Quantity')

    @property
    def _trademark(self):
        text = self._content.get('Trademark', '')
        if self.is_jpg_or_png(text):
            cell = self._geometry.get('Trademark', 0)
            cell_height = max(1, cell.height_pt - 6) if cell.height_pt is not None else None
            return self.inline_image(text, width=cell.width_pt, height=cell_height)
        return self.plaintext('Trademark', 28)

    @property
    def _basis(self):
        return self.field_paragraph('Basis')

    @property
    def _criteria(self):
        return self.field_paragraph('Criteria')

    @property
    def _items(self):
        return self.field_paragraph('Items')

    @property
    def _technique(self):
        return self.boolean('TECHNIQUE')

    @property
    def _instrument(self):
        return self.boolean('INSTRUMENT')

    @property
    def _environment(self):
        return self.boolean('ENVIRONMENT')

    @property
    def _method(self):
        return self.boolean('METHOD')

    @property
    def _person(self):
        return self.boolean('PERSON')

    @property
    def _sample(self):
        return self.boolean('SAMPLE')

    @property
    def _scope(self):
        return self.boolean('SCOPE')

    @property
    def _cma(self):
        return self.boolean('CMA')

    @property
    def _cnas(self):
        return self.boolean('CNAS')

    @property
    def _signature(self):
        text = self._content.get('Signature', '')
        if self.is_jpg_or_png(text):
            return self.inline_image(text, width=120, height=20)
        return self.plaintext('Signature', 16)

    @property
    def _appearance(self):
        return self.plaintext('Appearance', 16)

    @property
    def _nameplate(self):
        return self.plaintext('Nameplate', 2)

    @property
    def _sample_handling(self):
        return self.plaintext('SampleHandling', 20)

    @property
    def _pickup(self):
        return self.boolean('PICKUP')

    @property
    def _report_quantity(self):
        return self.plaintext('ReportQuantity', 4)

    @property
    def _report_date(self):
        return self.plaintext('ReportDate', 14)

    @property
    def _amount(self):
        return self.format_amount(self._content.get('Amount', '0'))

    @property
    def _amount_in_words(self):
        return cn2an.an2cn(self._amount, 'rmb')

    @property
    def _payment(self):
        return self.plaintext('Payment', 24)

    @property
    def _remark(self):
        return self.field_paragraph('Remark')

    @property
    def _consignor(self):
        return self.plaintext('Consignor', 52)

    @property
    def _consignor_phone(self):
        return self.plaintext('ConsignorPhone', 48)

    @property
    def _client_address(self):
        return self.plaintext('ClientAddress', 106)

    @property
    def _party_a(self):
        return self.plaintext('PartyA', 110)

    @property
    def _payer(self):
        return self.plaintext('Payer', 102)

    @property
    def _handler(self):
        return self.plaintext('Handler', 32)

    @property
    def _phone(self):
        return self.plaintext('Phone', 34)

    @property
    def _department(self):
        return self.plaintext('Department', 150)

    @property
    def context(self):
        raise NotImplementedError()


class EntrustProduct(EntrustMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'Center': self._center,  # 国家中心
            'SampleNo': self._sample_no,  # 样品编号
            'EntrustDate': self._entrust_date,  # 委托日期
            'Client': self._client,  # 委托单位
            'SampleName': self._sample_name,  # 样品名称
            'Model': self._model,  # 规格型号
            'Manufacturer': self._manufacturer,  # 生产单位
            'Serial': self._manufacturing_date_with_serial,  # 生产日期/编号
            'SubmissionDate': self._submission_date,  # 送样日期
            'Category': self._category,  # 检验类别
            'Quantity': self._quantity,  # 样品数量
            'Trademark': self._trademark,  # 商标
            'Basis': self._basis,  # 检验依据
            'Criteria': self._criteria,  # 判定依据
            'Items': self._items,  # 检验项目
            'TECHNIQUE': self._technique,  # 技术能力
            'INSTRUMENT': self._instrument,  # 仪器设备
            'ENVIRONMENT': self._environment,  # 环境设施条件
            'METHOD': self._method,  # 方法
            'PERSON': self._person,  # 人员
            'SAMPLE': self._sample,  # 样品
            'SCOPE': self._scope,  # 检验依据授权
            'CMA': self._cma,  # 加盖CMA章
            'CNAS': self._cnas,  # 加盖CNAS章
            'Signature': self._signature,  # 签字
            'Appearance': self._appearance,  # 外观
            'Nameplate': self._nameplate,  # 铭牌
            'SampleHandling': self._sample_handling,  # 检验后样品处理要求
            'PICKUP': self._pickup,  # 提交报告方式
            'ReportQuantity': self._report_quantity,  # 报告份数
            'ReportDate': self._report_date,  # 报告时间
            'Amount': self._amount,  # 检验费用
            'AmountInWords': self._amount_in_words,  # 大写
            'Payment': self._payment,  # 交费情况
            'Remark': self._remark,  # 备注
            'Consignor': self._consignor,  # 委托人
            'ConsignorPhone': self._consignor_phone,  # 委托人电话
            'ClientAddress': self._client_address,  # 委托单位地址
            'PartyA': self._party_a,  # 合同甲方
            'Payer': self._payer,  # 其他甲方（付款方）
            'Handler': self._handler,  # 经手人
            'Phone': self._phone,  # 电话
            'Department': self._department,  # 试验室名称
        }


class EntrustEngineering(EntrustMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'Center': self._center,  # 国家中心
            'SampleNo': self._sample_no,  # 样品编号
            'EntrustDate': self._entrust_date,  # 委托日期
            'Client': self._client,  # 委托单位
            'SampleName': self._sample_name,  # 样品名称
            'Category': self._category,  # 检验类别
            'Basis': self._basis,  # 检验依据
            'Criteria': self._criteria,  # 判定依据
            'Items': self._items,  # 检验项目
            'TECHNIQUE': self._technique,  # 技术能力
            'INSTRUMENT': self._instrument,  # 仪器设备
            'ENVIRONMENT': self._environment,  # 环境设施条件
            'METHOD': self._method,  # 方法
            'PERSON': self._person,  # 人员
            'SAMPLE': self._sample,  # 样品
            'SCOPE': self._scope,  # 检验依据授权
            'CMA': self._cma,  # 加盖CMA章
            'CNAS': self._cnas,  # 加盖CNAS章
            'Signature': self._signature,  # 签字
            'Appearance': self._appearance,  # 外观
            'Nameplate': self._nameplate,  # 铭牌
            'SampleHandling': self._sample_handling,  # 检验后样品处理要求
            'PICKUP': self._pickup,  # 提交报告方式
            'ReportQuantity': self._report_quantity,  # 报告份数
            'ReportDate': self._report_date,  # 报告时间
            'Amount': self._amount,  # 检验费用
            'AmountInWords': self._amount_in_words,  # 大写
            'Payment': self._payment,  # 交费情况
            'Remark': self._remark,  # 备注
            'Consignor': self._consignor,  # 委托人
            'ConsignorPhone': self._consignor_phone,  # 委托人电话
            'ClientAddress': self._client_address,  # 委托单位地址
            'PartyA': self._party_a,  # 合同甲方
            'Payer': self._payer,  # 其他甲方（付款方）
            'Handler': self._handler,  # 经手人
            'Phone': self._phone,  # 电话
            'Department': self._department,  # 试验室名称
        }


class ReportMaker(TemplateHelper):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

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
    def is_docx(cls, file_path: str) -> bool:
        return cls.is_file_with_ext(file_path, [".docx"])

    def get_qr_code(self, text: Any, logo_path: str | None, width: int,
                    background: str | None = '#FFFFFF') -> InlineImage | str:
        if not isinstance(text, str) or text == '':
            return ''
        if isinstance(logo_path, str) and self.is_jpg_or_png(logo_path):
            renderer = QrCodeRenderer(logo_path=logo_path, background=background)
        else:
            renderer = QrCodeRenderer(background=background)
        return renderer.make_inline_image(self._template, text, width)

    @property
    def _cma_mark(self):
        text = self._content.get('CMAText', '')
        if self.get_display_length(text) == 12 and text.isdigit():
            renderer = CmaMarkRenderer()
            return renderer.make_inline_image(self._template, text, width=72)
        return ''

    @property
    def _cnas_mark(self):
        text = self._content.get('CNASText', '')
        mark_path = Path(ASSETS_DIR / 'images/cnas_ilac-mra.png')
        if self.get_display_length(text) > 0 and self.is_jpg_or_png(mark_path):
            return self.inline_image(mark_path, width=150)
        return ''

    @property
    def _cnas_text(self):
        return self.plaintext('CNASText', 42)

    @property
    def _cover_footer(self):
        styles = ['cover-footer-song', 'cover-footer-song-small', 'cover-footer-song-fs', 'cover-footer-song-small-5']
        return self.paragraph('CoverFooter', styles, sep='\n')

    @property
    def _page_header(self):
        styles = ['page-header-song', 'page-header-song-small']
        return self.paragraph('PageHeader', styles, sep='\n')

    @property
    def _SAMPLE_NAME(self):  # noqa
        return self.plaintext('SampleName', 110)

    @property
    def _CLIENT(self):  # noqa
        return self.plaintext('Client', 70)

    @property
    def _MANUFACTURER(self):  # noqa
        return self.plaintext('Manufacturer', 70)

    @property
    def _CATEGORY(self):  # noqa
        return self.plaintext('Category', 44)

    @property
    def _INSPECTED_UNIT(self):  # noqa
        return self.plaintext('InspectedUnit', 70)

    @property
    def _business_tel(self):
        return self.plaintext('BusinessTel', 50)

    @property
    def _fax(self):
        return self.plaintext('Fax', 36)

    @property
    def _email(self):
        return self.plaintext('Email', 70)

    @property
    def _report_no(self):
        return self.plaintext('ReportNo', 32)

    @property
    def _sample_name(self):
        return self.field_paragraph('SampleName', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _client(self):
        return self.field_paragraph('Client', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _manufacturer(self):
        return self.field_paragraph('Manufacturer', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _trademark(self):
        text = self._content.get('Trademark', '')
        if self.is_jpg_or_png(text):
            cell = self._geometry.get('Trademark', 0)
            return self.inline_image(text, width=cell.width_pt, height=cell.height_pt)
        return self.plaintext('Trademark', 60)

    @property
    def _model(self):
        return self.field_paragraph('Model', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _serial(self):
        return self.field_paragraph('Serial', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _place(self):
        return self.field_paragraph('Place', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _engineering_name(self):
        return self.field_paragraph('EngineeringName', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _sample_no(self):
        return self.plaintext('SampleNo', 24)

    @property
    def _category(self):
        return self.plaintext('Category', 44)

    @property
    def _quantity(self):
        return self.plaintext('Quantity', 44)

    @property
    def _sample_condition(self):
        return self.plaintext('SampleCondition', 44)

    @property
    def _manufacturing_date(self):
        return self.field_paragraph('ManufacturingDate', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _entrust_date(self):
        return self.plaintext('EntrustDate', 44)

    @property
    def _submission_date(self):
        return self.plaintext('SubmissionDate', 44)

    @property
    def _test_date(self):
        return self.field_paragraph('TestDate', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _client_address(self):
        return self.field_paragraph('ClientAddress', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _basis(self):
        return self.field_paragraph('Basis', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _criteria(self):
        return self.field_paragraph('Criteria', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _items(self):
        return self.field_paragraph('Items', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _instruments(self):
        return self.field_paragraph('Instruments', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _conclusion(self):
        text = self._content.get('Conclusion', '')
        if self.is_docx(text):
            return self._template.new_subdoc(text)
        return self.field_paragraph('Conclusion', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _report_date(self):
        return self.plaintext('ReportDate', 14)

    @property
    def _remark(self):
        return self.field_paragraph('Remark', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _report_qrcode(self):
        text = self._content.get('ReportQRCode', '')
        width = 72
        if isinstance(text, tuple) and len(text) >= 2:
            return self.get_qr_code(text[0], text[1], width, None)
        return self.get_qr_code(text, None, width, None)

    @property
    def _account_qrcode(self):
        text = self._content.get('AccountQRCode', '')
        width = 72
        if isinstance(text, tuple) and len(text) >= 2:
            return self.get_qr_code(text[0], text[1], width, None)
        return self.get_qr_code(text, None, width, None)

    @property
    def _original_report_date(self):
        return self.plaintext('OriginalReportDate', 14)

    @property
    def _sample_arrival_date(self):
        return self.plaintext('SampleArrivalDate', 28)

    @property
    def _sampling_unit(self):
        return self.field_paragraph('SamplingUnit', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _sampling_date(self):
        return self.plaintext('SamplingDate', 28)

    @property
    def _sampler(self):
        return self.plaintext('Sampler', 30)

    @property
    def _sampling_quantity(self):
        return self.plaintext('SamplingQuantity', 20)

    @property
    def _sampling_place(self):
        return self.field_paragraph('SamplingPlace', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _sampling_base(self):
        return self.plaintext('SamplingBase', 20)

    @property
    def _sealing_inspector(self):
        return self.plaintext('SealingInspector', 30)

    @property
    def _sealing_condition(self):
        return self.plaintext('SealingCondition', 20)

    @property
    def _task_source(self):
        return self.field_paragraph('TaskSource', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _sample_grade(self):
        return self.plaintext('SampleGrade', 20)

    @property
    def _inspected_unit(self):
        return self.field_paragraph('InspectedUnit', font_range=(FontSize.L, FontSize.XXXXS))

    @property
    def _calibration_date(self):
        return self.plaintext('CalibrationDate', 28)

    @property
    def _temperature(self):
        return self.plaintext('Temperature', 20)

    @property
    def _humidity(self):
        return self.plaintext('Humidity', 20)

    @property
    def _pressure(self):
        return self.plaintext('Pressure', 20)

    @property
    def context(self):
        raise NotImplementedError()


class ReportProduct(ReportMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'CMAMark': self._cma_mark,  # CMA标识
            'CNASMark': self._cnas_mark,  # CNAS标识
            'CNASText': self._cnas_text,  # CNAS说明
            'CoverFooter': self._cover_footer,  # 封面单位及中心信息
            'PageHeader': self._page_header,  # 正文单位及中心信息
            'SAMPLENAME': self._SAMPLE_NAME,
            'CLIENT': self._CLIENT,
            'MANUFACTURER': self._MANUFACTURER,
            'CATEGORY': self._CATEGORY,
            'BusinessTel': self._business_tel,  # 业务电话
            'Fax': self._fax,  # 传真
            'Email': self._email,  # E-mail
            'ReportNo': self._report_no,  # 报告编号
            'SampleName': self._sample_name,  # 样品名称
            'Client': self._client,  # 委托单位
            'Manufacturer': self._manufacturer,  # 生产单位
            'Trademark': self._trademark,  # 商标
            'Model': self._model,  # 规格型号
            'Serial': self._serial,  # 出厂编号
            'Place': self._place,  # 检测地点
            'EngineeringName': self._engineering_name,  # 工程名称
            'SampleNo': self._sample_no,  # 样品编号
            'Category': self._category,  # 检验类别
            'Quantity': self._quantity,  # 样品数量
            'SampleCondition': self._sample_condition,  # 样品状态
            'ManufacturingDate': self._manufacturing_date,  # 生产日期
            'EntrustDate': self._entrust_date,  # 委托日期
            'SubmissionDate': self._submission_date,  # 送样日期
            'TestDate': self._test_date,  # 检测日期
            'ClientAddress': self._client_address,  # 委托单位地址
            'Basis': self._basis,  # 检验依据
            'Criteria': self._criteria,  # 判定依据
            'Items': self._items,  # 检验项目
            'Instruments': self._instruments,  # 仪器设备
            'Conclusion': self._conclusion,  # 检测结论
            'ReportDate': self._report_date,  # 报告日期
            'Remark': self._remark,  # 备注
            'ReportQRCode': self._report_qrcode,  # 报告二维码
            'AccountQRCode': self._account_qrcode,  # 公众号二维码
            'OriginalReportDate': self._original_report_date,  # 原报告日期，仅更正报告需要传值
        }


class ReportSampling(ReportMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'CMAMark': self._cma_mark,  # CMA标识
            'CNASMark': self._cnas_mark,  # CNAS标识
            'CNASText': self._cnas_text,  # CNAS说明
            'CoverFooter': self._cover_footer,  # 封面单位及中心信息
            'PageHeader': self._page_header,  # 正文单位及中心信息
            'SAMPLENAME': self._SAMPLE_NAME,
            'CLIENT': self._CLIENT,
            'INSPECTEDUNIT': self._INSPECTED_UNIT,
            'MANUFACTURER': self._MANUFACTURER,
            'CATEGORY': self._CATEGORY,
            'BusinessTel': self._business_tel,  # 业务电话
            'Fax': self._fax,  # 传真
            'Email': self._email,  # E-mail
            'ReportNo': self._report_no,  # 报告编号
            'SampleName': self._sample_name,  # 样品名称
            'Client': self._client,  # 委托单位
            'Manufacturer': self._manufacturer,  # 生产单位
            'Trademark': self._trademark,  # 商标
            'Model': self._model,  # 规格型号
            'Serial': self._serial,  # 出厂编号
            'Place': self._place,  # 检测地点
            'SampleNo': self._sample_no,  # 样品编号
            'Category': self._category,  # 检验类别
            'Quantity': self._quantity,  # 样品数量
            'SampleCondition': self._sample_condition,  # 样品状态
            'SampleArrivalDate': self._sample_arrival_date,  # 样品到达日期
            'ManufacturingDate': self._manufacturing_date,  # 生产日期
            'EntrustDate': self._entrust_date,  # 委托日期
            'TestDate': self._test_date,  # 检测日期
            'SamplingUnit': self._sampling_unit,  # 抽样单位
            'SamplingDate': self._sampling_date,  # 抽样日期
            'Sampler': self._sampler,  # 抽样人
            'SamplingQuantity': self._sampling_quantity,  # 抽样数量
            'SamplingPlace': self._sampling_place,  # 抽样地点
            'SamplingBase': self._sampling_base,  # 抽样基数
            'SealingInspector': self._sealing_inspector,  # 检查封样人员
            'SealingCondition': self._sealing_condition,  # 封样状态
            'TaskSource': self._task_source,  # 任务来源
            'SampleGrade': self._sample_grade,  # 样品等级
            'ClientAddress': self._client_address,  # 委托单位地址
            'InspectedUnit': self._inspected_unit,  # 受检单位
            'Basis': self._basis,  # 检验依据
            'Criteria': self._criteria,  # 判定依据
            'Items': self._items,  # 检验项目
            'Instruments': self._instruments,  # 仪器设备
            'Conclusion': self._conclusion,  # 检测结论
            'ReportDate': self._report_date,  # 报告日期
            'Remark': self._remark,  # 备注
            'ReportQRCode': self._report_qrcode,  # 报告二维码
            'AccountQRCode': self._account_qrcode,  # 公众号二维码
            'OriginalReportDate': self._original_report_date,  # 原报告日期，仅更正报告需要传值
        }


class ReportEngineering(ReportMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'CMAMark': self._cma_mark,  # CMA标识
            'CNASMark': self._cnas_mark,  # CNAS标识
            'CNASText': self._cnas_text,  # CNAS说明
            'CoverFooter': self._cover_footer,  # 封面单位及中心信息
            'PageHeader': self._page_header,  # 正文单位及中心信息
            'SAMPLENAME': self._SAMPLE_NAME,
            'CLIENT': self._CLIENT,
            'CATEGORY': self._CATEGORY,
            'BusinessTel': self._business_tel,  # 业务电话
            'Fax': self._fax,  # 传真
            'Email': self._email,  # E-mail
            'ReportNo': self._report_no,  # 报告编号
            'ReportDate': self._report_date,  # 报告日期
            'ReportQRCode': self._report_qrcode,  # 报告二维码
            'AccountQRCode': self._account_qrcode,  # 公众号二维码
            'OriginalReportDate': self._original_report_date,  # 原报告日期，仅更正报告需要传值
        }


class ReportInspection(ReportMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'CMAMark': self._cma_mark,  # CMA标识
            'CNASMark': self._cnas_mark,  # CNAS标识
            'CNASText': self._cnas_text,  # CNAS说明
            'CoverFooter': self._cover_footer,  # 封面单位及中心信息
            'PageHeader': self._page_header,  # 正文单位及中心信息
            'SAMPLENAME': self._SAMPLE_NAME,
            'CLIENT': self._CLIENT,
            'CATEGORY': self._CATEGORY,
            'BusinessTel': self._business_tel,  # 业务电话
            'Fax': self._fax,  # 传真
            'Email': self._email,  # E-mail
            'ReportNo': self._report_no,  # 报告编号
            'ReportDate': self._report_date,  # 报告日期
            'ReportQRCode': self._report_qrcode,  # 报告二维码
            'AccountQRCode': self._account_qrcode,  # 公众号二维码
            'OriginalReportDate': self._original_report_date,  # 原报告日期，仅更正报告需要传值
        }


class ReportCalibration(ReportMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def _report_no(self):
        return self.plaintext('ReportNo', 20)

    @property
    def _SAMPLE_NAME(self):
        return self.plaintext('SampleName', 50)

    @property
    def _MODEL(self):  # noqa
        return self.plaintext('Model', 50)

    @property
    def _SERIAL(self):  # noqa
        return self.plaintext('Serial', 50)

    @property
    def _MANUFACTURER(self):
        return self.plaintext('Manufacturer', 50)

    @property
    def _CLIENT(self):
        return self.plaintext('Client', 50)

    @property
    def _CLIENT_ADDRESS(self):  # noqa
        return self.plaintext('ClientAddress', 50)

    @property
    def _PLACE(self):  # noqa
        return self.plaintext('Place', 240)

    @property
    def _BASIS(self):  # noqa
        return self.plaintext('Basis', 360)

    @property
    def _INSTRUMENTS(self):  # noqa
        line_width = 12  # depend on template
        max_lines = 22  # depend on template
        texts = self._content.get('Instruments', '').split('\t')
        result = []
        line_count = 0
        c = 6
        for i in range(len(texts) // c):
            row = {'nam': texts[i * c], 'rng': texts[i * c + 1], 'spc': texts[i * c + 2], 'crt': texts[i * c + 3],
                   'trc': texts[i * c + 4], 'exp': texts[i * c + 5]}
            result.append(row)
            line_count += max((self.cell_line_count(value, line_width) for value in row.values()), default=1)
        line_count += len(result)
        if line_count < max_lines:
            result.append(
                {'nam': '\n' * (max_lines - line_count - 2), 'rng': '', 'spc': '', 'crt': '', 'trc': '', 'exp': ''})
        return result

    @property
    def context(self):
        return {
            'CMAMark': self._cma_mark,  # CMA标识
            'CNASMark': self._cnas_mark,  # CNAS标识
            'CNASText': self._cnas_text,  # CNAS说明
            'CoverFooter': self._cover_footer,  # 封面单位及中心信息
            'PageHeader': self._page_header,  # 正文单位及中心信息
            'SAMPLENAME': self._SAMPLE_NAME,
            'MODEL': self._MODEL,
            'SERIAL': self._SERIAL,
            'MANUFACTURER': self._MANUFACTURER,
            'CLIENT': self._CLIENT,
            'CLIENTADDRESS': self._CLIENT_ADDRESS,
            'SubmissionDate': self._submission_date,
            'CalibrationDate': self._calibration_date,
            'ReportNo': self._report_no,  # 报告编号
            'ReportDate': self._report_date,  # 报告日期
            'ReportQRCode': self._report_qrcode,  # 报告二维码
            'Basis': self._BASIS,
            'Temperature': self._temperature,
            'Humidity': self._humidity,
            'Pressure': self._pressure,
            'PLACE': self._PLACE,
            'INSTRUMENTS': self._INSTRUMENTS,
            'OriginalReportDate': self._original_report_date,  # 原报告日期，仅更正报告需要传值
        }


class IssuanceRecordMaker(TemplateHelper):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def _RECORDS(self):  # noqa
        texts = self._content.get('IssuanceRecords', '').split('\t')
        result = []
        c = 5
        for i in range(len(texts) // c):
            row = {'no': texts[i * c], 'au': texts[i * c + 1], 'nam': texts[i * c + 2], 'cli': texts[i * c + 3],
                   'qty': texts[i * c + 4]}
            result.append(row)
        return result

    @property
    def context(self):
        raise NotImplementedError()


class IssuanceRecordProduct(IssuanceRecordMaker):
    def __init__(self, docx_path: str | Path, check_docx: bool = False, **kwargs):
        super().__init__(docx_path, check_docx, **kwargs)

    @property
    def context(self):
        return {
            'RECORDS': self._RECORDS,
        }


IssuanceRecordEngineering = IssuanceRecordProduct

__all__ = ['EntrustMaker', 'EntrustProduct', 'EntrustEngineering', 'ReportProduct', 'ReportSampling',
           'ReportEngineering', 'ReportInspection', 'ReportCalibration', 'IssuanceRecordProduct',
           'IssuanceRecordEngineering']
