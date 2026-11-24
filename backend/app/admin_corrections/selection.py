"""Business forms validation for admin corrections (contract-free OSS edition)."""
from ..models import Entrust, Report


def validate(row, before, patch):
    if isinstance(row, Report) and (row.main_report_no or (row.detail or {}).get("derivedFrom")):
        from copy import deepcopy
        from ..derived_registration import lock_source_scheme
        if "department" in patch and patch["department"] != row.department:
            raise ValueError("派生报告的检测部门不能更改")
        if "detail" in patch:
            candidate = deepcopy(patch["detail"])
            error = lock_source_scheme(row, candidate)
            if error:
                raise ValueError(error)
            patch["detail"] = candidate
    if not isinstance(row, (Entrust, Report)):
        return
    if isinstance(row, Report) and "detail" in patch:
        from ..sample_pricing import contract_completion_error, price_error, standard_price
        previous = before.get("detail") or {}
        candidate = patch["detail"]
        old_items = (previous.get("rawSample") or {}).get("subItems")
        new_items = (candidate.get("rawSample") or {}).get("subItems")
        if standard_price(candidate) != standard_price(previous) or new_items != old_items:
            complete = patch.get("sample_reg_state", row.sample_reg_state) != "登记中"
            parent = Entrust.query.filter_by(entrust_no=row.entrust_no).first() if row.entrust_no else None
            error = contract_completion_error(candidate, parent) if complete else price_error(candidate, report=row)
            if error:
                raise ValueError(error)
