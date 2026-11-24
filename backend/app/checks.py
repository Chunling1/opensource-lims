"""报告系统校验：依据三个库动态计算（标准/一单一库、受控仪器库、CNAS 资质库）。

- 标准与一单一库：报告依据标准必须在标准库内（且现行），否则"不在库内"，不可盖 CMA。
- 仪器有效性：仪器须在受控仪器库内，且检测日期在校准/检定有效期内。
- 盖章范围(CNAS)：CMA 校验一单一库及 CMA 授权，CNAS 仅校验 CNAS 授权，库外参数仅展示，不影响范围判定。

校验输入取自 report.detail['checkInput'] = {standard, instrument, testDate, seal, project}。
无 checkInput 的旧报告沿用其静态 checks。
"""
from datetime import date, datetime

from .models import EquipmentItem, Instrument, Qualification
from .standard_control import find_controlled_standard


def _parse(s):
    try:
        return datetime.strptime((s or "").strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _mk(group, status, ctype, items):
    return {"group": group, "status": status, "type": ctype, "items": items}


def compute_report_checks(report):
    """返回 (checks, out_of_scope, note)。out_of_scope=True 表示有红色不通过项（超范围）。"""
    detail = report.detail or {}
    ci = detail.get("checkInput")
    if not ci:
        static = detail.get("checks", [])
        if static:
            return static, bool(report.__dict__.get("out_of_scope")), report.__dict__.get("out_of_scope_note") or ""
        # 检测信息尚未录入：给出待录入提示
        return [_mk("检测信息校验", "待录入", "info", [
            ["提示", "检测人员尚未录入检测信息（标准/仪器/检测日期）"],
            ["说明", "录入后自动进行 标准/一单一库、仪器有效性、CNAS 三库校验"],
        ])], False, ""

    standard = (ci.get("standard") or "").strip()
    instrument = (ci.get("instrument") or "").strip()
    from .report_scope import scope_projection
    scope = scope_projection(report)
    seal = scope["seal"]
    project = ci.get("project") or report.project or ""
    when = _parse(ci.get("testDate")) or date.today()
    dangers = []

    # Authorization is checked per standard; parameters only indicate library membership.
    label = {'in_scope': '通过', 'out_of_scope': '超范围', 'needs_review': '待核实'}[scope['state']]
    kind = {'in_scope': 'success', 'out_of_scope': 'danger', 'needs_review': 'warning'}[scope['state']]
    items = [[row['standard'], '；'.join(row['reasons']) or (('一单一库；' if row['singleList'] else '') + ('授权：' + '/'.join(row['marks']) if row['marks'] else '受控标准'))] for row in scope['standardRows']]
    items.extend([row['item'], '库内参数'] for row in scope['rows'])
    if scope['note']:
        items.append(['判定依据', scope['note']])
    if scope['reviewApplied']:
        items.append(['人工复核', scope['review'].get('reason', '')])
    c1 = _mk('项目能力范围校验', label, kind, items)

    # 2) 仪器有效性（优先使用新版设备台账快照；兼容历史 Instrument 数据）
    equipment_ids = ci.get("equipmentIds") or []
    equipment_snapshots = ci.get("equipmentSnapshots") or []
    equipment_rows = (
        EquipmentItem.query.filter(
            EquipmentItem.id.in_(equipment_ids),
            EquipmentItem.deleted_at.is_(None),
        ).all()
        if equipment_ids else []
    )
    if equipment_rows:
        intervals = ci.get("testIntervals") or [{
            "start": ci.get("testStartDate") or when.isoformat(),
            "end": ci.get("testDate") or when.isoformat(),
        }]
        bounds = [(_parse(part.get("start")), _parse(part.get("end")))
                  if isinstance(part, dict) else (None, None) for part in intervals]
        missing_ids = set(map(str, equipment_ids)) - {str(e.id) for e in equipment_rows}
        invalid = [f'设备ID {value}（不存在或已停用）' for value in sorted(missing_ids)]
        items = []
        for equipment in equipment_rows:
            valid_from = _parse(equipment.actual_cal_date or equipment.last_cal_date)
            valid_until = _parse(equipment.valid_until or equipment.plan_cal_date)
            status = equipment.effective_status()
            long_term = equipment.is_long_term()
            reason = next((error for start, end in bounds
                           if (error := equipment.test_interval_error(start, end))), "")
            window = "长期有效" if long_term else (
                f"{valid_from.isoformat() if valid_from else '未记录'} 至 "
                f"{valid_until.isoformat() if valid_until else '未记录'}"
            )
            items.append([equipment.name or equipment.archive_no,
                          f"当前状态 {status}，有效期 {window}；" + (reason or "覆盖全部试验区间")])
            if reason:
                invalid.append(f"{equipment.archive_no} {equipment.name}（{reason}）")
        if invalid:
            c2 = _mk("仪器有效性校验", "不通过", "danger", items + [
                ["阻断原因", "以下设备未覆盖检测日期：" + "、".join(invalid)],
            ])
            dangers.append("仪器在检测日期不在校准/检定有效期内：" + "、".join(invalid))
        else:
            c2 = _mk("仪器有效性校验", "通过", "success", items)
    elif equipment_ids or equipment_snapshots:
        c2 = _mk("仪器有效性校验", "不在库内", "danger", [
            ["仪器名称", instrument or "未填写"],
            ["受控状态", "所选设备已不在有效设备台账内"],
            ["处理建议", "重新选择设备台账中的有效仪器"],
        ])
        dangers.append("所选仪器已不在有效设备台账内")
    else:
        ins = None
        if instrument:
            # Legacy text is not an identity. Never choose a fuzzy or ambiguous match.
            matches = Instrument.query.filter_by(name=instrument).all()
            if not matches:
                matches = Instrument.query.filter_by(code=instrument).all()
            if len(matches) == 1:
                ins = matches[0]
        if not ins:
            c2 = _mk("仪器有效性校验", "不在库内", "danger", [
                ["仪器名称", instrument or "未填写"],
                ["受控状态", "不在受控仪器库内"],
                ["处理建议", "先将仪器纳入受控仪器库"],
            ])
            dangers.append("仪器不在受控仪器库内")
        else:
            v = ins.valid_at(when)
            if v:
                c2 = _mk("仪器有效性校验", "通过", "success", [
                    ["仪器名称", ins.name],
                    ["受控状态", "在受控仪器清单内"],
                    ["有效期", f"{v.valid_from.isoformat()} 至 {v.valid_to.isoformat()}，检测日期有效"],
                ])
            else:
                latest = max((x for x in ins.validities), key=lambda x: x.valid_to, default=None)
                window = f"截至 {latest.valid_to.isoformat()}" if latest else "无有效记录"
                c2 = _mk("仪器有效性校验", "不通过", "danger", [
                    ["仪器名称", ins.name],
                    ["受控状态", "在受控仪器清单内"],
                    ["有效期", f"检测日期 {when.isoformat()} 不在校准/检定有效期内（{window}）"],
                ])
                dangers.append("仪器在检测日期不在校准/检定有效期内")

    # Scope classification does not confer a seal or bypass equipment/compliance approval.
    c3 = _mk('标识覆盖说明', '按标准校验', 'info', [
        ['委托标识要求', seal or '未指定'],
        ['说明', 'CMA 校验所选标准的一单一库范围及 CMA 授权；CNAS 校验对应授权，不要求一单一库；库外参数仅展示，不影响范围判定'],
    ])
    return [c1, c2, c3], scope['outOfScope'], (scope['note'] if scope['outOfScope'] else '')
