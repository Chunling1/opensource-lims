import { dataEntryStatus } from '../src/types/commissions/workflow'
import { createHash, randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { registrationCanReadSamples } from '../src/services/commissions/registrationService'
import { demoActors } from '../src/services/storage/demoActors'
import { emptyTrialForm, legacyTrialDates, normalizeConclusion, entryConclusions, type TrialForm, type EntryState, type EntryDetail, type EntryTemplate, type EntryOptions, type EntryCapabilities, type EntryFileKind } from '../src/types/testing/dataEntryDetail'
import type { RegistrationDependencies, RegistrationSample, RegistrationState } from '../src/types/commissions/registration'
import type { Actor } from '../src/types/lims'
import { getSampleReportConfig } from './sampleReportSettings'
import { reportSettingFields } from '../src/types/commissions/reportSettings'
import { stockDate } from './stockReceipt'
import { entryPeople, queryEntryPeople, resolveEntryPerson } from './dataEntryPeople'
import { templateTask, finalTask } from './dataEntryTasks'
import { fieldChanges, entryRecords } from './dataEntryRecords'
import { equipmentOptions, equipmentConfig, updateEquipmentConfig } from './dataEntryEquipment'
import { dataCheckCapabilities } from './testingDataCheck'
import { reportCheckCapabilities } from './reportCheck'
import { canChangeData } from '../src/types/testing/dataChanges'
import { completeReportConfig, completeReportGeneration } from './dataEntryGeneration'

const maxFileSize = 20 * 1024 * 1024
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new AppError('BAD_REQUEST', '请求格式有误。')
  return value as Record<string, unknown>
}
export function entryCapabilities(actor: Actor, sample: RegistrationSample): EntryCapabilities {
  const canView = registrationCanReadSamples(actor) && (actor.scope === 'all' || actor.departmentId === sample.departmentId)
  const manage = canView && actor.roles.some(role => ['admin', 'testing'].includes(role)) && !['voided', 'void_pending'].includes(sample.status)
  const status = dataEntryStatus(sample.dataStatus)
  const canEdit = manage && (status === '检测数据录入中' || canChangeData(actor, sample))
  return { canView, canEdit, canManageReport: canEdit, canManageOriginals: manage && ['检测数据录入中', '检测数据录入完成', '检测更改中'].includes(status), canComplete: manage && status === '检测数据录入中', canUndo: manage && sample.dataStatus === '检测数据录入完成' && !sample.workflow?.auditDate && !sample.workflow?.approvalDate, canCheck: canView && dataCheckCapabilities(actor, sample).canCheck, canReportCheck: canView && reportCheckCapabilities(actor, sample).canCheck, canReportReview: canView && reportCheckCapabilities(actor, sample, 'review').canCheck, canReportApprove: canView && reportCheckCapabilities(actor, sample, 'approval').canCheck }
}
export function entryTemplate(sample: RegistrationSample, layoutId = sample.details?.reportSettings.layoutId): EntryTemplate {
  const config = getSampleReportConfig(), settings = sample.details?.reportSettings ? { ...sample.details.reportSettings, layoutId } : undefined
  const valid = settings && config.combinations.some(row => reportSettingFields.every(({ key }) => row[key] === settings[key]))
  return { id: settings ? reportSettingFields.map(({ key }) => settings[key]).join('-') : '', version: config.version,
    labels: reportSettingFields.map(({ key, label }) => `${label}：${config.options[key].find(row => row.id === settings?.[key])?.label || '未设置'}`),
    ...(!valid ? { error: '报告配置不完整或组合不可用，请通过委托更改或退回流程修正。' } : {}) }
}
const templateKey = (template: EntryTemplate) => `${template.id}:${template.version}`
const sourceKey = (sample: RegistrationSample) => {
  // Report form selects the post-approval workflow, not the report body or template.
  const { reportForm: _form, ...details } = sample.details || {}
  return createHash('sha256').update(JSON.stringify([sample.code, sample.reportCode, sample.name, sample.customer, sample.projects, sample.commissionInfo, details])).digest('hex')
}
function layouts(sample: RegistrationSample) {
  const config = getSampleReportConfig(), settings = sample.details?.reportSettings
  return config.options.layoutId.filter(option => config.combinations.some(row => row.layoutId === option.id && ['formatId', 'titleId', 'languageId'].every(key => row[key as 'formatId'] === settings?.[key as 'formatId'])))
}
const templateSource = (sample: RegistrationSample, entry: EntryState, kind = 'template') => createHash('sha256').update(JSON.stringify([sourceKey(sample), entry.form, templateKey(entryTemplate(sample, entry.layoutId)), kind, kind === 'complete-report' ? completeReportConfig : undefined])).digest('hex')
function options(sample: RegistrationSample): EntryOptions {
  return { people: entryPeople('tester'), reviewers: entryPeople('reviewer'), approvers: entryPeople('approver'), equipment: equipmentOptions(sample), maxFileSize }
}
function initial(sample: RegistrationSample): EntryState {
  const assigned = (id?: string, name?: string) => {
    if (id) return id
    const matches = options(sample).people.filter(person => person.name === name)
    return matches.length === 1 ? matches[0]!.id : ''
  }
  return { version: 1, reportRevision: 1, form: { ...emptyTrialForm(), tester1Id: assigned(sample.assignmentInfo?.tester1Id, sample.assignmentInfo?.tester1), tester2Id: assigned(sample.assignmentInfo?.tester2Id, sample.assignmentInfo?.tester2), testDates: sample.dataEntryInfo?.testDates || legacyTrialDates(sample.workflow?.testStartDate, sample.workflow?.testEndDate), testStartDate: sample.workflow?.testStartDate || '', testEndDate: sample.workflow?.testEndDate || '', conclusionStatus: normalizeConclusion(sample.assignmentInfo?.conclusion || '') }, files: [], events: [], requests: [] }
}
// Seed explicit, completed demo reports rather than fabricating a final file on approval.
export function seedCompletedReport(state: RegistrationState, sample: RegistrationSample) {
  const entry = initial(sample), template = entryTemplate(sample)
  entry.layoutId = sample.details?.reportSettings.layoutId; entry.layoutAdopted = true
  entry.form.conclusion = '演示检测结果符合要求。'; entry.form.conclusionStatus = '合格'
  entry.job = { id: `demo-final-${sample.id}`, sourceRevision: entry.reportRevision, sourceKey: sourceKey(sample), templateKey: templateKey(template), createdAt: Date.now() - 60000, status: 'ready' }
  entry.reportConfirmation = { taskId: entry.job.id, at: new Date().toISOString(), actor: 'admin' }
  ;(state.dataEntries ??= {})[sample.id] = entry
  entry.taskSnapshots = { [entry.job.id]: createDataEntryService({ actor: () => demoActors[0]!, read: () => state }).detail(sample.id) }
}
function parseForm(value: unknown, sample: RegistrationSample, complete: boolean | 'report' = false): TrialForm {
  const input = object(value), form = emptyTrialForm(), errors: Record<string, string> = {}, choices = options(sample)
  for (const key of Object.keys(form) as (keyof TrialForm)[]) {
    if (['testDates', 'testStartDate', 'testEndDate'].includes(key)) continue
    const field = input[key], defaultValue = form[key]
    if (typeof defaultValue === 'boolean') { if (typeof field !== 'boolean') errors[key] = '请选择有效选项。'; else Object.assign(form, { [key]: field }) }
    else if (Array.isArray(defaultValue)) { if (!Array.isArray(field) || field.some(item => typeof item !== 'string') || field.length > 100) errors[key] = '请选择有效选项。'; else Object.assign(form, { [key]: [...new Set(field)] }) }
    else if (typeof field !== 'string' || field.length > (['conclusion', 'notes'].includes(key) ? 5000 : 500)) errors[key] = '内容格式错误或超出长度限制。'
    else Object.assign(form, { [key]: field.trim() })
  }
  const dates = input.testDates === undefined ? legacyTrialDates(typeof input.testStartDate === 'string' ? input.testStartDate : '', typeof input.testEndDate === 'string' ? input.testEndDate : '') : input.testDates
  form.testDates = []
  if (!Array.isArray(dates) || !dates.length || dates.length > 50) errors.testDates = '试验日期至少保留一项，最多填写 50 项。'
  else dates.forEach((value, index) => {
    const key = `testDates.${index}`
    if (!value || typeof value !== 'object' || !['single', 'range'].includes(value.kind) || typeof value.from !== 'string' || typeof value.to !== 'string') { errors[key] = '请选择有效的日期类型和日期。'; return }
    const row = { kind: value.kind as 'single' | 'range', from: value.from.trim(), to: value.to.trim() }
    if (row.kind === 'single') row.to = row.from
    row.kind = 'range'
    for (const date of [row.from, row.to]) if (date) try { stockDate({ date }, '日期') } catch { errors[key] = '请输入有效日期。' }
    if (!errors[key] && row.from && row.to && row.from > row.to) errors[key] = '结束日期不能早于开始日期。'
    if (!errors[key] && complete && (!row.from || !row.to)) errors[key] = '请完整填写开始和结束日期。'
    form.testDates.push(row)
  })
  if (complete && !form.testDates.length && !errors.testDates) errors.testDates = '完成录入前请至少填写一项试验日期。'
  form.testStartDate = form.testDates.map(row => row.from).filter(Boolean).sort()[0] || ''
  form.testEndDate = form.testDates.map(row => row.to).filter(Boolean).sort().at(-1) || ''
  form.conclusionStatus = normalizeConclusion(form.conclusionStatus)
  if (form.conclusionStatus && !(entryConclusions as readonly string[]).includes(form.conclusionStatus)) errors.conclusionStatus = '请选择有效结论状态。'
  for (const key of ['tester1Id', 'tester2Id', 'reviewerId', 'approverId'] as const) {
    const list = key === 'reviewerId' ? choices.reviewers : key === 'approverId' ? choices.approvers : choices.people
    if (form[key] && !list.some(person => person.id === form[key])) errors[key] = '人员不存在或不在可选范围内。'
  }
  if (form.tester1Id && form.tester1Id === form.tester2Id) errors.tester2Id = '两位试验人不能重复。'
  if (form.equipmentIds.some(id => !choices.equipment.some(row => row.id === id))) errors.equipmentIds = '设备不在当前样品部门范围内。'
  if (!form.calibrationEnabled) form.calibrationDate = ''
  if (!form.reportDateEnabled) form.reportDate = ''
  for (const key of ['calibrationDate', 'reportDate'] as const) {
    if (form[key]) try { stockDate({ date: form[key] }, '日期') } catch { errors[key] = '请输入有效日期。' }
  }
  if (form.calibrationEnabled && !form.calibrationDate) errors.calibrationDate = '请填写校准日期。'
  if (form.reportDateEnabled && !form.reportDate) errors.reportDate = '请填写报告日期。'
  if (complete) {
    for (const key of ['conclusion', 'conclusionStatus', 'tester1Id'] as const) if (!form[key]) errors[key] = complete === 'report' ? '报告填写前请填写此项。' : '完成录入前请填写此项。'
    if (form.conclusionStatus === '不合格' && !form.failedParameters.length) errors.failedParameters = '不合格时必须填写不合格参数。'
  }
  if (Object.keys(errors).length) throw new AppError('VALIDATION', complete === 'report' ? '请先补全试验信息，再进入报告填写。' : '请检查试验信息。', { fieldErrors: errors })
  return form
}

