import { inboundStatus } from '../src/types/commissions/workflow'
import { entryCapabilities, seedCompletedReport, validateEntryCompletion } from './dataEntryDetail'
import { prepareReportRelease, commitReportRelease, supersedeReportRelease, demoLifecycleConfig, hasApprovedReport, isReportPrintSample, isReportSigningSample, isReportDistributionSample, isReportArchiveSample, type ReportLifecycleConfig } from './reportLifecycle'
import { queryEntryPeople, resolveEntryPerson } from './dataEntryPeople'
import { isReportCheckSample, reportCheckRows, parseReportCheckQuery, reportCheckCapabilities, parseReportCheckRejection, completeReportIssue } from './reportCheck'
import { reportStageColumns, reportStages, type ReportStage, type ReportCheckQuery } from '../src/types/reports/reportCheck'
import { isDataChangeSample, canChangeData, type DataChangeQuery } from '../src/types/testing/dataChanges'
import { dataChangeRows, parseDataChangeQuery } from './testingDataChanges'
import { parseSampleCompletionQuery, parseSampleCompletionResult, sampleCompletionRows } from './testingSampleCompletion'
import { sampleCompletionColumns, type SampleCompletionAction, type SampleCompletionQuery } from '../src/types/testing/sampleCompletion'
import { dataQueryRows, parseDataQueryQuery } from './testingDataQuery'
import { dataQueryColumns, type DataQueryQuery } from '../src/types/testing/dataQuery'
import { sampleCopyRows, sampleCopyDataStatus, parseSampleCopyQuery, parseSampleCopyInput, isSampleCopySample, resetCopiedWorkflow } from './testingSampleCopy'
import { parseReportQuery, reportQueryRows, canQueryVoid } from './reportQuery'
import { reportQueryColumns, type ReportQueryQuery } from '../src/types/reports/reportQuery'
import { sampleCopyColumns, sampleCopyNextState, availableSampleCopyStates, type SampleCopyQuery } from '../src/types/testing/sampleCopy'
import { isDataCheckSample, dataCheckRows, dataCheckCapabilities, parseDataCheckQuery } from './testingDataCheck'
import { dataCheckColumns, type DataCheckQuery } from '../src/types/testing/dataCheck'
import { fieldChanges } from './dataEntryRecords'
import { isDataEntrySample, dataEntryRows, parseDataEntryQuery } from './testingDataEntry'
import { dataEntryColumns, type DataEntryQuery } from '../src/types/testing/dataEntry'
import { inboundRows, outboundRows, isOutboundSample, isInboundSample, parseInboundReceipt } from './sampleInbound'
import { assignmentRows, parseAssignmentQuery, assignmentPending, assignmentReversible, assignmentPrintable, parseAssignmentSubmission } from './testingAssignment'
import { createAutoAssignment } from './autoAssignment'
import { isTaskQuerySample, taskQueryRows, parseTaskQuery, taskReturnAllowed } from './testingTaskQuery'
import { taskQueryColumns, type TaskQuery } from '../src/types/testing/taskQuery'
import { parsePickupQuery, pickupRows, pickupAllowed, parsePickupReceipt } from './testingPickup'
import { pickupColumns, pickupStates, type PickupQuery } from '../src/types/testing/pickup'
import type { TaskPrintSource } from './taskPrint'
import { assignmentColumns, assignmentConclusions, type AssignmentQuery } from '../src/types/testing/assignment'
import { flowRows, flowStatus, isFlowSample } from './sampleFlow'
import { flowColumns, flowDateEnabled, type FlowQuery } from '../src/types/samples/flow'
import { outboundStates } from '../src/types/samples/outbound'
import { disposalRows, isDisposalSample, allowedDisposalActions, disposalRequirement, parseDisposalReceipt } from './sampleDisposal'
import { disposalColumns, type DisposalAction, type DisposalQuery } from '../src/types/samples/disposal'
import type { OutboundAction } from '../src/types/samples/outbound'
import { allowedOutboundActions, parseOutboundReturn } from './sampleOutbound'
import { parseStockReceipt } from './stockReceipt'
import { resolvePlanSelection } from './testPlanSelection'
import { inboundColumns, type InboundAction, type InboundQuery } from '../src/types/samples/inbound'
import { cancellationRows, parseCancellationSubmission } from './cancellationApprovals'
import { cancellationColumns, canApproveCancellation, type CancellationQuery } from '../src/types/commissions/cancellationApproval'
import { changeRows } from './commissionChanges'
import { commissionChangeColumns, changeProblemSources, type CommissionChangeQuery } from '../src/types/commissions/commissionChanges'
import { tableCellText } from '../src/services/common/table'
import { sampleWorkflowDateFields } from '../src/types/commissions/sampleWorkflow'
import { sampleAdvancedFields, type SampleAdvancedKey } from '../src/types/commissions/sampleAdvancedQuery'
import { commissionAdvancedFields } from '../src/types/commissions/commissionAdvancedQuery'
import { createReviewChecks, reviewCheckMessages } from './reviewChecks'
import { emptyContractReview, reviewCheckOptions } from '../src/types/commissions/contractReview'
import { parseContractReview, parseReviewCheckOptions } from './contractReview'
import { bulkCommissionFields, bulkCommissionKeys } from '../src/types/commissions/commissionFields'
import type { BulkCommissionContext, BulkCommissionTarget } from '../src/types/commissions/bulkCommission'
import { getSampleReportConfig, validateReportSettings } from './sampleReportSettings'
import { manufacturers } from './sampleManufacturers'
import type { ManufacturerQuery } from '../src/types/commissions/manufacturer'
import { AppError } from '../src/services/common/errors'
import { testPlanGroups, testPlans, publicTestPlan } from './samplePlans'
import { queryTestBases, resolveTestBases } from './sampleTestBases'
import type { TestBasisQuery } from '../src/types/commissions/testBasis'
import type { TestPlanQuery } from '../src/types/commissions/sampleForm'
import { parseSampleDetails, parseSampleCommission, sampleFormOptions } from './sampleForm'
import { copySampleCommission } from '../src/types/commissions/sampleCommission'
import { summaryCommission, summarySample, summaryInquirySample } from './registrationSummary'
import { inquirySampleColumns, inquirySampleCell } from '../src/services/commissions/inquirySampleColumns'
import { commissionColumns, commissionCell, sampleColumns, sampleCell } from '../src/services/commissions/registrationColumns'
import { commissionDetailKeys, registrationDepartments, registrationInvoiceTypes } from '../src/types/commissions/commissionForm'
import { registrationContracts, registrationOrganizations } from './registrationReferences'
import type { RegistrationContractQuery, RegistrationOrganizationQuery } from '../src/types/commissions/commissionForm'
import type { Actor } from '../src/types/lims'
import type { RegistrationWorkspace, RegistrationKind, RegistrationState, RegistrationDependencies, RegistrationQuery, RegistrationRecord, RegistrationCommission, RegistrationSample, RegistrationCommissionInput, RegistrationSampleInput, DemoAttachment } from '../src/types/commissions/registration'
import { commissionSearchFields, sampleSearchFields, inquirySampleSearchFields } from '../src/types/commissions/registration'
import { sampleReadOnlyReason, demoCustomers, demoProjects, demoCategories, registrationCanWrite, registrationCanLink, registrationCanEdit, workspaceActions, workspaceCanEdit, type WorkflowRecord } from '../src/services/commissions/registrationService'

const sampleAttachmentStates = new Set([
  '委托登记中', '完成登记', '委托登记完成', '合同评审中', '评审完成', '合同评审完成',
  '样品入库中', '样品入库完成', '样品出库中', '样品出库完成', '样品待领取', '样品已领取',
  '任务分配中', '任务分配完成', '任务处理中', '任务处理完成', '检测数据录入中', '委托更改中', '检测更改中',
])
function workspaceCanManageAttachments(actor: Actor, kind: RegistrationKind, row: WorkflowRecord, workspace: RegistrationWorkspace = 'registration') {
  if (kind === 'commissions') return workspaceCanEdit(actor, kind, row, workspace)
  if (workspace === 'query' || (workspace === 'changes' && row.dataStatus !== '委托更改中')) return false
  return (row.dataStatus === '检测更改中' ? actor.roles.some(role => ['admin', 'testing'].includes(role)) : registrationCanWrite(actor, kind)) && ['pending', 'completed'].includes(row.status) && sampleAttachmentStates.has(row.dataStatus ?? '')
}
const has = (actor: Actor, roles: string[]) => actor.roles.includes('admin') || roles.some(r => actor.roles.includes(r))
const isAssignmentSample = (sample: RegistrationSample) => assignmentPending(sample) || assignmentReversible(sample)
const isPickupSample = (sample: RegistrationSample) => (pickupStates as readonly string[]).includes(sample.dataStatus) && !['voided', 'void_pending'].includes(sample.status)
const visible = (actor: Actor, row: RegistrationRecord) => actor.scope === 'all' || actor.departmentId === row.departmentId

