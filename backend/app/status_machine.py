"""R6 全流程数据状态机（2026-07-09 批次）。

设计（实施计划 P-2 路线 A）：底层沿用既有状态枚举（reports.status / sample_status、
entrusts.status、agreements.status），本模块把它们**派生**为 R6 术语的「数据状态」
（环节 + 中/完成），供列表列与表单徽章统一展示；同时集中定义各环节
完成/撤销动作的下游拦截规则（Q8 默认：禁止撤销已流转，提示先处理下游）。

映射为纯函数：不写库、无副作用，SQLite/达梦通用。
"""

# 报告主状态 → (环节, 中/完成 说明见各行注释)
_REPORT_STAGE = {
    "待合同评审": "合同评审中",      # 样品登记完成后进入评审待办（登记中的样品由 sample_reg_state 覆盖）
    "待样品入库": "样品入库中",
    "待样品领取": "样品出库领取中",
    "检测录入中": "检测数据录入中",
    "委托更改中": "委托更改中",
    "检测更改中": "检测更改中",
    "退回待重传": "检测数据录入中",  # 被退回重录
    "待审核": "报告审核中",          # 检测录入完成后直接进入
    "待批准": "报告批准中",
    "待打印": "报告签发中",
}


def detection_data_started(detail):
    """检测数据是否至少由录入模块实际保存过一次。

    新流程使用显式标记，避免样品复制或历史初始化产生的 ``checkInput``
    被误判为已经开始录入；没有显式标记的历史数据仍按 ``checkInput`` 兼容。
    """
    detail = detail or {}
    marker = detail.get("dataEntryStarted")
    if marker is not None:
        return bool(marker)
    return bool(detail.get("checkInput"))


def report_data_status(status, sample_status, sample_reg_state="", archive_state="", voided=False,
                       data_entry_started=None, issuance_label=None, released=False):
    """报告（样品单）的数据状态标签。"""
    status = status or ""
    sample_status = sample_status or "待入库"
    if voided or (sample_reg_state or "") == "已作废":
        return "样品单已作废"
    if status == "待合同评审" and (sample_reg_state or "登记完成") == "登记中":
        return "样品登记中"
    if status == "检测录入中" and sample_status == "已领取" and data_entry_started is False:
        return "样品出库领取完成"
    if status == "待校核":
        # 兼容取消“报告校核”前的遗留数据；数据库迁移会统一转为待审核。
        if sample_status == "待入库":
            return "样品入库中（历史数据）"
        if sample_status == "已入库":
            return "样品出库领取中（历史数据）"
        return "报告审核中"
    if status in {"待发放", "已发放"}:
        from .report_delivery import SEALED, ARCHIVED, RELEASED
        if released:
            return RELEASED
        return ARCHIVED if archive_state == "归档完成" else SEALED
    if status == "待打印" and issuance_label:
        return issuance_label
    return _REPORT_STAGE.get(status, status)


def entrust_data_status(status):
    return {"委托中": "委托登记中", "委托完成": "委托登记完成"}.get(status or "", status or "")


def agreement_data_status(status):
    return {"合同登记中": "合同登记中", "已登记": "合同登记完成"}.get(status or "", status or "合同登记中")


# ---- 撤销/流转的下游拦截（Q8 默认：禁止撤销已流转） ----

def entrust_can_add_sample(entrust):
    """R6-AC2：委托登记完成后才可流转样品登记。entrust 为 None（历史孤儿）放行。"""
    if entrust is None:
        return None
    if entrust.status != "委托完成":
        return f"委托单 {entrust.entrust_no} 尚未完成登记，请先在委托登记点「完成」"
    return None


def agreement_undo_blocker(agreement, entrust_query):
    """撤销合同登记完成：存在关联委托即拦截。"""
    n = entrust_query.filter_by(contract_no=agreement.agreement_no).count()
    if n:
        return f"该合同下已登记 {n} 张委托单，请先处理下游委托后再撤销登记"
    return None


def entrust_undo_blocker(entrust, report_query):
    """撤销委托登记完成：该委托下已有样品单（未作废）即拦截。"""
    n = report_query.filter_by(entrust_no=entrust.entrust_no).count()
    if n:
        return f"该委托下已登记 {n} 张样品单，请先作废/更改样品单后再撤销完成"
    return None


def review_undo_blocker(report):
    """撤销合同评审：评审通过后一旦样品入库/流转即拦截（默认实施计划歧义 #5）。"""
    if report.status != "待样品入库":
        return f"报告已流转至「{report_data_status(report.status, report.sample_status)}」，不可撤销合同评审"
    if (report.sample_status or "待入库") != "待入库":
        return f"样品为「{report.sample_status}」，请先处理样品库存后再撤销合同评审"
    return None


def release_undo_blocker(report):
    """撤销发放完成：已归档拦截；样品已处置拦截。"""
    if (getattr(report, "archive_state", "") or "") == "归档完成":
        return "报告已归档，请先撤销归档"
    if (report.sample_status or "") == "已处置":
        return "样品已处置，无法撤销发放"
    return None


def sample_inbound_undo_blocker(report):
    if bool(report.voided) or (report.sample_reg_state or "") == "已作废":
        return "样品单已作废，不能撤销入库"
    if report.status != "待样品领取" or report.sample_status != "已入库":
        return "仅已入库、等待领取的样品可以撤销入库"
    return None


def sample_return_stock_blocker(report, data_entry_started=None):
    """样品回库（出库并领取 → 未开始检测录入回库）。"""
    if (report.sample_status or "") != "已领取":
        return f"样品当前为「{report.sample_status}」，仅「已领取」可回库"
    if report.status != "检测录入中":
        return "检测数据已提交，不能回库；检测完成后请走「样品处置」"
    if data_entry_started is None:
        from .data_entry_state import report_data_entry_started
        data_entry_started = report_data_entry_started(report)
    if data_entry_started:
        return "已保存检测数据，不能撤回入库；如需修改请走检测数据更改流程"
    return None


def sample_dispose_blocker(report):
    """样品处置：检测完成（已直接进入审核及以后）方可处置。"""
    if (report.sample_status or "") not in ("已领取", "已出库"):
        return f"样品当前为「{report.sample_status}」，不可处置"
    if report.status in (
        "待合同评审", "待样品入库", "待样品领取", "检测录入中",
        "退回待重传", "委托更改中", "检测更改中",
    ):
        return "检测尚未完成，不能处置；未完成检测请走「样品回库」"
    return None