export function validateEntryCompletion(state: RegistrationState, sample: RegistrationSample, actor: Actor, acknowledgeMissingOriginals = false, now = () => Date.now()) {
  const detail = createDataEntryService({ actor: () => actor, read: () => state }, now).detail(sample.id)
  const operation = sample.dataStatus === '检测更改中' ? '更改' : '录入'
  parseForm(detail.form, sample, true)
  if (detail.reportStatus !== 'ready') throw new AppError('BUSINESS_RULE', `请先生成最新最终报告，再完成${operation}。`, { fieldErrors: { finalReport: '请先生成最新最终报告。' } })
  const originals = state.originalRecords?.[sample.id], entry = state.dataEntries?.[sample.id]
  const hasOriginal = originals?.records.some(record => record.source === 'file' ? !!record.files?.length : record.source === 'scan' && !!(record.draft?.files.length || record.revisions?.some(revision => revision.files.length)))
    || entry?.files.some(file => file.kind === 'original' && !originals?.migratedFileIds.includes(file.id))
  if (!hasOriginal && !acknowledgeMissingOriginals) throw new AppError('BUSINESS_RULE', `尚未上传原始记录，是否继续完成${operation}？`, { fieldErrors: { originalRecords: '尚未上传原始记录。' } })
  return !hasOriginal
}

