"""Configurable multi-stage review and approval workflow per project."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_stages(raw: Any, default_label: str, default_role: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"{default_label}第{idx + 1}级").strip()
        role_key = str(item.get("roleKey") or default_role).strip()
        accounts = [str(a).strip() for a in (item.get("userAccounts") or []) if str(a).strip()]
        result.append({
            "index": idx,
            "name": name,
            "roleKey": role_key,
            "userAccounts": accounts,
        })
    return result


def configured_stages(project, kind: str) -> list[dict[str, Any]]:
    config = project.workflow_config if project and isinstance(project.workflow_config, dict) else {}
    if kind == "review":
        return normalize_stages(config.get("reviewStages"), "审核", "reviewer")
    if kind == "approval":
        return normalize_stages(config.get("approvalStages"), "批准", "approver")
    return []


def advance_stage_or_complete(report, user, kind: str, project, note: str = "") -> tuple[bool, str, str | None]:
    """Advance multi-stage review/approval if >1 stage is configured.

    Returns (completed_all_stages, status_message, error_message).
    """
    stages = configured_stages(project, kind)
    if len(stages) <= 1:
        return True, "", None

    detail = dict(report.detail or {})
    state = dict(detail.get("multiStageApproval") or {})
    idx_key = f"{kind}Index"
    hist_key = f"{kind}History"
    current_idx = int(state.get(idx_key) or 0)
    if current_idx >= len(stages):
        current_idx = len(stages) - 1

    stage = stages[current_idx]
    allowed_accounts = stage.get("userAccounts") or []
    if allowed_accounts and user.account not in allowed_accounts and user.role_key != "admin":
        return False, "", f"当前节点「{stage['name']}」仅限指定人员（{', '.join(allowed_accounts)}）办理"

    history = list(state.get(hist_key) or [])
    history.append({
        "stageIndex": current_idx,
        "stageName": stage["name"],
        "operatorAccount": user.account,
        "operatorName": user.name,
        "actedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
    })
    state[hist_key] = history

    if current_idx + 1 < len(stages):
        next_stage = stages[current_idx + 1]
        state[idx_key] = current_idx + 1
        state[f"{kind}CurrentName"] = next_stage["name"]
        state[f"{kind}Total"] = len(stages)
        detail["multiStageApproval"] = state
        report.detail = detail
        return False, f"{report.report_no} 已通过「{stage['name']}」（{current_idx + 1}/{len(stages)}），进入下一级「{next_stage['name']}」", None

    state[idx_key] = len(stages)
    state[f"{kind}CurrentName"] = ""
    state[f"{kind}Total"] = len(stages)
    detail["multiStageApproval"] = state
    report.detail = detail
    return True, "", None


def reset_multi_stage_on_return(report) -> None:
    detail = dict(report.detail or {})
    state = dict(detail.get("multiStageApproval") or {})
    if not state:
        return
    state["reviewIndex"] = 0
    state["approvalIndex"] = 0
    state["reviewCurrentName"] = ""
    state["approvalCurrentName"] = ""
    detail["multiStageApproval"] = state
    report.detail = detail
