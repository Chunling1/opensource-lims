import os
from typing import Literal
from pathlib import Path
from template_helper import IssuanceRecordProduct, IssuanceRecordEngineering

RecordCategory = Literal['Product', 'Engineering']


class RecordConfig:
    def __init__(self, category: RecordCategory) -> None:
        self._category = category.capitalize()

    @property
    def template(self) -> str | Path:
        version = 'Standard'
        category = 'a' if self._category == 'Product' else 'c'
        filepath = f"assets/templates/LAB-Record-4229{category}-{version}-202611_tpl.docx"
        if os.path.isfile(filepath):
            return filepath
        return ''

    @property
    def instance(self) -> object | None:
        if self._category == 'Product':
            return IssuanceRecordProduct
        elif self._category == 'Engineering':
            return IssuanceRecordEngineering
        return None


def make_record(context: dict, output: str | Path, category: RecordCategory) -> None:
    config = RecordConfig(category)
    tpl = config.template
    inst = config.instance
    if not tpl:
        raise RuntimeError('The template does not exist')
    if inst is None:
        raise RuntimeError('Unknow instance')
    record = inst(tpl, **context)
    out = record.render(record.context, output)
    print(out)


if __name__ == '__main__':
    raw_context = {
        'IssuanceRecords': 'LAB-2026JH-ZH-0000-1\t主检1号\t样品名称示例\t委托单位示例\t5\tLAB-2026ZX-0001\t主检1号\t样品名称示例\t委托单位示例\t5\tLAB-2026ZX-0001\t主检1号\t样品名称示例\t委托单位示例\t5',
        # 发放记录列表参数格式: ReportNo\tReportAuthor\tSampleName\tClient\tQuantity[\t...]
    }
    make_record(raw_context, 'output/record_product.docx', 'Product')
