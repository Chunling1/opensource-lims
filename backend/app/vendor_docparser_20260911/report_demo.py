import os
from typing import Literal
from pathlib import Path
from template_helper import ReportProduct, ReportSampling, ReportEngineering, ReportInspection, ReportCalibration

ReportCenter = Literal['LAB', 'NCSA']
ReportCategory = Literal['Product', 'Sampling', 'Engineering', 'Inspection', 'Calibration']
ReportLanguage = Literal['CN', 'EN']


class ReportConfig:
    report_context = {
        'LAB': {
            'context': {
                'CMAText': '',  # CMA证书编号，留空则不显示
                'CNASText': '中国认可\n国际互认\n检测\nTESTING\nCNAS L1045',  # CNAS证书信息，留空则不显示
                # 封面底部
                'CoverFooter': '示  例  检  测  科  技  有  限  公  司\nExample Testing Lab Co., Ltd.',
                # 首页页眉
                'PageHeader': '\n\n示例检测机构\nExample Testing Lab Co., Ltd.',
                'BusinessTel': '400-000-0001  400-000-0002',  # 业务电话
                'Fax': '400-000-0001',  # 传真
                'Email': 'lab@example.com  lab@example.com',  # E-mail
            },
            'category': {
                'Product': {},
                'Sampling': {},
                'Engineering': {},
                'Inspection': {'CNASText': '中国认可\n国际互认\n检验\nINSPECTION\nCNAS IB0222'},
                'Calibration': {'CNASText': '中国认可\n国际互认\n校准\nCALIBRATION\nCNAS L1045'},
            }
        },
        'NCSA': {
            'context': {
                'CMAText': '220020344460',  # CMA证书编号，留空则不显示
                'CNASText': '中国认可\n国际互认\n检测\nTESTING\nCNAS L1045',  # CNAS证书信息，留空则不显示
                # 封面底部
                'CoverFooter': '示  例  检  测  科  技  有  限  公  司\nExample Testing Lab Co., Ltd.\n（国家空调设备质量检验检测中心）\n(National Center of Quality Inspection and Testing for Air Conditioning Equipment)',
                # 首页页眉
                'PageHeader': '示例检测机构\nExample Testing Lab Co., Ltd.\n国家空调设备质量检验检测中心\nNational Center of Quality Inspection and Testing for Air Conditioning Equipment',
                'BusinessTel': '400-000-0001  400-000-0002',  # 业务电话
                'Fax': '400-000-0001',  # 传真
                'Email': 'lab@example.com  lab@example.com',  # E-mail
            },
            'category': {
                'Product': {},
                'Sampling': {},
                'Engineering': {},
            }
        },
    }

    def __init__(self, center: ReportCenter, category: ReportCategory, language: ReportLanguage = 'CN',
                 extended: bool = False) -> None:
        self._center = center.upper()
        self._category = category.capitalize()
        self._language = language.upper()
        self._extended = extended

    @property
    def context(self) -> dict | None:
        context = self.report_context.get(self._center, {}).get('context', {})
        category_context = self.report_context.get(self._center, {}).get('category', {}).get(self._category, None)
        if category_context is None:
            return None
        context.update(category_context)
        return context

    @property
    def template(self) -> str | Path:
        version = 'Extended' if self._extended else 'Standard'
        filepath = f"assets/templates/LAB-Report-{self._category}-{self._language}-{version}-202609_tpl.docx"
        if os.path.isfile(filepath):
            return filepath
        return ''

    @property
    def instance(self) -> object | None:
        if self._category == 'Product':
            return ReportProduct
        elif self._category == 'Sampling':
            return ReportSampling
        elif self._category == 'Engineering':
            return ReportEngineering
        elif self._category == 'Inspection':
            return ReportInspection
        elif self._category == 'Calibration':
            return ReportCalibration
        return None


