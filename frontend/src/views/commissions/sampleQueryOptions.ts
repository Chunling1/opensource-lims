// Inquiry covers the complete workflow; registration and review keep their own options.
const inquiryStates = [
  '委托登记中', '委托登记完成', '合同评审中', '合同评审完成',
  '样品入库中', '样品入库完成', '样品出库中', '样品出库完成', '样品待领取', '样品已领取',
  '任务分配中', '任务分配完成', '任务处理中', '任务处理完成',
  '检测数据录入中', '检测数据录入完成', '检测数据校核中', '检测数据校核完成',
  '报告校核中', '报告校核完成', '报告审核中', '报告审核完成', '报告批准中', '报告批准完成',
  '报告打印中', '报告打印完成', '委托更改中', '检测更改中', '报告更改中',
  '委托作废申请中', '委托已作废', '报告更改审批中', '任务已取消', '终止',
] as const
// Match the existing backend values without renaming stored workflow states.
const storedValues: Partial<Record<typeof inquiryStates[number], string>> = {
  委托登记完成: '完成登记', 合同评审完成: '评审完成', 委托作废申请中: '作废申请中',
}
export const inquirySampleDataStatusOptions = [
  { value: '', label: '全部' },
  ...inquiryStates.map(label => ({ value: storedValues[label] ?? label, label })),
]
