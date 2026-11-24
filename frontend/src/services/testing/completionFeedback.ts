const labels: Record<string, string> = { conclusion: '结论', conclusionStatus: '结论状态', failedParameters: '不合格参数', notes: '备注', tester1Id: '试验人1', tester2Id: '试验人2', reviewerId: '指定审核人', approverId: '指定批准人', testDates: '试验日期', calibrationDate: '校准日期', reportDate: '报告日期', environment: '试验环境', equipmentIds: '试验设备' }
export function completionFieldMessages(errors: Record<string, string> = {}) {
  return [...new Set(Object.entries(errors).map(([key, message]) => {
    if (key === 'originalRecords') return ''
    const date = /^testDates\.(\d+)$/.exec(key)
    const label = date ? `第 ${Number(date[1]) + 1} 项试验日期` : labels[key]
    return label ? `${label}：${message}` : message
  }))].filter(Boolean)
}
