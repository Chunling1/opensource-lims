"""报告签名状态和历史系统封面识别；报告封面由正式模板生成。"""

_STATUS_ORDER = ["待审核", "待批准", "待打印", "待发放", "已发放"]


def signature_state(report):
    """主检/审核/批准签名：优先用各步骤提交的用户电子签名（detail.signatures），否则按状态显示 已签/待签。"""
    s = report.status or ""
    idx = _STATUS_ORDER.index(s) if s in _STATUS_ORDER else 0
    sigs = (report.detail or {}).get("signatures") or {}

    def val(role, signed):
        return sigs.get(role) or ("已签" if signed else "待签")

    return {
        "主检": val("主检", True),
        "审核": val("审核", idx >= 2),   # 待批准及以后 = 审核已通过
        "批准": val("批准", idx >= 3),   # 待打印及以后 = 批准已通过
    }


def is_system_cover_attachment(attachment):
    """Use provenance as well as name: never exclude a person's same-name upload."""
    return (
        attachment.source == "模板生成"
        and str(attachment.name or "").lower() in {"系统生成封面.docx", "系统生成封面.pdf"}
    )


def _field(detail, section_title, key, default=""):
    for sec in (detail or {}).get("summary", []):
        if sec.get("title") == section_title:
            for k, v in sec.get("fields", []):
                if k == key:
                    return v
    return default
