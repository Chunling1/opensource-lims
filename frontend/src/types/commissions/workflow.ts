// A completed stage joins the next queue without changing stored facts on a read.
export const inboundStatus = (status: string) => ['评审完成', '合同评审完成', '委托复核完成'].includes(status) ? '样品入库中' : status
export const assignmentStatus = (status: string) => status === '样品入库完成' ? '任务分配中' : status
export const outboundStatus = (status: string) => status === '任务分配完成' ? '样品出库中' : status
export const dataEntryStatus = (status: string) => ['样品已领取', '任务处理完成'].includes(status) ? '检测数据录入中' : status
export const contractReviewStage = (status?: string) => !status || ['完成登记', '委托登记完成', '合同评审中', '委托复核中', '评审完成', '合同评审完成', '委托复核完成'].includes(status)
