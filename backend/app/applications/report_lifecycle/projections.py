"""Pure read projections for report lifecycle delivery adapters."""

from __future__ import annotations


_STANDARD_SAMPLE_FIELDS = [
    "样品编号",
    "样品名称",
    "样品/工程名称",
    "规格型号",
    "代表批量",
    "生产厂家",
    "检测部门",
    "检测室",
    "是否加急",
    "检测期限",
    "外观",
    "铭牌",
    "检测地点",
    "样品数量",
    "出厂编号",
    "生产日期",
    "送样日期",
    "单位",
    "检测类型",
    "报告类型",
    "检测类别",
    "流转状态",
]

_EXTRA_SECTIONS = [
    ("项目信息", ["委托单备注", "报告首页备注", "备注（内部）"]),
    ("抽样信息", ["抽样单位", "抽样人", "抽样时间", "抽样数量", "基数", "受检单位", "任务来源"]),
    ("结算信息", ["标准价格", "缴费情况", "支付方式", "已缴费", "其他"]),
    (
        "报告发送",
        [
            "报告寄送(对外)",
            "报告寄送(内部)",
            "样品处理方式",
            "报告交付方式",
            "邮寄地址",
            "报告交付标准",
            "报告形式",
            "现场检测时间约定",
            "内业标准日期",
        ],
    ),
]

_SUMMARY_ORDER = [
    "委托信息",
    "送样信息",
    "样品信息",
    "项目信息",
    "抽样信息",
    "结算信息",
    "报告发送",
    "实验信息",
    "原始记录",
]


def augment_report_summary(summary):
    """Return a stable complete read projection without mutating source data."""

    by_title, result = {}, []
    for section in summary:
        projected = {
            "title": section.get("title"),
            "fields": list(section.get("fields", [])),
        }
        result.append(projected)
        by_title[projected["title"]] = projected
    sample = by_title.get("送样信息") or by_title.get("样品信息")
    if sample:
        sample["title"] = "送样信息"
        existing = {key for key, _value in sample["fields"]}
        for field_name in _STANDARD_SAMPLE_FIELDS:
            if field_name not in existing:
                sample["fields"].append([field_name, "—"])
    for title, fields in _EXTRA_SECTIONS:
        if title not in by_title:
            result.append({"title": title, "fields": [[field, "—"] for field in fields]})
    result.sort(
        key=lambda section: _SUMMARY_ORDER.index(section["title"])
        if section["title"] in _SUMMARY_ORDER
        else 99
    )
    return result


__all__ = ["augment_report_summary"]