def make_report(context: dict, output: str | Path, center: ReportCenter, category: ReportCategory,
                language: ReportLanguage = 'CN', extended=False) -> None:
    config = ReportConfig(center, category, language, extended)
    ctx = config.context
    if ctx is None:
        raise RuntimeError('Unknow context')
    ctx.update(context)
    tpl = config.template
    inst = config.instance
    if not tpl:
        raise RuntimeError('The template does not exist')
    if inst is None:
        raise RuntimeError('Unknow instance')
    report = inst(tpl, **ctx)
    out = report.render(report.context, output)
    print(out)


if __name__ == '__main__':
    raw_context = {
        # 中心参数（请不要打开注释，否则将覆盖默认配置）
        # 'CMAText': '',  # CMA证书编号，留空则不显示
        # 'CNASText': '',  # CNAS证书信息，留空则不显示
        # 'CoverFooter': '',  # 封面底部
        # 'PageHeader': '',  # 首页页眉
        # 'BusinessTel': '',  # 业务电话
        # 'Fax': '',  # 传真
        # 'Email': '',  # E-mail
        # 报告参数
        'ReportNo': '2026XX-XX-0001',  # 报告编号
        'SampleName': '产品名称',  # 样品名称
        'Client': '委托单位',  # 委托单位
        'Manufacturer': '生产单位',  # 生产单位
        'Trademark': 'assets/images/signature-example.png',  # 商标
        'Model': '规格型号',  # 规格型号
        'Serial': 'SN1234567890',  # 出厂编号
        'Place': '检测地点',  # 检测地点
        'EngineeringName': '/',  # 工程名称
        'SampleNo': '样品编号',  # 样品编号
        'Category': '委托',  # 检验类别
        'Quantity': '100套',  # 样品数量
        'SampleCondition': '样品状态',
        'ManufacturingDate': '2026年10月01日',  # 生产日期
        'EntrustDate': '2026年10月01日',  # 委托日期
        'SubmissionDate': '2026年10月01日',  # 送样日期
        'TestDate': '2026年10月01日',  # 检测日期
        'ClientAddress': '委托单位地址',  # 委托单位地址
        'Basis': '《检测依据》GB 12345-2000',  # 检验依据
        'Criteria': '《判定依据》GB 12345-2000',  # 判定依据
        'Items': '检测项目1，检测项目2',  # 检验项目
        'Instruments': '仪器设备',
        # 仪器设备，校准设备列表参数格式: Name\tRange\tUncertainty\tCertificate\tTraceability\tExpiry[\t...]
        'Conclusion': '检测结论',  # 检测结论文本，或检测结论docx文件路径
        'ReportDate': '',  # 报告日期/签发日期，更正报告日期，应留空
        'Remark': '备注',  # 备注
        'ReportQRCode': 'http://lab.example.com/',  # 报告二维码
        'AccountQRCode': 'https://lab.example.com/wechat-demo',  # 公众号二维码
        'OriginalReportDate': '',  # 原报告日期，仅对更正报告有效，默认留空
        # 补充抽样参数
        'SampleArrivalDate': '2026年10月01日',  # 样品到达日期
        'SamplingUnit': '示例检测机构',  # 抽样单位
        'SamplingDate': '2026年10月01日',  # 抽样日期
        'Sampler': '抽样人',  # 抽样人
        'SamplingQuantity': '20',  # 抽样数量
        'SamplingPlace': '抽样地点',  # 抽样地点
        'SamplingBase': '2000',  # 抽样基数
        'SealingInspector': '封样人',  # 检查封样人员
        'SealingCondition': '正常',  # 封样状态
        'TaskSource': '任务来源',  # 任务来源
        'SampleGrade': '1级',  # 样品等级
        'InspectedUnit': '受检单位',  # 受检单位
        # 校准参数
        'CalibrationDate': '2026年10月01日',
        'Temperature': '20.56℃',
        'Humidity': '65.34%',
        'Pressure': '103.125 kPa',
    }
    make_report(raw_context, 'output/report_sample.docx', 'LAB', 'Engineering', 'CN', extended=False)