export function seedRegistration(now = new Date()): RegistrationState {
  // Seed real commission dates within the default query window; never substitute createdAt in filtering.
  const commissionDate = (daysAgo: number) => {
    const date = new Date(now)
    date.setDate(date.getDate() - daysAgo)
    return serverDate(date)
  }
  const commissions: RegistrationCommission[] = Array.from({ length: 14 }, (_, i) => ({
    id: `demo-wt-${i + 1}`, code: `WT202609${String(i + 1).padStart(3, '0')}`,
    name: ['园区地表水例行检测', '建设工程材料检测', '食品出厂质量检测'][i % 3]! + `（第 ${i + 1} 批）`,
    customer: demoCustomers[i % 3]!, departmentId: i === 13 ? 'lab2' : 'lab', owner: i % 2 ? '李受理' : '演示用户',
    createdAt: `2026-09-${String(18 - i).padStart(2, '0')}T09:30:00+08:00`, commissionDate: commissionDate(i), version: 1,
    status: i % 7 === 4 || i % 7 === 6 ? '已完成' : '未完成',
    contract: registrationContracts[i % 4]!.code, dueDate: '2026-10-15', requirements: '按约定项目及方法进行检测。',
    contact: ['张经理', '刘工', '陈女士'][i % 3]!, phone: '13800000000', projects: i % 3 === 1 ? ['抗压强度'] : i % 3 === 2 ? ['微生物', '重金属'] : ['pH 值', '化学需氧量'],
    source: '客户送样', settlement: '预付', discount: 0, taxRate: 6, notes: '', completedReports: 1, openTasks: 0, attachments: [], events: [],
  }))
  const samples: RegistrationSample[] = Array.from({ length: 78 }, (_, i) => {
    const commission = commissions[i % commissions.length]!
    const categoryIndex = i % commissions.length % 3
    return { id: `demo-yp-${i + 1}`, code: `SP202609${String(i + 1).padStart(4, '0')}`, name: ['地表水样', '混凝土试块', '食品留样'][categoryIndex]! + ` ${i + 1}`,
      reportCode: `BG202609${String(i + 1).padStart(4, '0')}`,
      reviewStatus: 'unreviewed', sampleType: i % 5 === 4 ? '英文报告样品' : i % 10 === 6 ? '分项/阶段性报告样品' : i % 10 === 7 ? '补充报告' : '原始样品', dataStatus: i % 3 === 1 ? '完成登记' : '委托登记中',
      customer: commission.customer, departmentId: commission.departmentId, owner: i % 2 ? '赵样品' : '演示用户', createdAt: `2026-09-${String(18 - i % 12).padStart(2, '0')}T10:20:00+08:00`, version: 1,
      contact: commission.contact, phone: commission.phone, projects: [...commission.projects], notes: '', events: [], attachments: [], status: (['pending', 'completed', 'pending'] as const)[i % 3]!,
      commissionId: commission.id, commissionInfo: copySampleCommission(commission), category: demoCategories[categoryIndex]!, quantity: i % 3 + 1, unit: '份', storage: '按方法要求保存',
    }
  })
  // Dedicated sample issue examples, preserving the existing IDs and overall sample count.
  for (const [index, position] of [60, 62, 65, 68, 69, 71, 74, 77].entries()) {
    const sample = samples[position]!
    sample.dataStatus = '委托更改中'
    sample.details = parseSampleDetails({ testPlanId: 'general-1', testPlan: '常规检测方案', testPlanCode: 'CG' })
    sample.commissionChange = { source: changeProblemSources[index % changeProblemSources.length]!, submittedBy: index % 2 ? '李受理' : '演示用户',
      submittedAt: commissionDate(index), type: index % 2 ? '委托要求调整' : '信息更正',
      description: index % 2 ? '示例问题：请核对并更正样品委托信息中的联系方式。' : '示例问题：请核对样品名称及规格型号，修改后完成更改。', result: '问题处理中' }
  }
  // Examples for the cancellation queue and completed application results.
  for (const [index, position] of [51, 53, 56, 59, 41].entries()) {
    const sample = samples[position]!
    sample.voidApplication = { reason: '示例申请：客户要求撤回本次样品检测。', appliedAt: `${commissionDate(index)}T10:00:00+08:00`, appliedBy: { id: 'business', name: '张受理' }, previousStatus: sample.status as 'pending' | 'completed', previousDataStatus: sample.dataStatus, previousReviewStatus: sample.reviewStatus }
    if (index === 1 || index === 2) Object.assign(sample.voidApplication, { decision: index === 1 ? 'approved' : 'rejected', approvedAt: `${commissionDate(index)}T14:00:00+08:00`, approvedBy: { id: 'admin', name: '演示用户' }, rejectionReason: index === 2 ? '示例审批：申请依据不足，请与客户确认。' : '' })
    if (index !== 2) { sample.status = index === 1 ? 'voided' : 'void_pending'; sample.dataStatus = index === 1 ? '委托已作废' : '作废申请中' }
  }
  // Saved inbound facts seed the mock inbound queue.
  for (const [index, position] of [30, 32, 33, 35, 36, 38, 39, 42, 44, 45, 47, 48].entries()) {
    const sample = samples[position]!
    const plan = testPlans.find(plan => plan.id === ['thermal-1', 'pressure-1', 'temperature-1', 'temperature-11', 'temperature-21', 'pressure-2'][index % 6])!
    sample.details = parseSampleDetails({ testPlanId: plan.id, testPlan: plan.name, testPlanCode: plan.code })
    sample.status = 'completed'; sample.reviewStatus = 'approved'; sample.dataStatus = index % 4 === 3 ? '样品入库完成' : '样品入库中'
    sample.inboundInfo = { site: index % 2 ? '第二站点' : '总部站点', groupNumber: `MOCK-${String(index + 1).padStart(2, '0')}` }
  }
  // Saved outbound examples supplement records arriving from completed assignments.
  for (const [index, position] of [18, 19, 20, 21, 22, 23, 24, 25, 26, 27].entries()) {
    const sample = samples[position]!
    const plan = testPlans.find(plan => plan.id === (sample.departmentId === 'lab2' ? 'branch-1' : ['general-1', 'pressure-1', 'temperature-11'][index % 3]))!
    // Collected samples also enter data entry, where report filling requires a valid template combination.
    sample.details = parseSampleDetails({ testPlanId: plan.id, testPlan: plan.name, testPlanCode: plan.code,
      reportSettings: { formatId: 'product', titleId: 'default_lab', languageId: 'zh', layoutId: 'standard' } })
    sample.status = 'completed'; sample.reviewStatus = 'approved'; sample.dataStatus = outboundStates[index % outboundStates.length]!
  }
  // Disposal uses its own workflow queue, separate from inbound and outbound.
  for (const [index, position] of [28, 29, 31, 34, 37, 40, 57, 46, 49, 55].entries()) {
    const sample = samples[position]!
    const plan = testPlans.find(plan => plan.id === (sample.departmentId === 'lab2' ? 'branch-1' : ['general-1', 'pressure-1', 'temperature-11'][index % 3]))!
    sample.details = parseSampleDetails({ testPlanId: plan.id, testPlan: plan.name, testPlanCode: plan.code })
    sample.status = 'completed'; sample.reviewStatus = 'approved'; sample.dataStatus = index % 2 ? '样品已处置' : '样品待处置'
    sample.details.disposalMethod = ['中心处置', '客户取回', '委托中心托运'][index % 3]!
    sample.disposalInfo = { retentionTime: `${commissionDate(index * 7 + 1)}T10:00:00+08:00` }
    sample.sampleCompletionInfo = { status: index < 5 && index % 2 === 0 ? '样品待处理' : '样品已处理' }
    if (sample.sampleCompletionInfo.status === '样品已处理') sample.sampleCompletionInfo.processedAt = `${commissionDate(index * 7 + 2)}T10:00:00+08:00`
    if (index % 2) sample.disposalInfo.receipt = { result: '模拟处置记录', name: '演示用户', date: commissionDate(index * 7), customerRequirement: sample.details.disposalMethod, recordedAt: `${commissionDate(index * 7)}T10:00:00+08:00`, recordedBy: { id: 'admin', name: '演示用户' } }
  }
  // Coherent saved facts for the demo flow stages; query code never fabricates missing dates.
  for (const sample of samples.filter(isFlowSample)) {
    const status = flowStatus(sample)
    const daysAgo = sample.disposalInfo?.retentionTime
      ? Math.floor((now.getTime() - Date.parse(sample.disposalInfo.retentionTime)) / 86400000) + 4
      : samples.indexOf(sample) % 8 + 4
    sample.inboundInfo = { site: '', groupNumber: '', ...sample.inboundInfo, receipt: {
      account: 'admin', name: '演示用户', date: commissionDate(daysAgo), location: '检测室', condition: '正常', notes: '',
      recordedAt: `${commissionDate(daysAgo)}T10:00:00+08:00`, recordedBy: { id: 'admin', name: '演示用户' },
    } }
    if (flowDateEnabled('outbound', status)) sample.outboundInfo = { receipt: {
      account: 'admin', name: '演示用户', date: commissionDate(daysAgo - 1),
      recordedAt: `${commissionDate(daysAgo - 1)}T10:00:00+08:00`, recordedBy: { id: 'admin', name: '演示用户' },
    } }
    if (flowDateEnabled('collection', status)) sample.flowInfo = { collection: { name: '李检测', date: commissionDate(daysAgo - 2) } }
  }
  // Assignment examples supplement completed inbound records in the same queue.
  for (const [index, position] of [50, 52, 54, 58, 61, 63, 64, 66, 67, 70, 72, 73].entries()) {
    const sample = samples[position]!
    sample.status = 'completed'; sample.reviewStatus = 'approved'; sample.dataStatus = index % 4 === 3 ? '任务分配完成' : '任务分配中'
    sample.details = parseSampleDetails({ testPlanId: 'general-1', testPlan: '常规检测方案', testPlanCode: 'CG', requestedTestDate: commissionDate(index), hasAppointment: true, appointmentDate: commissionDate(index) })
    sample.assignmentInfo = { conclusion: assignmentConclusions[index % assignmentConclusions.length], ...(index % 4 === 3 ? { assignedBy: '演示用户', dataEntryPerson: '李检测', tester1: '李检测', tester2: '王复核' } : {}) }
  }
  // Data-entry examples supplement collected samples entering the recording queue.
  for (const [index, position] of [75, 76].entries()) {
    const sample = samples[position]!
    sample.status = 'completed'; sample.reviewStatus = 'approved'; sample.dataStatus = index ? '检测数据录入完成' : '检测数据录入中'
    sample.details = parseSampleDetails({ testPlanId: 'general-1', testPlan: '常规检测方案', testPlanCode: 'CG', requestedTestDate: commissionDate(0), inspector: '李检测' })
    sample.assignmentInfo = { assignedBy: '演示用户', assignedById: 'admin', dataEntryPerson: '李检测', dataEntryPersonId: 'analyst', assignedDate: commissionDate(2), tester1: '李检测', conclusion: index ? '合格' : '其它' }
    sample.workflow = { testStartDate: commissionDate(1), ...(index ? { testEndDate: commissionDate(0) } : {}) }
    sample.dataEntryInfo = { tester1: '李检测', tester2: '' }; sample.details!.reportSettings = { formatId: 'product', titleId: 'default_lab', languageId: 'zh', layoutId: 'standard' }
  }
  // Separate detection-change examples reuse valid entry settings without altering existing queues.
  for (const [index, planId] of ['general-1', 'pressure-1', 'temperature-11'].entries()) {
    const sample = structuredClone(samples[75]!), plan = testPlans.find(row => row.id === planId)!
    const number = 79 + index
    sample.id = `demo-yp-${number}`; sample.code = `SP202609${String(number).padStart(4, '0')}`; sample.reportCode = `BG202609${String(number).padStart(4, '0')}`
    sample.name = `检测更改样品 ${number}`; sample.dataStatus = '检测更改中'
    Object.assign(sample.details!, { testPlanId: plan.id, testPlan: plan.name, testPlanCode: plan.code })
    sample.dataChange = { source: changeProblemSources[index % 2]!, submittedBy: '演示用户', submittedAt: commissionDate(index), type: '检测数据更正', description: '请核对并更正检测数据，处理后完成更改。', result: '问题处理中' }
    samples.push(sample)
  }
  // Report checking has its own saved facts, independent of testing data checking.
  for (const [index, planId] of ['general-1', 'pressure-1', 'branch-1'].entries()) {
    const sample = structuredClone(samples[76]!), plan = testPlans.find(row => row.id === planId)!, number = 82 + index
    sample.id = `demo-yp-${number}`; sample.code = `SP202609${String(number).padStart(4, '0')}`; sample.reportCode = `BG202609${String(number).padStart(4, '0')}`
    sample.name = `报告校核样品 ${number}`; sample.dataStatus = index === 1 ? '报告校核完成' : '报告校核中'
    sample.departmentId = index === 2 ? 'lab2' : 'lab'; sample.reportChangeCount = index
    Object.assign(sample.details!, { testPlanId: plan.id, testPlan: plan.name, testPlanCode: plan.code })
    if (index === 1) sample.reportCheckInfo = { actorId: 'reviewer', actorName: '王复核', at: `${commissionDate(0)}T10:00:00+08:00` }
    const review = emptyContractReview(), checkedAt = `${commissionDate(2)}T10:00:00+08:00`
    sample.contractReview = { ...review, decision: 'approved', compliance: {
      result: { id: `demo-contract-check-${number}`, sampleId: sample.id, sampleVersion: sample.version, checkedAt, reviewOptions: reviewCheckOptions(review), messages: reviewCheckMessages(sample) },
      readConfirmed: true, confirmedBy: { id: 'reviewer', name: '王复核' }, confirmedAt: checkedAt,
    } }
    samples.push(sample)
  }
  for (const [stageIndex, stage] of (['review', 'approval'] as const).entries()) {
    const config = reportStages[stage]
    for (const index of [0, 1, 2]) {
      const sample = structuredClone(samples.find(row => row.id === 'demo-yp-82')!), number = 85 + stageIndex * 3 + index
      sample.id = `demo-yp-${number}`; sample.code = `SP202609${String(number).padStart(4, '0')}`; sample.reportCode = `BG202609${String(number).padStart(4, '0')}`
      sample.name = `${config.title}样品 ${number}`; sample.dataStatus = index === 1 ? config.completed : config.pending
      sample.departmentId = index === 2 ? 'lab2' : 'lab'
      const fact = { actorId: 'reviewer', actorName: '王复核', at: `${commissionDate(0)}T10:00:00+08:00`, date: commissionDate(0) }
      sample.reportCheckInfo = { ...fact }
      sample.workflow = { ...sample.workflow, auditDate: undefined, approvalDate: undefined }
      if (stage === 'approval') { sample.reportReviewInfo = { ...fact }; sample.workflow.auditDate = fact.date }
      if (index === 1) {
        sample[config.infoKey] = { ...fact, ...(stage === 'approval' ? { actorId: 'approver', actorName: '陈批准' } : {}) }
        sample.workflow[stage === 'review' ? 'auditDate' : 'approvalDate'] = fact.date
      }
      if (sample.contractReview?.compliance) { sample.contractReview.compliance.result.sampleId = sample.id; sample.contractReview.compliance.result.id = `demo-contract-check-${number}`; sample.contractReview.compliance.result.messages = reviewCheckMessages(sample) }
      samples.push(sample)
    }
  }
  for (const [index, form] of (['纸质', '纸质', '电子', '电子', '纸质', '电子', '纸质'] as const).entries()) {
    const sample = structuredClone(samples.find(row => row.id === 'demo-yp-88')!), number = 91 + index
    sample.id = `demo-yp-${number}`; sample.code = `SP20260900${number}`; sample.reportCode = `BG20260900${number}`
    sample.name = `${form}报告流程演示 ${number}`; sample.details!.reportForm = form
    sample.dataStatus = '报告批准完成'; sample.reportApprovalInfo = { actorId: 'admin', actorName: '演示用户', at: now.toISOString(), nextAction: 'next' }
    samples.push(sample)
  }
  const state: RegistrationState = { commissions, samples }
  for (const sample of samples.filter(row => /^报告/.test(row.dataStatus))) seedCompletedReport(state, sample)
  return state
}
function fail(message: string, code: 'BUSINESS_RULE' | 'VALIDATION' | 'FORBIDDEN' | 'NOT_FOUND' = 'BUSINESS_RULE'): never { throw new AppError(code, message) }
function field(value: string, label: string, max = 150) { if (!value?.trim() || value.length > max) fail(`请填写${label}（不超过 ${max} 字）。`, 'VALIDATION') }
function validDate(value: string) { return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value }
export function serverDate(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
function filter<T extends RegistrationRecord & { status: string; contract?: string; projectRegistrationCode?: string; projectTradingCode?: string; category?: string; commissionId?: string; commissionDate?: string; reportCode?: string; sampleType?: string; dataStatus?: string; commissionInfo?: RegistrationSample['commissionInfo']; details?: RegistrationSample['details']; contractReview?: RegistrationSample['contractReview']; workflow?: RegistrationSample['workflow'] }>(rows: T[], query: RegistrationQuery, kind: RegistrationKind, workspace: RegistrationWorkspace = 'registration') {
  const keyword = query.keyword?.trim().toLocaleLowerCase()
  if (query.from && !validDate(query.from) || query.to && !validDate(query.to) || query.from && query.to && query.from > query.to) fail(kind === 'commissions' ? '请检查委托日期范围。' : '请检查登记日期范围。', 'VALIDATION')
  if (query.commissionFrom && !validDate(query.commissionFrom) || query.commissionTo && !validDate(query.commissionTo) || query.commissionFrom && query.commissionTo && query.commissionFrom > query.commissionTo) fail('请检查委托日期范围。', 'VALIDATION')
  for (const { key, label } of sampleWorkflowDateFields) {
    const range = query.sampleWorkflow?.dates?.[key]
    if (range && (!validDate(range.from) || !validDate(range.to) || range.from > range.to)) fail(`请检查${label}范围。`, 'VALIDATION')
  }
  const selected = query.ids ? new Set(query.ids) : null
  const commissions = query.commissionIds ? new Set(query.commissionIds) : null
  const contains = (value: string | undefined, text: string) => (value || '').toLocaleLowerCase().includes(text.toLocaleLowerCase())
  const sampleContent = (row: T, field: SampleAdvancedKey | typeof sampleSearchFields[number]['value']) => {
    switch (field) {
      case 'commissionCode': return row.commissionInfo?.code
      case 'projectName': return row.commissionInfo?.name
      case 'contract': return row.commissionInfo?.contract
      case 'projectRegistrationCode': return row.commissionInfo?.projectRegistrationCode
      case 'projectTradingCode': return row.commissionInfo?.projectTradingCode
      case 'erpContract': return row.commissionInfo?.erpContract
      case 'projects': return row.projects.join('；')
      case 'specification': return row.details?.specification
      case 'inspector': return row.details?.inspector
      case 'commissionOwner': return row.commissionInfo?.owner
      case 'customer': return row.commissionInfo?.customer
      case 'contact': return row.commissionInfo?.contact
      case 'manufacturer': return row.details?.manufacturer
      case 'reviewer': {
        // Use the latest review operation; withdrawal removes the current reviewer.
        const event = [...row.events].reverse().find(event => ['开始合同评审', '评审通过', '评审不通过', '撤销评审'].includes(event.action))
        if (event) return event.action === '撤销评审' ? '' : event.actor
        return row.contractReview?.compliance?.confirmedBy?.name
      }
      case 'all': return ''
      default: return row[field]
    }
  }
  const matchesQuery = (row: T) => {
    if (kind === 'commissions' && query.commissionAdvanced && !commissionAdvancedFields.every(({ key }) => !query.commissionAdvanced![key] || contains(row[key], query.commissionAdvanced![key]!))) return false
    if (kind === 'samples') {
      if (query.sampleWorkflow?.conclusion && row.workflow?.conclusion !== query.sampleWorkflow.conclusion) return false
      if (!sampleWorkflowDateFields.every(({ key }) => {
        const range = query.sampleWorkflow?.dates?.[key]
        const date = row.workflow?.[key]
        return !range || !!date && validDate(date) && date >= range.from && date <= range.to
      })) return false
      if (query.sampleAdvanced && !sampleAdvancedFields.every(({ key }) => !query.sampleAdvanced![key] || contains(sampleContent(row, key), query.sampleAdvanced![key]!))) return false
      if (query.sampleCode && !contains(row.code, query.sampleCode) || query.reportCode && !contains(row.reportCode, query.reportCode)) return false
      if (query.dataStatus && row.dataStatus !== query.dataStatus || query.sampleType && row.sampleType !== query.sampleType) return false
      const date = row.commissionInfo?.commissionDate
      if ((query.commissionFrom || query.commissionTo) && (!date || query.commissionFrom && date < query.commissionFrom || query.commissionTo && date > query.commissionTo)) return false
    }
    if (kind === 'commissions' && query.commissionCode && !contains(row.code, query.commissionCode)) return false
    if (keyword && !contains(`${row.code} ${row.name} ${kind === 'commissions' ? row.customer : ''}`, keyword)) return false
    if (!query.contains) return true
    if (kind === 'samples') return (workspace === 'query' ? inquirySampleSearchFields : sampleSearchFields).some(field => field.value !== 'all' && (!query.searchField || query.searchField === 'all' || query.searchField === field.value) && contains(sampleContent(row, field.value), query.contains!))
    if (query.searchField && query.searchField !== 'all') {
      const field = [...commissionSearchFields, { value: 'contract' as const }].find(field => field.value !== 'all' && field.value === query.searchField)
      return !!field && field.value !== 'all' && contains(row[field.value], query.contains)
    }
    return commissionSearchFields.some(field => field.value !== 'all' && contains(row[field.value], query.contains!))
  }
  const matchesDate = (row: T) => {
    const date = kind === 'commissions' ? row.commissionDate : row.createdAt.slice(0, 10)
    return (!query.from && !query.to) || !!date && (!query.from || date >= query.from) && (!query.to || date <= query.to)
  }
  const items = rows.filter(r => matchesDate(r) && matchesQuery(r) && (!query.status || r.status === query.status) && (!query.customer || r.customer.includes(query.customer)) && (!query.owner || r.owner.includes(query.owner)) && (!query.contract || !!r.contract?.includes(query.contract)) && (!query.category || r.category === query.category) && (query.commissionId === undefined || r.commissionId === query.commissionId) && (!commissions || !!r.commissionId && commissions.has(r.commissionId)) && (!selected || selected.has(r.id)))
  const key = query.sort === 'code' ? 'code' : kind === 'commissions' && query.sort === 'commissionDate' ? 'commissionDate' : 'createdAt', direction = query.direction === 'asc' ? 1 : -1
  return items.sort((a, b) => {
    const left = a[key] || '', right = b[key] || ''
    if (!left !== !right) return left ? -1 : 1 // Missing dates remain last in either direction.
    return (left.localeCompare(right, 'zh-CN', { numeric: true }) || a.id.localeCompare(b.id, 'zh-CN', { numeric: true })) * direction
  })
}
function page<T>(items: T[], q: Pick<RegistrationQuery, 'page' | 'pageSize'>, kind: RegistrationKind) {
  const sizes = kind === 'commissions' ? [5, 10, 20] : [10, 20, 50]
  const pageSize = sizes.includes(q.pageSize || 0) ? q.pageSize! : sizes[0]!
  const requested = Number.isFinite(q.page) ? Math.floor(q.page!) : 1
  const current = Math.min(Math.max(1, requested), Math.max(1, Math.ceil(items.length / pageSize)))
  return { items: items.slice((current - 1) * pageSize, current * pageSize), total: items.length, page: current, pageSize }
}
export function registrationCsv(rows: unknown[][]) {
  const cell = (value: unknown) => { const text = String(value ?? ''); return `"${(/^[=+\-@\t\r]/.test(text) ? "'" : '') + text.replaceAll('"', '""')}"` }
  return '\uFEFF' + rows.map(row => row.map(cell).join(',')).join('\r\n')
}
export function createRegistrationService(dependencies: RegistrationDependencies, reviewChecks = createReviewChecks(), autoAssignment = createAutoAssignment(), lifecycleConfig: ReportLifecycleConfig = demoLifecycleConfig) {
  let memory: RegistrationState | undefined
  function actor(kind: RegistrationKind) {
    if (dependencies.locked?.()) throw new AppError('LOCKED', '工作空间已锁定。')
    const a = dependencies.actor()
    if (!has(a, kind === 'samples' ? ['samples', 'commissions', 'testing', 'reviewer', 'approver', 'reports'] : ['commissions', 'finance', 'testing', 'sampling', 'samples', 'reports', 'reviewer', 'approver'])) fail('当前身份无权查看此列表。', 'FORBIDDEN')
    return a
  }
  function read() { return structuredClone(dependencies.read?.() ?? (memory ??= seedRegistration())) }
  function write<T>(run: (state: RegistrationState) => T): T {
    const next = read(), previous = new Map(next.samples.map(row => [row.id, row.dataStatus])), result = run(next)
    for (const sample of next.samples) {
      // Reversing disposal clears its receipt but preserves the original retention time.
      if (sample.dataStatus === '样品待处置' && !['样品待处置', '样品已处置'].includes(previous.get(sample.id) || '')) {
        sample.disposalInfo = { ...sample.disposalInfo, retentionTime: new Date().toISOString() }
      }
    }
    dependencies.write?.(next); memory = next
    return structuredClone(result)
  }
  function find(state: RegistrationState, kind: RegistrationKind, id: string, a: Actor) {
    const row = state[kind].find(r => r.id === id)
    if (!row || !visible(a, row)) fail('记录不存在或已不可访问。', 'NOT_FOUND')
    return row
  }
  function bulkRows(state: RegistrationState, ids: string[], a: Actor, workspace: RegistrationWorkspace = 'registration') {
    if (!registrationCanWrite(a, 'samples')) fail('当前身份无权批量修改样品。', 'FORBIDDEN')
    if (!Array.isArray(ids) || !ids.length || ids.length > 50 || ids.some(id => typeof id !== 'string' || !id) || new Set(ids).size !== ids.length) fail('请选择 1 至 50 张不重复的样品单。', 'VALIDATION')
    const rows = ids.map(id => find(state, 'samples', id, a) as RegistrationSample)
    if (rows.some(row => hasApprovedReport(row) && !(workspace === 'changes' && row.dataStatus === '委托更改中'))) fail('已批准报告不能直接批量修改，请先通过报告更改处理。')
    if (!rows[0]!.commissionId || rows.some(row => row.commissionId !== rows[0]!.commissionId)) fail('只能批量修改同一委托单下的样品，不能跨委托单。')
    find(state, 'commissions', rows[0]!.commissionId, a)
    if (rows.some(row => !workspaceCanEdit(a, 'samples', row, workspace))) fail(workspace === 'review' ? '所选样品包含已评审或已作废记录。' : '所选样品包含已完成或已作废记录，请仅选择未完成样品。')
    return rows
  }
  function matching(state: RegistrationState, kind: RegistrationKind, q: RegistrationQuery, workspace: RegistrationWorkspace = 'registration') {
    const a = actor(kind)
    if (kind === 'samples') {
      if (q.commissionId !== undefined) find(state, 'commissions', q.commissionId, a)
      for (const id of q.commissionIds ?? []) find(state, 'commissions', id, a)
    }
    return filter<RegistrationCommission | RegistrationSample>(state[kind].filter(r => visible(a, r) && (!q.eligibleOnly || kind !== 'commissions' || r.status === '未完成')), q, kind, workspace)
  }
  function sampleRows(state: RegistrationState, q: RegistrationQuery, workspace: RegistrationWorkspace = 'registration') {
    const a = actor('samples')
    return (matching(state, 'samples', q, workspace) as RegistrationSample[])
      // Default to the active queue; an explicit completed filter retrieves reviewed history.
      // Scope is decided before pagination/export, never filtered by the browser.
      .filter(s => workspace !== 'changes' || s.dataStatus === '委托更改中' && !sampleReadOnlyReason(s.status))
      .filter(s => workspace !== 'review' || (s.dataStatus !== '委托更改中' && s.status === 'completed' && (q.dataStatus === '评审完成' ? s.reviewStatus === 'approved' : s.reviewStatus !== 'approved'))).map(s => {
      const order = state.commissions.find(c => c.id === s.commissionId && visible(a, c))
      return { ...s, commissionId: order?.id ?? '', commissionCode: order ? s.commissionInfo.code : '', commissionName: order ? s.commissionInfo.name : '' }
    })
  }
  function audit(row: RegistrationRecord, a: Actor, action: string, reason = '') { row.version++; row.events.push({ at: new Date().toISOString(), actor: a.name, action, reason }) }
  
  function reviewBatch(state: RegistrationState, input: unknown, a: Actor, started = false) {
    if (!registrationCanWrite(a, 'samples')) fail('当前身份无权批量评审样品。', 'FORBIDDEN')
    if (!Array.isArray(input) || !input.length || input.length > 50 || input.some(item => !item || typeof item.id !== 'string' || !item.id || !Number.isSafeInteger(item.version) || item.version < 1) || new Set(input.map(item => item.id)).size !== input.length) throw new AppError('BAD_REQUEST', '请选择 1 至 50 个不重复的样品，并提供有效版本。')
    return input.map(item => {
      const sample = find(state, 'samples', item.id, a) as RegistrationSample
      
      if (sample.status !== 'completed' || !workspaceActions(a, 'samples', sample, 'review').some(action => action.id === 'review' && !action.disabled) || started && sample.reviewStatus !== 'reviewed') fail(`${sample.code} 当前状态不允许批量评审，请刷新列表。`)
      return sample
    })
  }
  const batchReviewScope = (samples: RegistrationSample[]) => 'contract-batch:' + JSON.stringify(samples.map(sample => sample.id).sort())
  function reportBatch(state: RegistrationState, input: unknown, a: Actor, stage: ReportStage) {
    const config = reportStages[stage]
    if (!has(a, stage === 'approval' ? ['approver'] : ['reports', 'reviewer'])) fail(`当前身份无权执行${config.title}。`, 'FORBIDDEN')
    if (!Array.isArray(input) || !input.length || input.length > 50 || input.some(item => !item || typeof item.id !== 'string' || !item.id || !Number.isSafeInteger(item.version) || item.version < 1) || new Set(input.map(item => item.id)).size !== input.length) throw new AppError('BAD_REQUEST', '请选择 1 至 50 个不重复的样品，并提供有效版本。')
    return input.map(item => {
      const sample = find(state, 'samples', item.id, a) as RegistrationSample
      
      if (!reportCheckCapabilities(a, sample, stage).canCheck) fail(`${sample.code} 当前状态不允许${config.title}，请刷新列表。`)
      return sample
    })
  }
  const reportBatchScope = (samples: RegistrationSample[], stage: ReportStage) => `report-batch-${stage}:` + JSON.stringify(samples.map(sample => sample.id).sort())
  function applyContractReview(sample: RegistrationSample, a: Actor, review: unknown, scope = 'contract') {
    const parsed = parseContractReview(review), input = review as Record<string, unknown>
    parsed.notes = sample.contractReview?.notes ?? parsed.notes
    const checked = parsed.decision === 'approved'
      ? reviewChecks.verify(a.id, sample, input.checkId, input.readConfirmed, parsed, scope)
      : reviewChecks.matching(a.id, sample, input.checkId, parsed, scope)
    if (checked) parsed.compliance = { result: checked, readConfirmed: input.readConfirmed === true, ...(input.readConfirmed === true ? { confirmedBy: { id: a.id, name: a.name }, confirmedAt: new Date().toISOString() } : {}) }
    sample.contractReview = parsed
    sample.reviewStatus = parsed.decision === 'approved' ? 'approved' : 'unreviewed'
    sample.dataStatus = parsed.decision === 'approved' ? '评审完成' : '完成登记'
  }
  function applyReportAction(sample: RegistrationSample, a: Actor, action: string, stage: ReportStage, confirmation?: unknown, rejection?: unknown, scope = stage === 'check' ? 'report' : 'report-' + stage) {
    const config = reportStages[stage]
    if (action === 'check') {
      const proof = confirmation && typeof confirmation === 'object' && !Array.isArray(confirmation) ? confirmation as Record<string, unknown> : undefined
      const result = reviewChecks.verify(a.id, sample, proof?.reviewCheckId, proof?.readConfirmed, reviewCheckOptions(sample.contractReview ?? emptyContractReview()), scope)
      if (proof?.nextAction !== 'next' && proof?.nextAction !== 'transfer') throw new AppError('VALIDATION', `请选择${config.label}通过后的下一步动作。`)
      const recipient = proof.nextAction === 'transfer' ? resolveEntryPerson({ role: config.role, id: proof.recipientId }) : undefined
      if (proof.nextAction === 'next' && proof.recipientId) throw new AppError('VALIDATION', '下一步无需指定接收人，请重新确认。')
      const at = new Date().toISOString()
      sample[config.infoKey] = { actorId: a.id, actorName: a.name, at, date: serverDate(),
        nextAction: proof.nextAction, ...(recipient ? { recipient: { id: recipient.id, name: recipient.name } } : {}),
        reviewConfirmation: { result: structuredClone(result), readConfirmed: true, confirmedBy: { id: a.id, name: a.name }, confirmedAt: at } }
      sample.dataStatus = proof.nextAction === 'transfer' ? config.pending : config.completed
      if (stage !== 'check') {
        sample.workflow ??= {}
        sample.workflow[stage === 'review' ? 'auditDate' : 'approvalDate'] = proof.nextAction === 'next' ? serverDate() : undefined
      }
    } else if (action === 'reject') {
      const input = parseReportCheckRejection(rejection), at = new Date().toISOString(), issueId = crypto.randomUUID()
      sample.reportCheckIssues = [...(sample.reportCheckIssues || []), { ...input, stage, id: issueId, submittedAt: at, submittedBy: { id: a.id, name: a.name } }]
      const change = { reportIssueId: issueId, source: '问题处理', submittedBy: a.name, submittedAt: at, type: input.problemType, description: input.reason, result: '问题处理中' as const }
      if (input.destination === 'commission') { sample.commissionChange = change; sample.dataStatus = '委托更改中' }
      else { sample.dataChange = change; sample.dataStatus = '检测更改中' }
      delete sample[config.infoKey]
      if (sample.workflow && stage !== 'check') sample.workflow[stage === 'review' ? 'auditDate' : 'approvalDate'] = undefined
    } else {
      sample.dataStatus = config.pending
      delete sample[config.infoKey]
      if (sample.workflow && stage !== 'check') sample.workflow[stage === 'review' ? 'auditDate' : 'approvalDate'] = undefined
    }
    const transferred = action === 'check' && sample[config.infoKey]?.nextAction === 'transfer'
    const issue = action === 'reject' ? sample.reportCheckIssues!.at(-1)! : undefined
    audit(sample, a, transferred ? `报告转交${config.label}` : action === 'check' ? `${config.title}通过` : action === 'reject' ? `${config.title}不通过` : `撤销${config.title}`, transferred ? `接收人：${sample[config.infoKey]!.recipient!.name}（${sample[config.infoKey]!.recipient!.id}）` : issue ? `${issue.destination === 'commission' ? '退回委托更改' : '退回检测数据更改'}：${issue.reason}` : '')
  }
  function requestSampleVoid(sample: RegistrationSample, a: Actor, reason: string) {
    field(reason, '申请作废原因', 500)
    if (sample.status !== 'pending' && sample.status !== 'completed') fail('当前状态不允许提交作废申请。')
    sample.voidApplication = { reason: reason.trim(), appliedAt: new Date().toISOString(), appliedBy: { id: a.id, name: a.name }, previousStatus: sample.status, previousDataStatus: sample.dataStatus, previousReviewStatus: sample.reviewStatus }
    sample.status = 'void_pending'; sample.dataStatus = '作废申请中'
  }
  function checkInput(input: { name: string; customer: string; projects: string[] }) { field(input.name, '名称'); if (input.customer.length > 500) fail('委托单位名称不能超过 500 字。', 'VALIDATION'); if (!input.projects.length || input.projects.some(p => !demoProjects.includes(p))) fail('请选择有效检测项目。', 'VALIDATION') }
  function base(state: RegistrationState, kind: RegistrationKind, a: Actor) {
    const now = new Date().toISOString()
    return { id: crypto.randomUUID(), code: `${kind === 'commissions' ? 'WT' : 'SP'}${now.slice(0, 10).replaceAll('-', '')}${String(state[kind].length + 1).padStart(4, '0')}`, departmentId: a.departmentId, owner: a.name, createdAt: now, version: 0, events: [] }
  }
  return {
    async commissionDefaults() {
      const a = actor('commissions')
      if (!registrationCanWrite(a, 'commissions')) fail('当前身份无权登记委托。', 'FORBIDDEN')
      return { commissionDate: serverDate() }
    },
    async manufacturers(query: ManufacturerQuery = {}) {
      const a = actor('samples')
      const available = manufacturers.filter(row => a.scope === 'all' || row.departmentId === a.departmentId)
      const matches = (value: string, filter?: string) => !filter || value.toLocaleLowerCase().includes(filter.toLocaleLowerCase())
      const result = page(available.filter(row => matches(row.code, query.code) && matches(row.name, query.name) && (!query.type || row.type === query.type)), query, 'commissions')
      return { ...result, items: result.items.map(({ departmentId, ...row }) => row), types: [...new Set(available.map(row => row.type))] }
    },
    async organizations(query: RegistrationOrganizationQuery = {}) {
      const a = actor('commissions'), keywords = (query.keyword || '').split(/[；;\r\n]+/).map(name => name.trim().toLocaleLowerCase()).filter(Boolean)
      const result = page(registrationOrganizations.filter(r => (a.scope === 'all' || r.departmentId === a.departmentId) && (!keywords.length || keywords.some(keyword => r.name.toLocaleLowerCase().includes(keyword)))), query, 'commissions')
      return { ...result, items: result.items.map(({ id, name }) => ({ id, name })) }
    },
    async contracts(query: RegistrationContractQuery = {}) {
      const a = actor('commissions'), keyword = query.keyword?.trim().toLocaleLowerCase()
      if (query.from && !validDate(query.from) || query.to && !validDate(query.to) || query.from && query.to && query.from > query.to) fail('请检查签订日期范围。', 'VALIDATION')
      const code = query.code?.trim().toLocaleLowerCase()
      return page(registrationContracts.filter(r => {
        if (a.scope !== 'all' && r.departmentId !== a.departmentId || query.ownDepartment && r.departmentId !== a.departmentId) return false
        const content = query.searchField && query.searchField !== 'all' ? r[query.searchField] : [r.code, r.name, r.customer, r.projectName, r.projectAddress, r.constructionCompany, r.registrationStatus].join(' ')
        return (!code || r.code.toLocaleLowerCase().includes(code)) && (!keyword || content.toLocaleLowerCase().includes(keyword)) && (!query.from || r.signedDate >= query.from) && (!query.to || r.signedDate <= query.to)
      }), query, 'commissions')
    },
    async testPlanSelection(selection: unknown, toggle?: unknown, sampleScope?: unknown) {
      const a = actor('samples')
      if (sampleScope !== undefined && !['inbound', 'outbound', 'disposal', 'flow', 'assignment', 'pickup', 'task-query', 'data-entry', 'data-check', 'sample-copy', 'data-changes', 'report-check', 'report-review', 'report-approval', 'report-print', 'report-signing', 'report-distribution', 'report-archive', 'report-query'].includes(String(sampleScope))) throw new AppError('BAD_REQUEST', '样品范围有误。')
      const populatedIds = sampleScope === undefined ? undefined : new Set(sampleRows(read(), {}).filter(sampleScope === 'report-query' ? (() => true) : sampleScope === 'report-archive' ? isReportArchiveSample : sampleScope === 'report-distribution' ? isReportDistributionSample : sampleScope === 'report-signing' ? isReportSigningSample : sampleScope === 'report-print' ? isReportPrintSample : sampleScope === 'report-review' ? (sample => isReportCheckSample(sample, 'review')) : sampleScope === 'report-approval' ? (sample => isReportCheckSample(sample, 'approval')) : sampleScope === 'report-check' ? (sample => isReportCheckSample(sample)) : sampleScope === 'data-changes' ? isDataChangeSample : sampleScope === 'sample-copy' ? isSampleCopySample : sampleScope === 'data-check' ? isDataCheckSample : sampleScope === 'data-entry' ? isDataEntrySample : sampleScope === 'task-query' ? isTaskQuerySample : sampleScope === 'assignment' ? isAssignmentSample : sampleScope === 'pickup' ? isPickupSample : sampleScope === 'flow' ? isFlowSample : sampleScope === 'disposal' ? isDisposalSample : sampleScope === 'outbound' ? isOutboundSample : isInboundSample).map(row => row.details?.testPlanId || '').filter(Boolean))
      const result = resolvePlanSelection(a, selection, toggle, populatedIds)
      return { ...result.state, catalogue: result.catalogue }
    },
    async copySample(id: string, raw: Record<string, unknown>) {
      const a = actor('samples'), input = parseSampleCopyInput(raw)
      if (!has(a, ['testing'])) fail('当前身份无权复制样品。', 'FORBIDDEN')
      return write(state => {
        const source = find(state, 'samples', id, a) as RegistrationSample
        const fingerprint = JSON.stringify({ id, ...input })
        const previous = state.samples.find(row => row.copyInfo?.actorId === a.id && row.copyInfo.requestId === input.requestId)
        if (previous) {
          if (previous.copyInfo!.fingerprint !== fingerprint) fail('复制请求已改变，请重新打开对话框。', 'BUSINESS_RULE')
          return previous
        }
        
        if (!isSampleCopySample(source) || ['委托作废申请中', '委托已作废', '任务已取消', '终止'].includes(sampleCopyDataStatus(source))) fail('当前样品状态不允许复制。')
        if (!availableSampleCopyStates(sampleCopyDataStatus(source)).some(status => status === input.dataStatus)) fail('复制状态不能超过原报告当前进度，请重新选择。', 'VALIDATION')
        if (input.testingDepartment && !registrationDepartments.some(department => department.name === input.testingDepartment && (a.scope === 'all' || department.id === a.departmentId))) fail('无权选择此检测部门。', 'FORBIDDEN')
        if (!source.reportCode) fail('原样品缺少报告编号，无法复制。', 'VALIDATION')
        const reportCode = source.reportCode + input.reportSuffix
        if (state.samples.some(row => row.reportCode === reportCode)) fail('复制后的报告编号已存在，请调整后缀或选择其他样品。', 'VALIDATION')
        const created = base(state, 'samples', a)
        while (state.samples.some(row => row.code === created.code)) created.code += 'C'
        const row: RegistrationSample = { ...structuredClone(source), ...created, departmentId: source.departmentId, events: structuredClone(source.events),
          reportCode, sampleType: input.sampleType, dataStatus: input.dataStatus, status: input.dataStatus === '委托登记中' ? 'pending' : 'completed',
          copyInfo: { sourceId: source.id, sourceCode: source.code, actorId: a.id, requestId: input.requestId, fingerprint, pendingStatus: sampleCopyNextState(input.dataStatus) } }
        // A copy has a new report number: never reuse approval files, signatures or delivery records.
        resetCopiedWorkflow(row)
        if (row.details && input.testingDepartment) row.details.testingDepartment = input.testingDepartment
        if (state.dataEntries?.[id]) state.dataEntries[row.id] = structuredClone(state.dataEntries[id])
        if (state.originalRecords?.[id]) state.originalRecords[row.id] = structuredClone(state.originalRecords[id])
        const records = state.taskProcessingRecords?.filter(record => record.sampleId === id) || []
        state.taskProcessingRecords?.push(...records.map(record => ({ ...structuredClone(record), id: crypto.randomUUID(), requestId: crypto.randomUUID(), sampleId: row.id, sampleCode: row.code })))
        audit(row, a, '复制样品', `来源：${source.code}；类型：${input.sampleType}；报告编号：${reportCode}`)
        state.samples.push(row)
        return row
      })
    },
    async reportQuerySamples(input: ReportQueryQuery = {}, all = false) {
      const a = actor('samples')
      if (!has(a, ['reports', 'reviewer', 'approver'])) fail('当前身份无权查询报告。', 'FORBIDDEN')
      const query = parseReportQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans), state = read()
      const rows = reportQueryRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, state, a)
      return { ...(all ? { items: rows, total: rows.length, page: 1, pageSize: rows.length } : page(rows, query, 'samples')), planSelection: selected.state }
    },
    async exportReportQuerySamples(input: ReportQueryQuery = {}) {
      const result = await this.reportQuerySamples(input, true)
      return registrationCsv([reportQueryColumns.map(column => column.label), ...result.items.map(row => reportQueryColumns.map(column => column.key === 'attachmentCount' ? row.attachmentCount > 0 ? '有' : '' : tableCellText(row[column.key], column)))])
    },
    async reportQueryFile(id: string, releaseId: string) {
      const a = actor('samples')
      if (!has(a, ['reports', 'reviewer', 'approver'])) fail('当前身份无权查询报告。', 'FORBIDDEN')
      const sample = find(read(), 'samples', id, a) as RegistrationSample, release = sample.reportRelease
      if (!release || release.id !== releaseId) fail('报告文件版本已更新，请刷新后预览。', 'BUSINESS_RULE')
      return release!.form === '电子' && release!.signing?.status === '签章完成' && release!.signed ? release!.signed : release!.original
    },
    async reportQueryVoid(id: string, version: number, reason: unknown) {
      const a = actor('samples')
      if (!Number.isSafeInteger(version) || version < 1 || typeof reason !== 'string') throw new AppError('BAD_REQUEST', '作废申请参数有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!canQueryVoid(a, sample)) fail('当前权限或状态不允许提交作废申请。', 'FORBIDDEN')
        requestSampleVoid(sample, a, reason)
        audit(sample, a, '提交作废申请', reason.trim())
        return sample
      })
    },
    async dataQuerySamples(input: DataQueryQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查询检测数据。', 'FORBIDDEN')
      const query = parseDataQueryQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans), state = read()
      const rows = dataQueryRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, state).map(row => ({ ...row, canView: true }))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportDataQuerySamples(input: DataQueryQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查询检测数据。', 'FORBIDDEN')
      const query = parseDataQueryQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans), state = read()
      const rows = dataQueryRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, state)
      return registrationCsv([dataQueryColumns.map(column => column.label), ...rows.map(row => dataQueryColumns.map(column => row[column.key]))])
    },
    async sampleCopySamples(input: SampleCopyQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看复制样品数据。', 'FORBIDDEN')
      const query = parseSampleCopyQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans), state = read()
      const rows = sampleCopyRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, state).map(row => ({ ...row, canCopy: has(a, ['testing']) && !['委托作废申请中', '委托已作废', '任务已取消', '终止'].includes(row.dataStatus) }))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportSampleCopySamples(input: SampleCopyQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看复制样品数据。', 'FORBIDDEN')
      const query = parseSampleCopyQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans), state = read()
      const rows = sampleCopyRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, state)
      return registrationCsv([sampleCopyColumns.map(column => column.label), ...rows.map(row => sampleCopyColumns.map(column => column.key === 'attachmentCount' ? row.attachmentCount > 0 ? '有' : '' : tableCellText(row[column.key], { money: 'money' in column && column.money })))])
    },
    async reportCheckSamples(input: ReportCheckQuery = {}, stage: ReportStage = 'check') {
      const config = reportStages[stage], a = actor('samples')
      if (!has(a, ['reports', 'reviewer', 'approver'])) fail(`当前身份无权查看${config.title}任务。`, 'FORBIDDEN')
      const query = parseReportCheckQuery(input as Record<string, unknown>, stage), selected = resolvePlanSelection(a, query.plans)
      const rows = reportCheckRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, a, stage)
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportReportCheckSamples(input: ReportCheckQuery = {}, stage: ReportStage = 'check') {
      const config = reportStages[stage], a = actor('samples')
      if (!has(a, ['reports', 'reviewer', 'approver'])) fail(`当前身份无权查看${config.title}任务。`, 'FORBIDDEN')
      const query = parseReportCheckQuery(input as Record<string, unknown>, stage), selected = resolvePlanSelection(a, query.plans)
      const rows = reportCheckRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query, undefined, stage)
      return registrationCsv([reportStageColumns(stage).map(column => column.label), ...rows.map(row => reportStageColumns(stage).map(column => column.key === 'attachmentCount' ? row.attachmentCount > 0 ? '有' : '' : tableCellText(row[column.key], {})))])
    },
    async reportCheckRecipients(id: string, input: Record<string, unknown>, resolve = false, stage: ReportStage = 'check') {
      const config = reportStages[stage], a = actor('samples'), sample = find(read(), 'samples', id, a) as RegistrationSample
      if (!has(a, (stage === 'approval' ? ['approver'] : ['reports', 'reviewer']))) fail(`当前身份无权执行${config.title}。`, 'FORBIDDEN')
      if (!reportCheckCapabilities(a, sample, stage).canCheck) fail(`样品状态已不允许此${config.title}操作，请刷新列表。`)
      return resolve ? resolveEntryPerson({ role: config.role, id: input.id }) : queryEntryPeople(sample, a, { ...input, role: config.role })
    },
    async reportBatchContext(ids: unknown, stage: ReportStage = 'check') {
      const a = actor('samples'), state = read()
      if (!Array.isArray(ids) || !ids.length || ids.length > 50 || ids.some(id => typeof id !== 'string') || new Set(ids).size !== ids.length) throw new AppError('BAD_REQUEST', '请选择 1 至 50 个不重复的样品。')
      const targets = ids.map(id => { const sample = find(state, 'samples', id, a); return { id, version: sample.version } })
      return reportBatch(state, targets, a, stage)
    },
    async reportBatchCheck(targets: unknown, stage: ReportStage = 'check') {
      const a = actor('samples'), samples = reportBatch(read(), targets, a, stage), scope = reportBatchScope(samples, stage)
      const validate = () => {
        const latestActor = actor('samples')
        if (latestActor.id !== a.id) fail('当前身份已变化，请重新校验。', 'FORBIDDEN')
        reportBatch(read(), targets, latestActor, stage)
      }
      const items = await Promise.all(samples.map(async sample => ({ ...await reviewChecks.run(a.id, sample, validate, reviewCheckOptions(sample.contractReview ?? emptyContractReview()), scope), sampleCode: sample.code, sampleName: sample.name })))
      validate()
      return { items }
    },
    async reportBatchSubmit(targets: unknown, action: unknown, confirmation: unknown, checks: unknown, rejection: unknown, stage: ReportStage = 'check') {
      const a = actor('samples')
      if (action !== 'check' && action !== 'reject') throw new AppError('BAD_REQUEST', '批量操作有误。')
      if (!Array.isArray(checks) || checks.length > 50 || checks.some(check => !check || typeof check.sampleId !== 'string' || typeof check.checkId !== 'string') || new Set(checks.map(check => check.sampleId)).size !== checks.length) throw new AppError('BAD_REQUEST', '核验结果格式有误。')
      const proof = confirmation && typeof confirmation === 'object' && !Array.isArray(confirmation) ? confirmation as Record<string, unknown> : {}
      const before = read(), batch = reportBatch(before, targets, a, stage)
      const releases = stage === 'approval' && action === 'check' && proof.nextAction === 'next'
        ? await Promise.all(batch.map(sample => prepareReportRelease(before, sample, a, lifecycleConfig))) : []
      if (actor('samples').id !== a.id) fail('当前身份已变化，请重新操作。', 'FORBIDDEN')
      return write(state => {
        const samples = reportBatch(state, targets, a, stage), scope = reportBatchScope(samples, stage)
        if (checks.some(check => !samples.some(sample => sample.id === check.sampleId))) throw new AppError('BAD_REQUEST', '核验结果与所选样品不一致。')
        samples.forEach((sample, index) => { if (releases[index]) commitReportRelease(state, sample, releases[index]!) })
        for (const sample of samples) applyReportAction(sample, a, action, stage, { ...proof, reviewCheckId: checks.find(check => check.sampleId === sample.id)?.checkId }, rejection, scope)
        return samples
      })
    },
    async reportComplianceCheck(id: string, version: number, stage: ReportStage = 'check') {
      const validate = () => {
        const config = reportStages[stage], a = actor('samples'), sample = find(read(), 'samples', id, a) as RegistrationSample
        if (!has(a, (stage === 'approval' ? ['approver'] : ['reports', 'reviewer']))) fail(`当前身份无权执行${config.title}。`, 'FORBIDDEN')
        if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
        
        if (!reportCheckCapabilities(a, sample, stage).canCheck) fail(`样品状态已不允许此${config.title}操作，请刷新列表。`)
        return { a, sample }
      }
      const { a, sample } = validate()
      return reviewChecks.run(a.id, sample, () => { const latest = validate(); if (latest.a.id !== a.id) fail('当前身份已变化，请重新校验。', 'FORBIDDEN') }, reviewCheckOptions(sample.contractReview ?? emptyContractReview()), stage === 'check' ? 'report' : 'report-' + stage)
    },
    async reportVoidAction(id: string, version: number, reason: unknown, stage: ReportStage) {
      const a = actor('samples')
      if (stage === 'check') throw new AppError('BAD_REQUEST', '报告校核不支持此作废申请入口。')
      if (!has(a, stage === 'approval' ? ['approver'] : ['reports', 'reviewer'])) fail('当前身份无权提交作废申请。', 'FORBIDDEN')
      if (!Number.isSafeInteger(version) || version < 1 || typeof reason !== 'string') throw new AppError('BAD_REQUEST', '作废申请参数有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!reportCheckCapabilities(a, sample, stage).canVoid) fail('样品当前状态不允许提交作废申请，请刷新列表。')
        requestSampleVoid(sample, a, reason)
        audit(sample, a, '提交作废申请', reason.trim())
        return sample
      })
    },
    async reportCheckAction(id: string, action: string, version: number, confirmation?: unknown, rejection?: unknown, stage: ReportStage = 'check') {
      const config = reportStages[stage], a = actor('samples')
      if (!has(a, (stage === 'approval' ? ['approver'] : ['reports', 'reviewer']))) fail(`当前身份无权执行${config.title}。`, 'FORBIDDEN')
      if (!['check', 'reject', 'undo'].includes(action)) throw new AppError('BAD_REQUEST', `不支持的${config.title}操作。`)
      if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      const before = read(), target = find(before, 'samples', id, a) as RegistrationSample
      
      const prepared = stage === 'approval' && action === 'check' && (confirmation as { nextAction?: string } | undefined)?.nextAction === 'next'
        ? await (reportCheckCapabilities(a, target, stage).canCheck ? prepareReportRelease(before, target, a, lifecycleConfig) : Promise.reject(new AppError('BUSINESS_RULE', '当前状态不允许批准。'))) : undefined
      if (actor('samples').id !== a.id) fail('当前身份已变化，请重新操作。', 'FORBIDDEN')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        const capabilities = reportCheckCapabilities(a, sample, stage)
        if (action === 'undo' ? !capabilities.canUndoCheck : !capabilities.canCheck) fail(`样品状态已不允许此${config.title}操作，请刷新列表。`)
        if (prepared) commitReportRelease(state, sample, prepared)
        applyReportAction(sample, a, action, stage, confirmation, rejection)
        return sample
      })
    },
    async dataCheckSamples(input: DataCheckQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测数据校核任务。', 'FORBIDDEN')
      const query = parseDataCheckQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans), state = read()
      const rows = dataCheckRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query).map(row => ({ ...row, ...dataCheckCapabilities(a, state.samples.find(sample => sample.id === row.id)!) }))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportDataCheckSamples(input: DataCheckQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测数据校核任务。', 'FORBIDDEN')
      const query = parseDataCheckQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = dataCheckRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query)
      return registrationCsv([dataCheckColumns.map(column => column.label), ...rows.map(row => dataCheckColumns.map(column => column.key === 'attachmentCount' ? row.attachmentCount > 0 ? '有' : '' : tableCellText(row[column.key], {})))])
    },
    async dataCheckAction(id: string, action: string, version: number) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer'])) fail('当前身份无权执行数据校核。', 'FORBIDDEN')
      if (!['check', 'reject', 'undo'].includes(action)) throw new AppError('BAD_REQUEST', '不支持的校核操作。')
      if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        const capabilities = dataCheckCapabilities(a, sample)
        if (action === 'undo' ? !capabilities.canUndoCheck : !capabilities.canCheck) fail('样品状态已不允许此校核操作，请刷新列表。')
        if (action === 'check') {
          sample.dataCheckInfo = { actorId: a.id, actorName: a.name, at: new Date().toISOString(), previousDataStatus: sample.dataStatus }
          sample.workflow = { ...sample.workflow, checkDate: serverDate() }
          sample.dataStatus = '检测数据校核完成'
        } else {
          sample.dataStatus = action === 'reject' ? '检测数据录入中' : sample.dataCheckInfo?.previousDataStatus === '检测数据录入完成' ? '检测数据录入完成' : '检测数据校核中'
          delete sample.dataCheckInfo
          if (sample.workflow) delete sample.workflow.checkDate
        }
        audit(sample, a, action === 'check' ? '数据校核' : action === 'reject' ? '数据校核不通过' : '撤销校核', action === 'reject' ? '退回检测数据录入' : '')
        return sample
      })
    },
    async dataEntrySamples(input: DataEntryQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测数据录入任务。', 'FORBIDDEN')
      const query = parseDataEntryQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const state = read()
      const rows = dataEntryRows(sampleRows(state, {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query).map(row => {
        const sample = state.samples.find(sample => sample.id === row.id)!
        return { ...row, canReturn: has(a, ['testing']), canVoid: workspaceActions(a, 'samples', sample).some(action => action.id === 'void' && !action.disabled), ...entryCapabilities(a, sample) }
      })
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportDataEntrySamples(input: DataEntryQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测数据录入任务。', 'FORBIDDEN')
      const query = parseDataEntryQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = dataEntryRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query)
      return registrationCsv([dataEntryColumns.map(column => column.label), ...rows.map(row => dataEntryColumns.map(column => column.key === 'attachmentCount' ? row.attachmentCount > 0 ? '有' : '' : tableCellText(row[column.key], {})))])
    },
    async taskQuerySamples(input: TaskQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测任务。', 'FORBIDDEN')
      const query = parseTaskQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = taskQueryRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query).map(row => ({ ...row, canReturn: has(a, ['testing']) }))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async taskQueryReturn(id: string, version: number, input: unknown) {
      const a = actor('samples')
      if (!has(a, ['testing'])) fail('当前身份无权退回检测任务。', 'FORBIDDEN')
      if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!taskReturnAllowed(sample)) fail('样品当前状态不允许退回，请刷新列表。')
        const returned = parseOutboundReturn(input)
        sample.taskReturns = [...(sample.taskReturns || []), { ...returned, recordedAt: new Date().toISOString(), recordedBy: { id: a.id, name: a.name }, previousDataStatus: sample.dataStatus }]
        sample.dataStatus = returned.type === 'commission' ? '委托登记中' : '完成登记'
        sample.status = returned.type === 'commission' ? 'pending' : 'completed'
        sample.reviewStatus = 'unreviewed'
        audit(sample, a, '退回检测任务', `${returned.type === 'commission' ? '委托信息错误' : '任务分配错误'}：${returned.reason}${returned.details ? `；${returned.details}` : ''}；退回时间：${returned.date}`)
        return sample
      })
    },
    async exportTaskQuerySamples(input: TaskQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测任务。', 'FORBIDDEN')
      const query = parseTaskQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = taskQueryRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query)
      return registrationCsv([taskQueryColumns.map(column => column.label), ...rows.map(row => taskQueryColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async pickupSamples(input: PickupQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测样品领取。', 'FORBIDDEN')
      const query = parsePickupQuery(input as Record<string, unknown>)
      const selected = resolvePlanSelection(a, query.plans)
      const rows = pickupRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query).map(row => ({ ...row, canPickup: has(a, ['testing']) && row.dataStatus === '样品待领取' }))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async pickupAction(id: string, version: number, input: unknown) {
      const a = actor('samples')
      if (!has(a, ['testing'])) fail('当前身份无权领取样品。', 'FORBIDDEN')
      if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!pickupAllowed(sample)) fail('样品状态已不允许领取，请刷新列表。')
        const receipt = parsePickupReceipt(input)
        sample.flowInfo = { ...sample.flowInfo, collection: { ...receipt, recordedAt: new Date().toISOString(), recordedBy: { id: a.id, name: a.name } } }
        sample.dataStatus = '样品已领取'
        audit(sample, a, '领取样品', `领样员：${receipt.name}（${receipt.account}）；领样时间：${receipt.date}`)
        return sample
      })
    },
    async exportPickupSamples(input: PickupQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测样品领取。', 'FORBIDDEN')
      const query = parsePickupQuery(input as Record<string, unknown>)
      const selected = resolvePlanSelection(a, query.plans)
      const rows = pickupRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query)
      return registrationCsv([pickupColumns.map(column => column.label), ...rows.map(row => pickupColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async assignmentSamples(input: AssignmentQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测任务。', 'FORBIDDEN')
      const query = parseAssignmentQuery(input as Record<string, unknown>)
      const selected = resolvePlanSelection(a, query.plans)
      const rows = assignmentRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query).map(row => ({ ...row, canAssign: has(a, ['testing']) && row.dataStatus === '任务分配中', canUndoAssign: has(a, ['testing']) && row.dataStatus === '任务分配完成' }))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async assignmentAction(id: string, version: number, input: unknown, action: 'assign' | 'undo' | 'auto' = 'assign') {
      const a = actor('samples')
      if (!has(a, ['testing'])) fail('当前身份无权分配检测任务。', 'FORBIDDEN')
      if (!['assign', 'undo', 'auto'].includes(action)) throw new AppError('BAD_REQUEST', '不支持的分配操作。')
      if (action === 'auto' && (!input || typeof input !== 'object' || Array.isArray(input) || Object.keys(input).some(key => !['action', 'version'].includes(key)))) throw new AppError('BAD_REQUEST', '自动分配请求格式已更新，请刷新页面后重试。')
      if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (action === 'undo') {
          if (!assignmentReversible(sample)) fail('样品状态已不允许撤销分配，请刷新列表。')
          sample.dataStatus = '任务分配中'
          audit(sample, a, '撤销分配')
          return sample
        }
        if (!assignmentPending(sample)) fail('样品状态已不允许分配，请刷新列表。')
        const fields = action === 'auto' ? autoAssignment.resolve(sample, a, serverDate()) : parseAssignmentSubmission(input)
        sample.assignmentInfo = { ...sample.assignmentInfo, ...fields, recordedBy: { id: a.id, name: a.name }, recordedAt: new Date().toISOString() }
        sample.dataStatus = '任务分配完成'
        audit(sample, a, action === 'auto' ? '自动分配' : '分配', `分配人：${fields.assignedBy}（${fields.assignedById}）；数据录入人：${fields.dataEntryPerson}；检测人1：${fields.tester1}；检测人2：${fields.tester2 || '无'}；分配日期：${fields.assignedDate}`)
        return sample
      })
    },
    async exportAssignmentSamples(input: AssignmentQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测任务。', 'FORBIDDEN')
      const query = parseAssignmentQuery(input as Record<string, unknown>)
      const selected = resolvePlanSelection(a, query.plans)
      const rows = assignmentRows(sampleRows(read(), {}).filter(row => !selected.restricted || selected.ids.has(row.details?.testPlanId || '')), query)
      return registrationCsv([assignmentColumns.map(column => column.label), ...rows.map(row => assignmentColumns.map(column => column.key === 'attachmentCount' ? (row.attachmentCount > 0 ? '有' : '') : tableCellText(row[column.key], {})))])
    },
    async flowSamples(query: FlowQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const rows = flowRows(sampleRows(read(), {}), query, selected.ids, selected.restricted)
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportFlowSamples(query: FlowQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const rows = flowRows(sampleRows(read(), {}), query, selected.ids, selected.restricted)
      return registrationCsv([flowColumns.map(column => column.label), ...rows.map(row => flowColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async sampleCompletionSamples(input: SampleCompletionQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检毕样品处理。', 'FORBIDDEN')
      const query = parseSampleCompletionQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = sampleCompletionRows(sampleRows(read(), {}), query, selected.ids, selected.restricted, has(a, ['testing']))
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportSampleCompletionSamples(input: SampleCompletionQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检毕样品处理。', 'FORBIDDEN')
      const query = parseSampleCompletionQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = sampleCompletionRows(sampleRows(read(), {}), query, selected.ids, selected.restricted, has(a, ['testing']))
      return registrationCsv([sampleCompletionColumns.map(column => column.label), ...rows.map(row => sampleCompletionColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async sampleCompletionAction(id: string, action: SampleCompletionAction, version: number, input?: unknown) {
      const a = actor('samples')
      if (!has(a, ['testing'])) fail('当前身份无权办理样品处理。', 'FORBIDDEN')
      if (!['process', 'undo'].includes(action)) throw new AppError('BAD_REQUEST', '不支持的样品处理操作。')
      if (!Number.isSafeInteger(version) || version < 1) throw new AppError('BAD_REQUEST', '记录版本有误。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        const info = sample.sampleCompletionInfo || { status: '样品待处理' }
        if (!isDisposalSample(sample) || info.status !== (action === 'process' ? '样品待处理' : '样品已处理')) fail('样品状态已不允许此操作，请刷新列表。')
        if (action === 'process') {
          const result = parseSampleCompletionResult(input), processedAt = new Date().toISOString()
          sample.sampleCompletionInfo = { ...info, status: '样品已处理', processedAt,
            receipt: { result, processedAt, processedBy: { id: a.id, name: a.name },
              customerRequirement: disposalRequirement(sample.details?.disposalMethod), retentionTime: sample.disposalInfo?.retentionTime || '' } }
          audit(sample, a, '样品处理', result)
        } else {
          sample.sampleCompletionInfo = { status: '样品待处理', history: [...(info.history || []), ...(info.receipt ? [info.receipt] : [])] }
          audit(sample, a, '撤销样品处理')
        }
        return sample
      })
    },
    async disposalSamples(query: DisposalQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const samples = sampleRows(read(), {}), source = new Map(samples.map(row => [row.id, row]))
      const rows = disposalRows(samples, query, selected.ids, selected.restricted).map(row => ({ ...row, disposalActions: registrationCanWrite(a, 'samples') ? allowedDisposalActions(source.get(row.id)!) : [] }))
      return { ...page(rows, query, 'samples'), sites: [], planSelection: selected.state }
    },
    async exportDisposalSamples(query: DisposalQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const rows = disposalRows(sampleRows(read(), {}), query, selected.ids, selected.restricted)
      return registrationCsv([disposalColumns.map(column => column.label), ...rows.map(row => disposalColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async inboundSamples(query: InboundQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans), samples = sampleRows(read(), {})
      const rows = inboundRows(samples, query, selected.ids, selected.restricted)
      const sites = [...new Set(inboundRows(samples, {}, new Set(), false).map(row => row.site).filter(Boolean))]
      return { ...page(rows, query, 'samples'), sites, planSelection: selected.state }
    },
    async exportInboundSamples(query: InboundQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const rows = inboundRows(sampleRows(read(), {}), query, selected.ids, selected.restricted)
      return registrationCsv([inboundColumns.map(column => column.label), ...rows.map(row => inboundColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async outboundSamples(query: InboundQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const rows = outboundRows(sampleRows(read(), {}), query, selected.ids, selected.restricted).map(row => ({ ...row, outboundActions: registrationCanWrite(a, 'samples') ? allowedOutboundActions(row) : [] }))
      return { ...page(rows, query, 'samples'), sites: [], planSelection: selected.state }
    },
    async exportOutboundSamples(query: InboundQuery = {}) {
      const a = actor('samples'), selected = resolvePlanSelection(a, query.plans)
      const rows = outboundRows(sampleRows(read(), {}), query, selected.ids, selected.restricted)
      return registrationCsv([inboundColumns.map(column => column.label), ...rows.map(row => inboundColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async disposalAction(id: string, action: DisposalAction, version: number, input?: unknown) {
      const a = actor('samples')
      if (!registrationCanWrite(a, 'samples')) fail('当前身份无权办理样品处置。', 'FORBIDDEN')
      if (!['dispose', 'undo'].includes(action)) throw new AppError('BAD_REQUEST', '不支持的处置操作。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!allowedDisposalActions(sample).includes(action)) fail('样品状态已不允许此操作，请刷新列表。')
        let reason = ''
        if (action === 'dispose') {
          const receipt = parseDisposalReceipt(input)
          sample.disposalInfo = { ...sample.disposalInfo, receipt: { ...receipt, customerRequirement: disposalRequirement(sample.details?.disposalMethod), recordedAt: new Date().toISOString(), recordedBy: { id: a.id, name: a.name } } }
          sample.dataStatus = '样品已处置'
          reason = `${receipt.result}；处置人：${receipt.name}；处置时间：${receipt.date}`
        } else {
          const info = sample.disposalInfo || {}
          sample.disposalInfo = { ...info, receipt: undefined, history: [...(info.history || []), ...(info.receipt ? [info.receipt] : [])] }
          sample.dataStatus = '样品待处置'
        }
        audit(sample, a, action === 'dispose' ? '样品处置' : '撤销处置', reason)
        return sample
      })
    },
    async inboundAction(id: string, action: InboundAction, version: number, receipt?: unknown) {
      const a = actor('samples')
      if (!registrationCanWrite(a, 'samples')) fail('当前身份无权办理样品入库。', 'FORBIDDEN')
      if (!['receive', 'undo'].includes(action)) throw new AppError('BAD_REQUEST', '不支持的入库操作。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        const expected = action === 'receive' ? '样品入库中' : '样品入库完成'
        if (!isInboundSample(sample) || inboundStatus(sample.dataStatus) !== expected) fail('样品状态已不允许此操作，请刷新列表。')
        if (action === 'receive') {
          const details = parseInboundReceipt(receipt)
          sample.inboundInfo = { site: '', groupNumber: '', ...sample.inboundInfo, receipt: { ...details, recordedAt: new Date().toISOString(), recordedBy: { id: a.id, name: a.name } } }
        }
        sample.dataStatus = action === 'receive' ? '样品入库完成' : '样品入库中'
        audit(sample, a, action === 'receive' ? '入库' : '撤销入库')
        return sample
      })
    },
    async outboundAction(id: string, action: OutboundAction, version: number, input?: unknown) {
      const a = actor('samples')
      if (!registrationCanWrite(a, 'samples')) fail('当前身份无权办理样品出库。', 'FORBIDDEN')
      if (!['dispatch', 'undo', 'return'].includes(action)) throw new AppError('BAD_REQUEST', '不支持的出库操作。')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!allowedOutboundActions(sample).includes(action)) fail('样品状态已不允许此操作，请刷新列表。')
        const recordedAt = new Date().toISOString(), recordedBy = { id: a.id, name: a.name }
        let reason = ''
        if (action === 'dispatch') {
          const receipt = parseStockReceipt(input, '出库')
          sample.outboundInfo = { ...sample.outboundInfo, receipt: { ...receipt, recordedAt, recordedBy } }
          sample.dataStatus = '样品待领取'
        } else if (action === 'undo') sample.dataStatus = '样品出库中'
        else {
          const returned = parseOutboundReturn(input)
          sample.outboundInfo = { ...sample.outboundInfo, returns: [...(sample.outboundInfo?.returns || []), { ...returned, recordedAt, recordedBy, previousDataStatus: sample.dataStatus }] }
          // “委托登记完成” is represented by the existing “完成登记” workflow value.
          sample.dataStatus = returned.type === 'commission' ? '委托登记中' : '完成登记'
          sample.status = returned.type === 'commission' ? 'pending' : 'completed'
          sample.reviewStatus = 'unreviewed'
          reason = `${returned.type === 'commission' ? '委托信息错误' : '任务分配错误'}：${returned.reason}${returned.details ? `；${returned.details}` : ''}`
        }
        audit(sample, a, action === 'dispatch' ? '出库' : action === 'undo' ? '撤销出库' : '退回委托', reason)
        return sample
      })
    },
    async cancellationApprovals(query: CancellationQuery = {}) {
      return page(cancellationRows(sampleRows(read(), {}), query), query, 'samples')
    },
    async exportCancellationApprovals(query: CancellationQuery = {}) {
      const rows = cancellationRows(sampleRows(read(), {}), query)
      return registrationCsv([cancellationColumns.map(column => column.label), ...rows.map(row => cancellationColumns.map(column => tableCellText(row[column.key], {})))])
    },
    async approveCancellation(id: string, input: unknown) {
      const a = actor('samples')
      if (!canApproveCancellation(a)) fail('当前身份无权审批作废申请。', 'FORBIDDEN')
      if (!input || typeof input !== 'object' || Array.isArray(input)) fail('审批数据格式有误。', 'VALIDATION')
      const submission = parseCancellationSubmission(input as Record<string, unknown>)
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        const application = sample.voidApplication
        if (sample.status !== 'void_pending' || !application || application.decision) fail('此作废申请已处理或已不在待审批状态，请刷新列表。')
        if (submission.decision === 'rejected' && (!['pending', 'completed'].includes(application.previousStatus) || !application.previousDataStatus)) fail('申请前的样品状态缺失，无法恢复。')
        if (submission.decision === 'approved') { sample.status = 'voided'; sample.dataStatus = '委托已作废' }
        else { sample.status = application.previousStatus; sample.dataStatus = application.previousDataStatus; sample.reviewStatus = application.previousReviewStatus }
        application.decision = submission.decision
        application.approvedAt = new Date().toISOString(); application.approvedBy = { id: a.id, name: a.name }
        application.rejectionReason = submission.decision === 'rejected' ? submission.reason : ''
        audit(sample, a, submission.decision === 'approved' ? '作废审批通过' : '作废审批不通过', application.rejectionReason)
        return sample
      })
    },
    async dataChanges(input: DataChangeQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测数据更改。', 'FORBIDDEN')
      const query = parseDataChangeQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = dataChangeRows(sampleRows(read(), {}).filter(row => isDataChangeSample(row) && (!selected.restricted || selected.ids.has(row.details?.testPlanId || ''))), query)
      return { ...page(rows, query, 'samples'), planSelection: selected.state }
    },
    async exportDataChanges(input: DataChangeQuery = {}) {
      const a = actor('samples')
      if (!has(a, ['testing', 'reviewer', 'approver'])) fail('当前身份无权查看检测数据更改。', 'FORBIDDEN')
      const query = parseDataChangeQuery(input as Record<string, unknown>), selected = resolvePlanSelection(a, query.plans)
      const rows = dataChangeRows(sampleRows(read(), {}).filter(row => isDataChangeSample(row) && (!selected.restricted || selected.ids.has(row.details?.testPlanId || ''))), query)
      return registrationCsv([commissionChangeColumns.map(column => column.label), ...rows.map(row => commissionChangeColumns.map(column => column.key === 'attachmentCount' ? sampleCell(row, column.key) : tableCellText(row[column.key], {})))])
    },
    async completeDataChange(id: string, version: number, acknowledgeMissingOriginals = false) {
      const a = actor('samples')
      return write(state => {
        const sample = find(state, 'samples', id, a) as RegistrationSample
        
        if (!canChangeData(a, sample)) fail('当前身份或样品状态不允许完成检测数据更改。', 'FORBIDDEN')
        const missingOriginals = validateEntryCompletion(state, sample, a, acknowledgeMissingOriginals === true)
        sample.status = 'completed'; sample.dataStatus = '检测数据录入完成'
        if (sample.dataChange) Object.assign(sample.dataChange, { result: '问题已处理', completedAt: new Date().toISOString(), completedBy: { id: a.id, name: a.name } })
        completeReportIssue(sample, sample.dataChange?.reportIssueId, a)
        sample.dataCheckInfo = undefined
        supersedeReportRelease(sample, a, '完成检测数据更改')
        sample.reportCheckInfo = undefined; sample.reportReviewInfo = undefined; sample.reportApprovalInfo = undefined
        if (sample.workflow) { sample.workflow.checkDate = undefined; sample.workflow.auditDate = undefined; sample.workflow.approvalDate = undefined }
        audit(sample, a, '完成检测数据更改', missingOriginals ? '已确认无原始记录，继续完成更改' : '')
        return sample
      })
    },
    async sampleChanges(query: CommissionChangeQuery = {}) {
      return page(changeRows(sampleRows(read(), {}, 'changes'), query), query, 'samples')
    },
    async exportSampleChanges(query: CommissionChangeQuery = {}) {
      const rows = changeRows(sampleRows(read(), {}, 'changes'), query)
      return registrationCsv([commissionChangeColumns.map(column => column.label), ...rows.map(row => commissionChangeColumns.map(column => column.key === 'attachmentCount' ? sampleCell(row, column.key) : tableCellText(row[column.key], {})))])
    },
    async commissions(query: RegistrationQuery = {}) { return page(matching(read(), 'commissions', query) as RegistrationCommission[], query, 'commissions') },
    async samples(query: RegistrationQuery = {}, workspace: RegistrationWorkspace = 'registration') { return page(sampleRows(read(), query, workspace), query, 'samples') },
    async commission(id: string) { return structuredClone(find(read(), 'commissions', id, actor('commissions'))) as RegistrationCommission },
    async sample(id: string) { const state = read(); find(state, 'samples', id, actor('samples')); return sampleRows(state, { ids: [id] })[0]! },
    async bulkCommissionContext(ids: string[], workspace: RegistrationWorkspace = 'registration'): Promise<BulkCommissionContext> {
      const state = read(), a = actor('samples'), rows = bulkRows(state, ids, a, workspace)
      const order = find(state, 'commissions', rows[0]!.commissionId, a)
      return { commissionId: order.id, commissionCode: order.code, items: rows.map(row => ({ id: row.id, code: row.code, version: row.version, commissionInfo: structuredClone(row.commissionInfo) })) }
    },
    async bulkCommissionSource(ids: string[], workspace: RegistrationWorkspace = 'registration') {
      const state = read(), a = actor('samples'), rows = bulkRows(state, ids, a, workspace)
      return copySampleCommission(find(state, 'commissions', rows[0]!.commissionId, a) as RegistrationCommission)
    },
    async saveBulkCommission(targets: BulkCommissionTarget[], changes: Record<string, unknown>, workspace: RegistrationWorkspace = 'registration') {
      const a = actor('samples')
      if (!Array.isArray(targets) || targets.some(target => !target || typeof target !== 'object')) fail('样品版本参数有误。', 'VALIDATION')
      if (!changes || typeof changes !== 'object' || Array.isArray(changes)) fail('批量修改字段格式有误。', 'VALIDATION')
      const keys = Object.keys(changes)
      if (!keys.length || keys.some(key => !bulkCommissionKeys.includes(key as typeof bulkCommissionKeys[number]))) fail('请选择允许修改的委托信息字段。', 'VALIDATION')
      for (const key of keys) {
        const spec = bulkCommissionFields.find(field => (field.key === 'contract' ? 'contractId' : field.key) === key)!
        if (typeof changes[key] !== 'string' || (changes[key] as string).length > (spec.max || 500)) fail(`${spec.label}格式或长度有误。`, 'VALIDATION')
      }
      return write(state => {
        const rows = bulkRows(state, targets.map(target => target.id), a, workspace)
        
        let contract: typeof registrationContracts[number] | undefined
        if ('contractId' in changes && changes.contractId) {
          contract = registrationContracts.find(c => c.id === changes.contractId && (a.scope === 'all' || c.departmentId === a.departmentId))
          if (!contract) fail('合同不存在或已不可访问。', 'NOT_FOUND')
        }
        if ('handlingDepartmentId' in changes && changes.handlingDepartmentId && (!registrationDepartments.some(d => d.id === changes.handlingDepartmentId) || a.scope !== 'all' && changes.handlingDepartmentId !== a.departmentId)) fail('无权选择此经办部门。', 'FORBIDDEN')
        if ('invoiceType' in changes && changes.invoiceType && !registrationInvoiceTypes.some(type => type === changes.invoiceType)) fail('请选择有效的发票类型。', 'VALIDATION')
        for (const row of rows) {
          const before = structuredClone(row.commissionInfo)
          const info = structuredClone(row.commissionInfo)
          for (const key of keys) (info as unknown as Record<string, unknown>)[key] = (changes[key] as string).trim()
          if ('contractId' in changes) Object.assign(info, { contractId: contract?.id || '', contract: contract?.code || '', erpContract: contract?.erpContract || '', erpProjectType: contract?.erpProjectType || '' })
          row.commissionInfo = info
          row.customer = info.customer; row.contact = info.contact; row.phone = info.phone
          audit(row, a, '批量修改委托信息', bulkCommissionFields.filter(field => keys.includes(field.key === 'contract' ? 'contractId' : field.key)).map(field => field.label).join('、'))
          row.events.at(-1)!.changes = fieldChanges({ commissionInfo: before }, { commissionInfo: info })
        }
        return { count: rows.length, items: rows.map(row => ({ id: row.id, version: row.version })) }
      })
    },
    async taskPrintSource(id: string): Promise<TaskPrintSource> {
      const a = actor('samples'), state = read()
      if (!has(a, ['testing', 'reviewer', 'approver']) && !(has(a, ['reports']) && isReportArchiveSample(find(state, 'samples', id, a) as RegistrationSample))) fail('当前身份无权查看检测任务。', 'FORBIDDEN')
      const sample = find(state, 'samples', id, a) as RegistrationSample
      if (['voided', 'void_pending'].includes(sample.status)) fail('样品已作废或正在申请作废，无法获取任务单。')
      const info = assignmentPrintable(sample) && !assignmentPending(sample) ? sample.assignmentInfo : undefined, commission = state.commissions.find(row => row.id === sample.commissionId)
      return { id: sample.id, code: sample.code, name: sample.name, testPlan: sample.details?.testPlan || '', version: sample.version, canPrint: assignmentPrintable(sample) || isReportArchiveSample(sample), submittedBy: { id: a.id, name: a.name },
        snapshot: { commissionCode: commission?.code || '', parameters: [...sample.projects], customer: sample.customer, commissionDate: sample.commissionInfo.commissionDate || '', projectAddress: sample.commissionInfo.projectAddress || '',
          assignedById: info?.assignedById || '', assignedBy: info?.assignedBy || '', dataEntryPerson: info?.dataEntryPerson || '', tester1: info?.tester1 || '', tester2: info?.tester2 || '', assignedDate: info?.assignedDate || '' } }
    },
    async printSource(kind: RegistrationKind, id: string) {
      const state = read(), a = actor(kind), record = find(state, kind, id, a)
      if (kind === 'samples' && sampleReadOnlyReason(record.status)) fail(`${sampleReadOnlyReason(record.status)}，无法打印。`)
      return { kind, id, code: record.code, name: record.name,
        canPrint: kind === 'samples' || state.samples.some(sample => sample.commissionId === id),
        preview: { customer: record.customer, contact: record.contact, phone: record.phone, projects: [...record.projects] } }
    },
    async saveCommission(input: RegistrationCommissionInput, id?: string, version?: number, workspace: RegistrationWorkspace = 'registration') {
      if (workspace === 'changes') fail('委托更改仅支持修改待更改的样品单。')
      if (workspace === 'query') fail('委托查询不支持修改资料。')
      if (!id && workspace === 'review') fail('合同评审不支持新增委托。')
      const a = actor('commissions'); if (!registrationCanWrite(a, 'commissions')) fail('当前身份无权登记委托。', 'FORBIDDEN')
      return write(state => {
        if (input.name.length > 150 || input.requirements.length > 2000 || input.customer.length > 500 || input.projects.some(p => !demoProjects.includes(p))) fail('请检查委托名称、单位及检测要求。', 'VALIDATION')
        if (input.dueDate && !validDate(input.dueDate)) fail('请填写有效的要求完成日期。', 'VALIDATION')
        if (!['客户送样', '现场采样'].includes(input.source) || !['预付', '信用'].includes(input.settlement) || [input.discount, input.taxRate].some(n => !Number.isFinite(n) || n < 0 || n > 100)) fail('请检查样品来源、结算条件、折扣和税率。', 'VALIDATION')
        for (const key of commissionDetailKeys) if (input[key] !== undefined && (typeof input[key] !== 'string' || input[key]!.length > 500)) fail('请检查委托资料字段格式。', 'VALIDATION')
        if (input.commissionDate && !validDate(input.commissionDate)) fail('请填写有效的委托日期。', 'VALIDATION')
        if (input.invoiceType && !registrationInvoiceTypes.some(type => type === input.invoiceType)) fail('请选择有效的发票类型。', 'VALIDATION')
        const department = input.handlingDepartmentId || a.departmentId
        if (!registrationDepartments.some(d => d.id === department) || a.scope !== 'all' && department !== a.departmentId) fail('无权选择此经办部门。', 'FORBIDDEN')
        // Explicitly copy editable fields; identifiers, scope and audit metadata remain server-owned.
        const values: RegistrationCommissionInput = {
          name: input.name.trim(), customer: input.customer.trim(), contract: input.contract, dueDate: input.dueDate,
          requirements: input.requirements, contact: input.contact, phone: input.phone, projects: [...input.projects],
          notes: input.notes, source: input.source, settlement: input.settlement, discount: input.discount, taxRate: input.taxRate,
        }
        for (const key of commissionDetailKeys) if (key !== 'commissionDate' && input[key] !== undefined) values[key] = input[key]!.trim()
        values.handlingDepartmentId = department
        if (values.contractId) {
          const contract = registrationContracts.find(c => c.id === values.contractId && (a.scope === 'all' || c.departmentId === a.departmentId))
          if (!contract) fail('合同不存在或已不可访问。', 'NOT_FOUND')
          values.contract = contract.code; values.erpContract = contract.erpContract; values.erpProjectType = contract.erpProjectType
        } else {
          values.erpContract = ''; values.erpProjectType = ''
        }
        let row: RegistrationCommission
        if (id) { row = find(state, 'commissions', id, a) as RegistrationCommission;  if (!registrationCanEdit(a, 'commissions', row.status)) fail('当前委托状态不可修改。'); Object.assign(row, values) }
        else { row = { ...values, commissionDate: serverDate(), ...base(state, 'commissions', a), status: '未完成', completedReports: 0, openTasks: 0, attachments: [] }; state.commissions.push(row) }
        row.name = input.name.trim(); audit(row, a, id ? '修改委托' : '新增委托'); return row
      })
    },
    async testBases(query: TestBasisQuery) { return queryTestBases(actor('samples'), query) },
    async resolveTestBases(planId: string, ids: string[], englishBookMarks = false, separators?: unknown) { return resolveTestBases(actor('samples'), planId, ids, englishBookMarks, separators) },
    async testPlans(query: TestPlanQuery = {}) {
      const a = actor('samples'), keyword = query.keyword?.trim().toLocaleLowerCase()
      const accessible = (row: { departmentId: string }) => a.scope === 'all' || row.departmentId === a.departmentId
      if (query.parentId && !testPlanGroups.some(group => group.id === query.parentId && accessible(group))) fail('检测方案分组不存在或已不可访问。', 'NOT_FOUND')
      const availablePlans = testPlans.filter(accessible)
      const parents = new Map(availablePlans.map(row => [row.id, row.parentId]))
      const reportQueryCounts = new Map<string, number>(), reportArchiveCounts = new Map<string, number>(), reportDistributionCounts = new Map<string, number>(), reportSigningCounts = new Map<string, number>(), reportPrintCounts = new Map<string, number>(), reportReviewCounts = new Map<string, number>(), reportApprovalCounts = new Map<string, number>(), reportCheckCounts = new Map<string, number>(), counts = new Map<string, number>(), outboundCounts = new Map<string, number>(), disposalCounts = new Map<string, number>(), flowCounts = new Map<string, number>(), assignmentCounts = new Map<string, number>(), pickupCounts = new Map<string, number>(), taskQueryCounts = new Map<string, number>(), dataEntryCounts = new Map<string, number>(), dataCheckCounts = new Map<string, number>(), sampleCopyCounts = new Map<string, number>(), dataChangeCounts = new Map<string, number>()
      for (const sample of sampleRows(read(), {})) {
        const id = sample.details?.testPlanId, parentId = id && parents.get(id)
        if (!id || !parentId) continue
        const targets = [reportQueryCounts, isReportArchiveSample(sample) ? reportArchiveCounts : undefined, isReportDistributionSample(sample) ? reportDistributionCounts : undefined, isReportSigningSample(sample) ? reportSigningCounts : undefined, isReportPrintSample(sample) ? reportPrintCounts : undefined, isReportCheckSample(sample, 'review') ? reportReviewCounts : undefined, isReportCheckSample(sample, 'approval') ? reportApprovalCounts : undefined, isReportCheckSample(sample) ? reportCheckCounts : undefined, isDataChangeSample(sample) ? dataChangeCounts : undefined, isInboundSample(sample) ? counts : undefined, isOutboundSample(sample) ? outboundCounts : undefined, isDisposalSample(sample) ? disposalCounts : undefined, isFlowSample(sample) ? flowCounts : undefined, isAssignmentSample(sample) ? assignmentCounts : undefined, isPickupSample(sample) ? pickupCounts : undefined, isTaskQuerySample(sample) ? taskQueryCounts : undefined, isDataEntrySample(sample) ? dataEntryCounts : undefined, isDataCheckSample(sample) ? dataCheckCounts : undefined, isSampleCopySample(sample) ? sampleCopyCounts : undefined]
        for (const target of targets) if (target) {
          target.set(id, (target.get(id) || 0) + 1)
          target.set(parentId, (target.get(parentId) || 0) + 1)
        }
      }
      const nodes = query.parentId || keyword
        ? availablePlans.filter(row => (!query.parentId || row.parentId === query.parentId) && (!keyword || `${row.name} ${row.code}`.toLocaleLowerCase().includes(keyword)))
        : testPlanGroups.filter(accessible)
      return page(nodes.map(row => ({ ...publicTestPlan(row), reportQuerySampleCount: reportQueryCounts.get(row.id) || 0, reportArchiveSampleCount: reportArchiveCounts.get(row.id) || 0, reportDistributionSampleCount: reportDistributionCounts.get(row.id) || 0, reportSigningSampleCount: reportSigningCounts.get(row.id) || 0, reportPrintSampleCount: reportPrintCounts.get(row.id) || 0, reportCheckSampleCount: reportCheckCounts.get(row.id) || 0, reportReviewSampleCount: reportReviewCounts.get(row.id) || 0, reportApprovalSampleCount: reportApprovalCounts.get(row.id) || 0, inboundSampleCount: counts.get(row.id) || 0, outboundSampleCount: outboundCounts.get(row.id) || 0, disposalSampleCount: disposalCounts.get(row.id) || 0, flowSampleCount: flowCounts.get(row.id) || 0, assignmentSampleCount: assignmentCounts.get(row.id) || 0, pickupSampleCount: pickupCounts.get(row.id) || 0, taskQuerySampleCount: taskQueryCounts.get(row.id) || 0, dataEntrySampleCount: dataEntryCounts.get(row.id) || 0, dataCheckSampleCount: dataCheckCounts.get(row.id) || 0, sampleCopySampleCount: sampleCopyCounts.get(row.id) || 0, dataChangeSampleCount: dataChangeCounts.get(row.id) || 0 })), { ...query, pageSize: query.pageSize ?? 10 }, 'samples')
    },
    async reportSettingsConfig() { actor('samples'); return getSampleReportConfig() },
    async sampleDefaults() {
      const a = actor('samples')
      // Form option metadata is also needed when viewing a sample read-only.
      return sampleFormOptions(registrationDepartments.filter(d => a.scope === 'all' || d.id === a.departmentId).map(d => d.name))
    },
    async saveSample(input: RegistrationSampleInput, id?: string, version?: number, reportConfigVersion?: string, workspace: RegistrationWorkspace = 'registration') {
      if (workspace === 'query') fail('委托查询不支持修改资料。')
      if (!id && workspace === 'review') fail('合同评审不支持新增样品。')
      if (!id && workspace === 'changes') fail('委托更改不支持新增样品。')
      const a = actor('samples'); if (!registrationCanWrite(a, 'samples')) fail('当前身份无权登记样品。', 'FORBIDDEN')
      return write(state => {
        const details = parseSampleDetails(input.details)
        validateReportSettings(details.reportSettings, reportConfigVersion)
        const existing = id ? find(state, 'samples', id, a) as RegistrationSample : undefined
        if (existing && hasApprovedReport(existing) && existing.dataStatus !== '委托更改中') fail('已批准报告不能直接修改，请先通过报告更改流程处理。')
        if (existing) {  if (sampleReadOnlyReason(existing.status)) fail(`${sampleReadOnlyReason(existing.status)}，不可修改。`); if (!workspaceCanEdit(a, 'samples', existing, workspace)) fail(workspace === 'review' ? '已评审或已作废样品不可修改，请先撤销评审。' : '已完成或已作废样品不可修改。'); if (input.commissionId !== existing.commissionId) fail('修改样品时不能更改所属委托。') }
        if (existing && details.testPlanId !== (existing.details?.testPlanId || '')) throw new AppError('VALIDATION', '已有样品的检测方案不可修改。', { fieldErrors: { testPlanId: '检测方案不可修改。' } })
        if (existing) {
          details.testPlan = existing.details?.testPlan || ''
          details.testPlanCode = existing.details?.testPlanCode || ''
        } else if (details.testPlanId) {
          const plan = testPlans.find(row => row.id === details.testPlanId && (a.scope === 'all' || row.departmentId === a.departmentId))
          if (!plan) fail('检测方案不存在或已不可访问。', 'NOT_FOUND')
          details.testPlan = plan.name
          details.testPlanCode = plan.code
        } else { details.testPlan = ''; details.testPlanCode = '' }
        if (details.testBasisIds.length) details.testBasis = resolveTestBases(a, details.testPlanId, details.testBasisIds, details.englishBookMarks, details.testBasisSeparators).text
        else details.testBasis = ''
        details.assessmentStandard = details.useAssessmentStandard && details.assessmentStandardIds.length
          ? resolveTestBases(a, details.testPlanId, details.assessmentStandardIds, details.assessmentEnglishBookMarks, details.assessmentStandardSeparators).text : ''
        if (!input.commissionId) fail('请选择样品所属委托单。', 'VALIDATION')
        if (!demoCategories.includes(input.category) || !Number.isFinite(input.quantity) || input.quantity <= 0 || !['份', '瓶', '袋', '块', '支'].includes(input.unit)) fail('请检查样品类别、数量和单位。', 'VALIDATION')
        let commissionInfo = existing?.commissionInfo
        if (input.commissionId) {
          if (!existing && !registrationCanLink(a)) fail('当前身份没有关联委托的权限。', 'FORBIDDEN')
          const order = find(state, 'commissions', input.commissionId, a) as RegistrationCommission
          if (!existing && order.status !== '未完成') fail('只能关联未完成的委托。')
          if (!existing && order.projects.length > 0 && input.projects.some(p => !order.projects.includes(p))) fail('检测项目须与委托范围一致。')
          const source = existing?.commissionInfo ?? copySampleCommission(order)
          commissionInfo = input.commissionInfo ? parseSampleCommission(input.commissionInfo) : { ...source, customer: input.customer, contact: input.contact, phone: input.phone }
          // Source identifiers are immutable; all editable values belong to this sample.
          commissionInfo.code = source.code; commissionInfo.owner = source.owner; commissionInfo.commissionDate = source.commissionDate
          const department = commissionInfo.handlingDepartmentId
          if (department && (!registrationDepartments.some(d => d.id === department) || a.scope !== 'all' && department !== a.departmentId)) fail('无权选择此经办部门。', 'FORBIDDEN')
          if (commissionInfo.invoiceType && !registrationInvoiceTypes.some(type => type === commissionInfo!.invoiceType)) fail('请选择有效的发票类型。', 'VALIDATION')
          if (commissionInfo.contractId && commissionInfo.contractId !== source.contractId) {
            const contract = registrationContracts.find(c => c.id === commissionInfo!.contractId && (a.scope === 'all' || c.departmentId === a.departmentId))
            if (!contract) fail('合同不存在或已不可访问。', 'NOT_FOUND')
            commissionInfo.contract = contract.code; commissionInfo.erpContract = contract.erpContract; commissionInfo.erpProjectType = contract.erpProjectType
          }
        }
        if (!commissionInfo) fail('请选择样品所属委托单。', 'VALIDATION')
        if (!existing && !details.testPlanId) throw new AppError('VALIDATION', '请选择检测方案。', { fieldErrors: { testPlanId: '检测方案为必填项目。' } })
        // Last submission replaces editable fields, never server-owned history or attachments.
        const values: RegistrationSampleInput = {
          name: input.name, commissionId: input.commissionId, category: input.category,
          quantity: input.quantity, unit: input.unit, storage: input.storage,
          projects: [...input.projects], notes: input.notes,
          customer: commissionInfo.customer, contact: commissionInfo.contact, phone: commissionInfo.phone,
        }
        checkInput(values)
        const row = existing ?? { ...structuredClone(values), commissionInfo, ...base(state, 'samples', a), reportCode: '', sampleType: '原始样品', dataStatus: '委托登记中', attachments: [], status: 'pending' as const }
        // Mock numbering is assigned once by the service; clients cannot replace it.
        const reportCode = existing ? existing.reportCode : `BG${row.code.slice(2)}`
        const before = existing ? structuredClone({ name: existing.name, category: existing.category, quantity: existing.quantity, unit: existing.unit, storage: existing.storage, notes: existing.notes, projects: existing.projects, commissionInfo: existing.commissionInfo, details: existing.details }) : undefined
        Object.assign(row, structuredClone(values), { name: input.name.trim(), details, commissionInfo, reportCode, reviewStatus: existing?.reviewStatus ?? 'unreviewed' })
        if (!existing) state.samples.push(row)
        audit(row, a, existing ? '修改样品' : '登记样品', input.commissionId ? '已关联委托' : '独立登记')
        if (before) row.events.at(-1)!.changes = fieldChanges(before, { name: row.name, category: row.category, quantity: row.quantity, unit: row.unit, storage: row.storage, notes: row.notes, projects: row.projects, commissionInfo: row.commissionInfo, details: row.details })
        return row
      })
    },
    async batchReviewContext(ids: unknown) {
      const a = actor('samples'), state = read()
      if (!Array.isArray(ids) || !ids.length || ids.length > 50 || ids.some(id => typeof id !== 'string') || new Set(ids).size !== ids.length) throw new AppError('BAD_REQUEST', '样品选择有误。')
      const targets = ids.map(id => { const sample = find(state, 'samples', id, a); return { id, version: sample.version } })
      return reviewBatch(state, targets, a, true)
    },
    async startBatchReview(targets: unknown) {
      const a = actor('samples')
      return write(state => {
        const samples = reviewBatch(state, targets, a)
        for (const sample of samples) if (sample.reviewStatus !== 'reviewed') {
          sample.reviewStatus = 'reviewed'; sample.dataStatus = '合同评审中'; audit(sample, a, '开始合同评审')
        }
        return samples
      })
    },
    async batchReviewCheck(targets: unknown, options: unknown) {
      const a = actor('samples'), samples = reviewBatch(read(), targets, a, true), parsed = parseReviewCheckOptions(options)
      const validate = () => {
        const latestActor = actor('samples')
        if (latestActor.id !== a.id) fail('当前身份已变化，请重新校验。', 'FORBIDDEN')
        reviewBatch(read(), targets, latestActor, true)
      }
      const scope = batchReviewScope(samples)
      const items = await Promise.all(samples.map(async sample => ({ ...await reviewChecks.run(a.id, sample, validate, parsed, scope), sampleCode: sample.code, sampleName: sample.name })))
      validate()
      return { items }
    },
    async submitBatchReview(targets: unknown, review: unknown, checks: unknown) {
      const a = actor('samples')
      if (!review || typeof review !== 'object' || Array.isArray(review)) throw new AppError('BAD_REQUEST', '评审信息格式有误。')
      if (!Array.isArray(checks) || checks.some(check => !check || typeof check.sampleId !== 'string' || typeof check.checkId !== 'string') || new Set(checks.map(check => check.sampleId)).size !== checks.length) throw new AppError('BAD_REQUEST', '核验结果格式有误。')
      return write(state => {
        const samples = reviewBatch(state, targets, a, true), scope = batchReviewScope(samples)
        if (checks.some(check => !samples.some(sample => sample.id === check.sampleId))) throw new AppError('BAD_REQUEST', '核验结果与所选样品不一致。')
        for (const sample of samples) {
          applyContractReview(sample, a, { ...review, checkId: checks.find(check => check.sampleId === sample.id)?.checkId }, scope)
          audit(sample, a, sample.reviewStatus === 'approved' ? '评审通过' : '评审不通过', '批量快速评审')
        }
        return samples
      })
    },
    async reviewCheck(id: string, version: number, options: unknown) {
      const validate = () => {
        const a = actor('samples'), sample = find(read(), 'samples', id, a) as RegistrationSample
        if (!registrationCanWrite(a, 'samples')) fail('当前身份无权进行合规校核。', 'FORBIDDEN')
        
        if (sample.status !== 'completed' || sample.reviewStatus !== 'reviewed') fail('请先开始评审再进行合规校核。')
        return { a, sample }
      }
      const { a, sample } = validate()
      return reviewChecks.run(a.id, sample, () => { validate() }, parseReviewCheckOptions(options))
    },
    async act(kind: RegistrationKind, id: string, actionId: string, version: number, reason = '', review?: unknown) {
      const a = actor(kind)
      return write(state => {
        const row = find(state, kind, id, a); 
        if (kind === 'samples' && hasApprovedReport(row as RegistrationSample) && !['void', 'complete-change'].includes(actionId)) fail('已批准报告不能撤销之前的流程，请通过报告更改处理。')
        if (kind === 'samples' && sampleReadOnlyReason(row.status)) fail(`${sampleReadOnlyReason(row.status)}，不允许此操作。`)
        if (kind === 'samples' && ['start-review', 'review', 'unreview'].includes(actionId) && row.status !== 'completed') fail('当前样品不在合同评审范围内。')
        const action = workspaceActions(a, kind, row, actionId === 'complete-change' ? 'changes' : ['start-review', 'review', 'unreview'].includes(actionId) ? 'review' : 'registration').find(x => x.id === (actionId === 'start-review' ? 'review' : actionId) && !x.disabled)
        if (!action) fail('当前身份或记录状态不允许此操作。')
        if (action.reason) field(reason, kind === 'samples' && actionId === 'void' ? '申请作废原因' : '操作原因', 500)
        if (kind === 'samples' && ['start-review', 'review', 'unreview'].includes(actionId)) {
          const sample = row as RegistrationSample
          if (actionId === 'start-review') {
            if (sample.reviewStatus === 'reviewed') return row
            sample.reviewStatus = 'reviewed'; sample.dataStatus = '合同评审中'
          } else if (actionId === 'review') {
            if (sample.reviewStatus !== 'reviewed') fail('请先进入评审样品页面开始评审。')
            applyContractReview(sample, a, review)
          } else {
            sample.reviewStatus = 'unreviewed'; sample.dataStatus = '完成登记'
          }
        } else if (actionId === 'complete-change') {
          const sample = row as RegistrationSample
          sample.status = 'completed'; sample.dataStatus = '完成登记'; sample.reviewStatus = 'unreviewed'
          if (sample.commissionChange) Object.assign(sample.commissionChange, { result: '问题已处理', completedAt: new Date().toISOString(), completedBy: { id: a.id, name: a.name } })
          completeReportIssue(sample, sample.commissionChange?.reportIssueId, a)
          supersedeReportRelease(sample, a, '完成委托更改')
          sample.reportCheckInfo = undefined; sample.reportReviewInfo = undefined; sample.reportApprovalInfo = undefined
          if (sample.workflow) { sample.workflow.auditDate = undefined; sample.workflow.approvalDate = undefined }
        } else if (kind === 'commissions') {
          row.status = actionId === 'complete' ? '已完成' : '未完成'
        } else {
          const sample = row as RegistrationSample
          if (actionId === 'void') {
            requestSampleVoid(sample, a, reason)
          } else {
            sample.status = actionId === 'complete' ? 'completed' : 'pending'
            sample.dataStatus = actionId === 'complete' ? '完成登记' : '委托登记中'
          }
        }
        audit(row, a, actionId === 'complete-change' ? '完成委托更改' : actionId === 'void' ? '提交作废申请' : actionId === 'start-review' ? '开始合同评审' : actionId === 'review' ? ((row as RegistrationSample).contractReview?.decision === 'approved' ? '评审通过' : '评审不通过') : action.label, reason); return row
      })
    },
    async export(kind: RegistrationKind, query: RegistrationQuery, workspace: RegistrationWorkspace = 'registration') {
      const state = read()
      const rows = kind === 'commissions' ? (matching(state, kind, query) as RegistrationCommission[]).map(record => { const row = summaryCommission(record); return commissionColumns.map(column => commissionCell(row, column.key)) }) : sampleRows(state, query, workspace).map(record => {
        if (workspace === 'query') { const row = summaryInquirySample(record); return inquirySampleColumns.map(column => inquirySampleCell(row, column.key)) }
        const row = summarySample(record); return sampleColumns.map(column => sampleCell(row, column.key))
      })
      const header = kind === 'commissions' ? commissionColumns.map(column => column.label) : (workspace === 'query' ? inquirySampleColumns : sampleColumns).map(column => column.label)
      return new Blob([registrationCsv([header, ...rows])], { type: 'text/csv;charset=utf-8' })
    },
    async attachments(id: string, kind: RegistrationKind = 'commissions') {
      const a = actor(kind), row = find(read(), kind, id, a)
      return { id: row.id, code: row.code, name: row.name, version: row.version, attachments: row.attachments, canManageAttachments: workspaceCanManageAttachments(a, kind, row) }
    },
    async deleteAttachment(id: string, version: number, attachmentId: string, kind: RegistrationKind = 'commissions', workspace: RegistrationWorkspace = 'registration') {
      const a = actor(kind)
      if (!registrationCanWrite(a, kind)) fail('当前身份无权删除附件。', 'FORBIDDEN')
      return write(state => {
        const row = find(state, kind, id, a); 
        if (kind === 'samples' && sampleReadOnlyReason(row.status)) fail(`${sampleReadOnlyReason(row.status)}，不允许此操作。`)
        if (!workspaceCanManageAttachments(a, kind, row, workspace)) fail(kind === 'commissions' ? '已完成委托不能删除附件，请先取消完成。' : '当前样品状态不允许删除附件，仅检测数据录入完成前的有效样品支持附件管理。')
        const index = row.attachments.findIndex(file => file.id === attachmentId)
        if (index < 0) fail('附件不存在或已被删除。', 'NOT_FOUND')
        const [removed] = row.attachments.splice(index, 1)
        audit(row, a, '删除附件', removed!.name); return { ...row, canManageAttachments: workspaceCanManageAttachments(a, kind, row, workspace) }
      })
    },
    async attach(id: string, version: number, file: Omit<DemoAttachment, 'id'>, kind: RegistrationKind = 'commissions', workspace: RegistrationWorkspace = 'registration') {
      const a = actor(kind)
      if (!registrationCanWrite(a, kind)) fail('当前身份无权添加附件。', 'FORBIDDEN')
      if (typeof file.name !== 'string' || !file.name.trim() || file.name.length > 255 || typeof file.type !== 'string' || typeof file.dataUrl !== 'string' || !Number.isSafeInteger(file.size) || file.size < 0 || file.size > 20 * 1024 * 1024) fail('请选择不超过 20 MB 的有效附件。', 'VALIDATION')
      const encoded = file.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
      if (encoded === undefined || encoded.length % 4 !== 0 || Buffer.from(encoded, 'base64').length !== file.size) fail('附件内容或大小不正确。', 'VALIDATION')
      return write(state => {
        const row = find(state, kind, id, a); 
        if (kind === 'samples' && sampleReadOnlyReason(row.status)) fail(`${sampleReadOnlyReason(row.status)}，不允许此操作。`)
        if (!workspaceCanManageAttachments(a, kind, row, workspace)) fail(kind === 'commissions' ? '已完成委托不能追加附件，请先取消完成。' : '当前样品状态不允许追加附件，仅检测数据录入完成前的有效样品支持附件管理。')
        row.attachments.push({ ...file, id: crypto.randomUUID() }); audit(row, a, '添加附件', file.name); return { ...row, canManageAttachments: workspaceCanManageAttachments(a, kind, row, workspace) }
      })
    },
  }
}
