type StatusRow = { dataStatus?: string; status?: string }

// Business labels from backend status_machine/report_delivery, not action states.
// Available filters must not depend on whether this account currently has a row.
export const reportDataStates = [
  '样品登记中', '合同评审中', '样品入库中', '样品出库领取中',
  '样品出库领取完成', '检测数据录入中', '委托更改中', '检测更改中',
  '报告审核中', '报告批准中', '报告签发中', '报告盖章中',
  '报告已盖章，归档中，未发放', '报告已归档，发放中', '报告发放完成', '样品单已作废',
]

export const reportDataStatus = (row: StatusRow) => row.dataStatus || row.status || ''
export const reportDataStatusChoices = (rows: StatusRow[]) =>
  [...new Set([...reportDataStates, ...rows.map(reportDataStatus).filter(Boolean)])]
