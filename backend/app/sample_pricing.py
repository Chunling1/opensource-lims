"""Sample-local money validation; contract totals do not limit sample prices."""
import re
from decimal import Decimal


def money(value, label, *, signed=False):
    text = str(value if value is not None else '').strip()
    pattern = r'-?\d{1,12}(?:\.\d{1,2})?' if signed else r'\d{1,12}(?:\.\d{1,2})?'
    if not re.fullmatch(pattern, text, flags=re.ASCII):
        raise ValueError(f'{label}须填写有效金额（最多12位整数、2位小数' + ('）' if signed else '，不能为负数）'))
    return Decimal(text)


def standard_price(detail):
    raw = (detail or {}).get('rawSample')
    if isinstance(raw, dict) and 'stdPrice' in raw:
        return raw['stdPrice']
    # Historical forms stored this field only in the printable summary.
    for section in (detail or {}).get('summary', []):
        if section.get('title') == '结算信息':
            for label, value in section.get('fields', []):
                if label == '标准价格':
                    return value
    return None


def payment_description_error(detail):
    """Every supplied subproject needs payment terms, including draft saves."""
    raw = (detail or {}).get('rawSample')
    rows = raw.get('subItems') if isinstance(raw, dict) else None
    if isinstance(rows, list):
        for index, row in enumerate(rows, 1):
            if isinstance(row, dict) and not str(row.get('paymentDescription') or '').strip():
                return f'请填写子项目第{index}行付款说明'
    return None


def completion_error(detail, *, allow_empty=False):
    raw = (detail or {}).get('rawSample')
    rows = raw.get('subItems') if isinstance(raw, dict) else None
    if allow_empty and (rows is None or rows == []):
        try:
            money(standard_price(detail), '标准价格')
        except ValueError as exc:
            return str(exc)
        return None
    if not isinstance(rows, list) or not rows:
        return '完成登记前请填写至少一个子项目'
    if len(rows) > 100:
        return '样品子项目不能超过100项'
    payment_error = payment_description_error(detail)
    if payment_error:
        return payment_error
    try:
        price = money(standard_price(detail), '标准价格')
        total = Decimal(0)
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                return f'子项目第{index}行格式无效'
            for key, label in (('projectName', '子项目名称'), ('dept', '核算部门'),
                               ('businessCategory', '业务三级分类')):
                if str(row.get(key) or '').strip() in ('', '—', '-'):
                    return f'请填写子项目第{index}行{label}'
            # Existing reward/penalty allocations can be signed; the sample
            # standard price itself must remain nonnegative.
            total += money(row.get('amount'), f'子项目第{index}行子项金额', signed=True)
            money(row.get('receivedAmount'), f'子项目第{index}行收款金额', signed=True)
        if total != price:
            return f'子项目金额合计 {total:.2f} 元必须等于标准价格 {price:.2f} 元（差额 {price - total:.2f} 元）'
    except ValueError as exc:
        return str(exc)
    return None


def price_error(detail, *, report=None, derived=False):
    """Validate saved settlement rows; incomplete drafts may leave price blank.

    Contract amounts can be undetermined. Do not read, aggregate or lock the
    contract or sibling samples as part of this sample-local validation.
    Completion separately requires exact equality with the subproject sum.
    """
    if derived or (report and ((report.report_kind or 'main') != 'main' or report.main_report_no)):
        return None
    # Save paths permit an unfinished price, but never blank payment terms
    # on an existing subproject row.
    payment_error = payment_description_error(detail)
    if payment_error:
        return payment_error
    raw = (detail or {}).get('rawSample')
    rows = raw.get('subItems') if isinstance(raw, dict) else None
    try:
        for index, row in enumerate(rows or [], 1):
            if not isinstance(row, dict):
                return f'子项目第{index}行格式无效'
            money(row.get('amount'), f'子项目第{index}行子项金额', signed=True)
            money(row.get('receivedAmount'), f'子项目第{index}行收款金额', signed=True)
    except ValueError as exc:
        return str(exc)
    value = standard_price(detail)
    if value is None or str(value).strip() in ('', '—', '-'):
        return None
    try:
        money(value, '标准价格')
    except ValueError as exc:
        return str(exc)
    return None


def contract_completion_error(detail, entrust=None):
    """Validate sample pricing upon completion (no contract exemption in OSS edition)."""
    return completion_error(detail, allow_empty=False)
