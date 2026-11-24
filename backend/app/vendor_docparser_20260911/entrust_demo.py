import os
from typing import Literal
from pathlib import Path
from template_helper import EntrustProduct, EntrustEngineering

EntrustCategory = Literal['Product', 'Engineering']


class EntrustConfig:
    def __init__(self, category: EntrustCategory, extended: bool = False) -> None:
        self._category = category.capitalize()
        self._extended = extended

    @property
    def template(self) -> str | Path:
        version = 'Extended' if self._extended else 'Standard'
        category = 'd' if self._category == 'Product' else 'g'
        filepath = f"assets/templates/LAB-Entrust-4204{category}-{version}-202601_tpl.docx"
        if os.path.isfile(filepath):
            return filepath
        return ''

    @property
    def instance(self) -> object | None:
        if self._category == 'Product':
            return EntrustProduct
        elif self._category == 'Engineering':
            return EntrustEngineering
        return None


def make_entrust(context: dict, output: str | Path, category: EntrustCategory, extended=False) -> None:
    config = EntrustConfig(category, extended)
    tpl = config.template
    inst = config.instance
    if not tpl:
        raise RuntimeError('The template does not exist')
    if inst is None:
        raise RuntimeError('Unknow instance')
    entrust = inst(tpl, **context)
    out = entrust.render(entrust.context, output)
    print(out)


if __name__ == '__main__':
    raw_context = {
        'Center': '（国家空调设备质量检验检测中心）',  # 国家中心
        'SampleNo': '2026XX-XX-0001',  # 样品编号
        'EntrustDate': '2026年10月01日',  # 委托日期
        'Client': '委托单位',  # 委托单位
        'SampleName': '样品名称',  # 样品名称
        'Model': '规格型号',  # 规格型号
        'Manufacturer': '生产单位',  # 生产单位
        'ManufacturingDate': '2026年10月01日',  # 生产日期
        'Serial': 'SN1234567890',  # 产品编号
        'SubmissionDate': '2026年10月01日',  # 送样日期
        'Category': '委托',  # 检验类别
        'Quantity': '100套',  # 样品数量
        'Trademark': 'assets/images/signature-example.png',  # 商标
        'Basis': 'GB 6566-2010 建筑材料放射性核素限量；GB/T 10295-2008 绝热材料稳态热阻及有关特性的测定 热流计法:GB/T30804-201用绝热制品 垂直于表面抗拉强度的测定:GBT32382-2015建筑用绝热制品 剪切性能的测定:GBT8810-2005硬质泡沫塑料吸水率的测定:GBT8811-2008硬质泡沫塑料 尺寸稳定性试验方法:GBT8812.2-2007 硬质泡沫塑料 弯曲性能的测定 第2部分:弯曲强和表观弯曲弹性模量的测定;GB/T8813-2020硬质泡沫塑料 压缩性能的测定;JGT480-2015 外墙保温复合板通用技术要求;Q',
        # 检验依据
        'Criteria': '《判断依据》GB 12345-2000',  # 判定依据
        'Items': '检验项目1，检验项目2',  # 检验项目
        'TECHNIQUE': True,  # 技术能力
        'INSTRUMENT': False,  # 仪器设备
        'ENVIRONMENT': True,  # 环境设施条件
        'METHOD': False,  # 方法
        'PERSON': False,  # 人员
        'SAMPLE': False,  # 样品
        'SCOPE': False,  # 检验依据授权
        'CMA': False,  # 加盖CMA章
        'CNAS': True,  # 加盖CNAS章
        'Signature': 'assets/images/signature-example.png',  # 签字
        'Appearance': '正常',  # 外观
        'Nameplate': '有',  # 铭牌
        'SampleHandling': '委托中心寄回',  # 检验后样品处理要求
        'PICKUP': True,  # 提交报告方式
        'ReportQuantity': 5,  # 报告份数
        'ReportDate': '2026年10月01日',  # 报告时间
        'Amount': 15000,  # 检验费用
        'Payment': '委托时缴纳',  # 交费情况
        'Remark': '备注',  # 备注
        'Consignor': '委托人',  # 委托人
        'ConsignorPhone': '1234567890',  # 委托人电话
        'ClientAddress': '委托单位地址',  # 委托单位地址
        'PartyA': '合同甲方',  # 合同甲方
        'Payer': '其他甲方（付款方）',  # 其他甲方（付款方）
        'Handler': '经手人',  # 经手人
        'Phone': '13812345678',  # 电话
        'Department': '实验室名称',  # 试验室名称
    }
    make_entrust(raw_context, 'output/entrust_sample.docx', 'Product', True)