export function createDataEntryService(deps: RegistrationDependencies, now = () => Date.now()) {
  function context(id: string) {
    if (deps.locked?.()) throw new AppError('LOCKED', '工作空间已锁定。')
    const actor = deps.actor()
    if (!registrationCanReadSamples(actor)) throw new AppError('FORBIDDEN', '无权查看样品。')
    const state = structuredClone(deps.read?.())
    const sample = state?.samples.find(row => row.id === id && (actor.scope === 'all' || actor.departmentId === row.departmentId))
    if (!sample || !state) throw new AppError('NOT_FOUND', '样品不存在或已不可访问。')
    const entries = state.dataEntries ??= {}
    const entry = entries[id] ??= { ...initial(sample), form: { ...initial(sample).form, equipmentIds: [...equipmentConfig(state, sample).defaultIds] } }
    entry.layoutId ??= sample.details?.reportSettings.layoutId || ''
    entry.layoutAdopted ??= !!(entry.templateJobs?.length || entry.job || entry.files.some(file => file.kind === 'report' || file.kind === 'appendix'))
    // Restore an unfinished legacy layout change without discarding its adopted file.
    const legacy = entry as EntryState & { layoutChange?: { fromLayoutId: string; reportId: string }; reportCandidate?: unknown; formRevision?: number }
    if (legacy.layoutChange && entry.files.some(file => file.id === legacy.layoutChange!.reportId)) entry.layoutId = legacy.layoutChange.fromLayoutId
    delete legacy.layoutChange; delete legacy.reportCandidate; delete legacy.formRevision
    for (const file of entry.files) delete (file as typeof file & { binding?: unknown }).binding
    if (entry.form.testDates === undefined) entry.form.testDates = legacyTrialDates(entry.form.testStartDate, entry.form.testEndDate)
    if (!entry.form.testDates.length) entry.form.testDates = [{ kind: 'range', from: '', to: '' }]
    entry.form.testDates = entry.form.testDates.map(row => ({ ...row, kind: 'range', to: row.kind === 'single' ? row.from : row.to }))
    if (Array.isArray(entry.form.failedParameters)) entry.form.failedParameters = entry.form.failedParameters.join('、')
    return { state, sample, actor, entry }
  }
  function detail(id: string): EntryDetail {
    const { state, sample, actor, entry } = context(id), template = entryTemplate(sample, entry.layoutId)
    const job = entry.job ? finalTask(entry.job, now(), entry.files.filter(file => file.kind !== 'original').map(file => file.id)) : undefined
    const stale = job && (job.sourceRevision !== entry.reportRevision || job.templateKey !== templateKey(template) || job.sourceKey !== sourceKey(sample))
    const key = templateSource(sample, entry), tasks = (entry.templateJobs || []).filter(task => !task.kind || task.kind === 'template')
    const current = [...tasks].reverse().find(task => task.sourceKey === key) || tasks.at(-1)
    const completeKey = templateSource(sample, entry, 'complete-report'), completeTasks = (entry.templateJobs || []).filter(task => task.kind === 'complete-report')
    const completeTask = [...completeTasks].reverse().find(task => task.sourceKey === completeKey) || completeTasks.at(-1)
    return { completeReportGeneration: completeReportGeneration(sample), completeReportJob: completeTask ? templateTask(completeTask, now()) : undefined, completeReportStale: !!completeTask && completeTask.sourceKey !== completeKey, equipmentConfig: equipmentConfig(state, sample), sample: { ...sample, attachments: [], events: [] }, version: entry.version, reportRevision: entry.reportRevision, form: entry.form, files: entry.files.map(({ dataUrl: _data, ...file }) => file), template, options: options(sample), capabilities: entryCapabilities(actor, sample), job, layoutId: entry.layoutId!, layoutAdopted: entry.layoutAdopted!, layouts: layouts(sample), templateJob: current ? templateTask(current, now()) : undefined, templateStale: !!current && current.sourceKey !== key, reportStatus: !job ? 'pending' : stale ? 'stale' : job.status, reportConfirmed: !!job && !stale && job.status === 'ready' && entry.reportConfirmation?.taskId === job.id, simulated: true }
  }
  function file(id: string, fileId: string) {
    const { entry } = context(id)
    const found = entry.files.find(item => item.id === fileId)
    if (!found) throw new AppError('NOT_FOUND', '文件不存在或不属于当前样品。')
    return found
  }
  function mutate(id: string, action: string, value: unknown): EntryDetail {
    const input = object(value), { state, sample, actor, entry } = context(id), capabilities = entryCapabilities(actor, sample)
    if (typeof input.requestId !== 'string' || !input.requestId || input.requestId.length > 100) throw new AppError('BAD_REQUEST', '缺少有效请求标识。')
    const fingerprint = createHash('sha256').update(JSON.stringify({ action, input })).digest('hex')
    const previous = entry.requests.find(row => row.id === input.requestId && row.actor === actor.id)
    if (previous) {
      if (previous.fingerprint !== fingerprint) throw new AppError('BUSINESS_RULE', '请求标识已用于其他内容，请刷新核对。')
      return detail(id)
    }
    const originalAction = action === 'upload' && input.kind === 'original' || action === 'delete' && entry.files.find(row => row.id === input.fileId)?.kind === 'original'
    const allowed = action === 'complete' ? capabilities.canComplete : action === 'undo' ? capabilities.canUndo : originalAction ? capabilities.canManageOriginals : capabilities.canEdit
    if (!allowed) throw new AppError('FORBIDDEN', '当前权限或样品状态不允许此操作，请刷新查看。')
    
    if (action === 'validate-report-entry') {
      parseForm(entry.form, sample, 'report')
      return detail(id)
    }
    const before = { ...entry.form, layoutId: entry.layoutId }
    let reportChanged = false, completedWithoutOriginal = false
    if (['equipment-associate', 'equipment-defaults', 'equipment-unset-defaults'].includes(action)) {
      updateEquipmentConfig(state, sample, action, input)
    } else if (action === 'save') {
      if (input.prepareReport !== undefined && input.prepareReport !== true) throw new AppError('BAD_REQUEST', '报告填写校验参数无效。')
      const form = parseForm(input.form, sample, input.prepareReport === true ? 'report' : false)
      const layoutId = input.layoutId ?? entry.layoutId
      if (typeof layoutId !== 'string' || !layouts(sample).some(row => row.id === layoutId)) throw new AppError('VALIDATION', '请选择有效报告版式。', { fieldErrors: { layoutId: '当前报告类型和语言不支持此版式。' } })
      if (input.adoptLayout !== undefined && input.adoptLayout !== true) throw new AppError('BAD_REQUEST', '版式采用参数无效。')
      if (layoutId !== entry.layoutId && (entry.templateJobs?.length || entry.job || entry.files.some(file => file.kind === 'report' || file.kind === 'appendix'))) throw new AppError('BUSINESS_RULE', '请确认更换版式后再保存。')
      reportChanged = JSON.stringify(form) !== JSON.stringify(entry.form) || layoutId !== entry.layoutId
      entry.layoutAdopted = input.adoptLayout === true || layoutId === entry.layoutId && !!entry.layoutAdopted
      entry.layoutId = layoutId
      entry.form = form
      sample.dataEntryInfo = { testDates: structuredClone(form.testDates), tester1: demoActors.find(row => row.id === form.tester1Id)?.name || '', tester2: demoActors.find(row => row.id === form.tester2Id)?.name || '' }
      sample.workflow = { ...sample.workflow, testStartDate: form.testStartDate, testEndDate: form.testEndDate, reportDate: form.reportDate,
        conclusion: form.conclusionStatus === '合格' ? 'qualified' : form.conclusionStatus === '不合格' ? 'unqualified' : undefined }
      sample.assignmentInfo = { ...sample.assignmentInfo, conclusion: form.conclusionStatus as NonNullable<RegistrationSample['assignmentInfo']>['conclusion'] }
      sample.version++
    } else if (action === 'upload') {
      const kind = input.kind as EntryFileKind, source = object(input.file)
      const extension = typeof source.name === 'string' ? source.name.split('.').pop()?.toLowerCase() : ''
      const allowedExtensions = kind === 'report' ? ['docx'] : kind === 'appendix' ? ['pdf', 'docx'] : kind === 'original' ? ['pdf'] : []
      if (!extension || !allowedExtensions.includes(extension) || typeof source.name !== 'string' || source.name.length > 255 || !Number.isSafeInteger(source.size) || Number(source.size) < 1 || Number(source.size) > maxFileSize || typeof source.dataUrl !== 'string') throw new AppError('VALIDATION', '文件格式不支持或超过 20 MB。')
      const encoded = source.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1], bytes = encoded ? Buffer.from(encoded, 'base64') : undefined
      if (!bytes || bytes.length !== source.size || (extension === 'pdf' ? bytes.subarray(0, 5).toString() !== '%PDF-' : extension === 'docx' ? bytes.subarray(0, 4).toString('hex') !== '504b0304' : extension === 'png' ? bytes.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a' : bytes.subarray(0, 3).toString('hex') !== 'ffd8ff')) throw new AppError('VALIDATION', '文件内容与格式不一致。')
      const types: Record<string, string> = { pdf: 'application/pdf', docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg' }
      const file = { id: randomUUID(), name: source.name, type: types[extension]!, size: Number(source.size), dataUrl: `data:${types[extension]};base64,${encoded}`, kind }
      if (kind === 'report') entry.files = [file, ...entry.files.filter(row => row.kind !== 'report')]
      else entry.files.push(file)
      reportChanged = kind !== 'original'
    } else if (action === 'change-report-layout') {
      const layoutId = input.layoutId
      if (input.confirmed !== true) throw new AppError('BUSINESS_RULE', '请确认更换版式并清空完整报告。')
      if (typeof layoutId !== 'string' || layoutId === entry.layoutId || !layouts(sample).some(row => row.id === layoutId)) throw new AppError('VALIDATION', '请选择可用且不同的报告版式。')
      entry.files = entry.files.filter(file => file.kind !== 'report')
      entry.layoutId = layoutId; entry.layoutAdopted = true; reportChanged = true
    } else if (action === 'delete') {
      if (state.originalRecords?.[id]?.records.some(record => [...(record.files || []), ...(record.revisions || []).flatMap(revision => revision.files), ...(record.draft?.files || [])].some(file => file.id === input.fileId))) throw new AppError('BUSINESS_RULE', '请在原始记录工作区管理此文件。')
      const index = entry.files.findIndex(row => row.id === input.fileId)
      if (index < 0) throw new AppError('NOT_FOUND', '文件不存在或不属于当前样品。')
      reportChanged = entry.files[index]!.kind !== 'original'; entry.files.splice(index, 1)
    } else if (action === 'sort') {
      const ids = input.ids, appendices = entry.files.filter(row => row.kind === 'appendix')
      if (!Array.isArray(ids) || ids.length !== appendices.length || new Set(ids).size !== ids.length || ids.some(id => !appendices.some(row => row.id === id))) throw new AppError('BAD_REQUEST', '附页顺序必须包含当前全部附页。')
      entry.files = [...entry.files.filter(row => row.kind !== 'appendix'), ...ids.map(id => appendices.find(row => row.id === id)!)]; reportChanged = true
    } else if (action === 'template-tasks' || action === 'retry-template-pdf') {
      const kind = input.kind ?? 'template'
      if (kind !== 'template' && kind !== 'complete-report') throw new AppError('BAD_REQUEST', '报告下载类型无效。')
      if (kind === 'complete-report' && !completeReportGeneration(sample).layoutIds.includes(entry.layoutId!)) throw new AppError('BUSINESS_RULE', completeReportGeneration(sample).unavailableReason)
      const template = entryTemplate(sample, entry.layoutId), key = templateSource(sample, entry, kind)
      if (template.error) throw new AppError('BUSINESS_RULE', template.error)
      const tasks = entry.templateJobs ??= []
      if (action === 'retry-template-pdf') {
        const task = tasks.find(row => row.id === input.taskId)
        if (!task || task.sourceKey !== key) throw new AppError('BUSINESS_RULE', '模板资料或版式已更新，请重新生成模板。')
        if (templateTask(task, now()).stage !== 'pdf-failed') throw new AppError('BUSINESS_RULE', '当前模板不需要重试转换。')
        task.conversionStartedAt = now(); task.scenario = undefined
      } else {
        if (input.wordOnly !== undefined && typeof input.wordOnly !== 'boolean') throw new AppError('BAD_REQUEST', '模板生成选项无效。')
        if (input.scenario !== undefined && !['failure', 'word-failure', 'pdf-failure', 'slow'].includes(String(input.scenario))) throw new AppError('BAD_REQUEST', '模拟场景无效。')
        const existing = [...tasks].reverse().find(task => (task.kind || 'template') === kind && task.sourceKey === key)
        if (!existing || templateTask(existing, now()).stage === 'word-failed') {
          const task = { id: randomUUID(), sourceKey: key, sourceRevision: entry.reportRevision, layoutId: entry.layoutId!, templateVersion: template.version, createdAt: now(), stage: 'word' as const, wordAvailable: false, pdfAvailable: false, elapsedMs: 0, wordOnly: input.wordOnly === true, scenario: input.scenario as 'failure' | 'word-failure' | 'pdf-failure' | 'slow' | undefined }
          tasks.push({ ...task, kind, wordOnly: kind === 'complete-report' || task.wordOnly }); (entry.taskSnapshots ??= {})[task.id] = detail(id)
        }
      }
    } else if (action === 'combine') {
      const template = entryTemplate(sample, entry.layoutId)
      if (template.error) throw new AppError('BUSINESS_RULE', template.error)
      if (input.scenario !== undefined && !['failure', 'slow'].includes(String(input.scenario))) throw new AppError('BAD_REQUEST', '模拟场景无效。')
      const current = detail(id)
      if (!['running', 'ready'].includes(current.reportStatus)) {
        entry.job = { id: randomUUID(), sourceRevision: entry.reportRevision, sourceKey: sourceKey(sample), templateKey: templateKey(template), createdAt: now(), status: 'running', scenario: input.scenario as 'failure' | 'slow' | undefined }
        ;(entry.taskSnapshots ??= {})[entry.job.id] = current
      }
    } else if (action === 'confirm-report') {
      if (!capabilities.canManageReport) throw new AppError('FORBIDDEN', '当前权限不允许确认报告。')
      if (!entry.job || detail(id).reportStatus !== 'ready' || input.taskId !== entry.job.id) throw new AppError('BUSINESS_RULE', '请预览最新报告后再确认。', { fieldErrors: { finalReport: '请生成并预览最新报告。' } })
      entry.reportConfirmation = { taskId: entry.job.id, at: new Date(now()).toISOString(), actor: actor.id }
    } else if (action === 'complete') {
      completedWithoutOriginal = validateEntryCompletion(state, sample, actor, input.acknowledgeMissingOriginals === true, now)
      sample.dataStatus = '检测数据录入完成'; sample.version++
    } else if (action === 'undo') {
      sample.dataStatus = '检测数据录入中'; sample.version++
    } else throw new AppError('NOT_FOUND', '操作不存在。')
    if (dataEntryStatus(sample.dataStatus) !== sample.dataStatus) { sample.dataStatus = '检测数据录入中'; sample.version++ }
    if (reportChanged) { entry.reportRevision++; delete entry.reportConfirmation }
    entry.version++; entry.events.push({ at: new Date(now()).toISOString(), actor: `${actor.name}（${actor.id}）`, action, reason: completedWithoutOriginal ? '已确认无原始记录，继续完成录入' : action === 'change-report-layout' ? entry.layoutId! : typeof input.fileId === 'string' ? input.fileId : '', ...(['save', 'change-report-layout'].includes(action) ? { changes: fieldChanges(before, { ...entry.form, layoutId: entry.layoutId }) } : {}) })
    entry.requests.push({ id: input.requestId, actor: actor.id, fingerprint })
    deps.write?.(state)
    return detail(id)
  }
  function people(id: string, value: unknown) {
    const { sample, actor } = context(id)
    return queryEntryPeople(sample, actor, object(value))
  }
  function resolvePerson(id: string, value: unknown) {
    const { sample, actor } = context(id)
    if (!entryCapabilities(actor, sample).canEdit) throw new AppError('FORBIDDEN', '当前权限或样品状态不允许修改人员，请刷新查看。')
    return resolveEntryPerson(object(value))
  }
  function taskResult(id: string, taskId: string, kind: 'word' | 'pdf' | 'final') {
    const { entry, sample } = context(id)
    const snapshot = entry.taskSnapshots?.[taskId]
    if (!snapshot) throw new AppError('NOT_FOUND', '任务不存在或不属于当前样品。')
    if (kind === 'final') {
      if (entry.job?.id !== taskId || detail(id).reportStatus !== 'ready') throw new AppError('BUSINESS_RULE', '请生成最新最终报告。')
    } else {
      const task = entry.templateJobs?.find(row => row.id === taskId)
      if (!task) throw new AppError('NOT_FOUND', '模板任务不存在。')
      if (task.kind === 'complete-report' && (!completeReportGeneration(sample).layoutIds.includes(task.layoutId) || task.sourceKey !== templateSource(sample, entry, 'complete-report'))) throw new AppError('BUSINESS_RULE', '完整报告资料或生成能力已更新，请重新生成。')
      const status = templateTask(task, now())
      if (kind === 'word' ? !status.wordAvailable : !status.pdfAvailable) throw new AppError('BUSINESS_RULE', '任务文件尚未生成。')
    }
    return snapshot
  }
  function taskStatus(id: string, taskId: string) {
    const task = context(id).entry.templateJobs?.find(row => row.id === taskId)
    if (!task) throw new AppError('NOT_FOUND', '模板任务不存在或不属于当前样品。')
    return templateTask(task, now())
  }
  function records(id: string, query: unknown) { const { sample, entry } = context(id); return entryRecords(sample, entry, query) }
  return { detail, mutate, file, templateKey, people, resolvePerson, taskResult, taskStatus, records }
}

