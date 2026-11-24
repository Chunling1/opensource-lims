import { planRequest } from '../../platformUi/lists/planCatalogue'
import { AppError } from '../common/errors'
import { platformRequest } from './http'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { profile } from './auth'
type Row = Record<string, any>
const commissionSnapshots = new Map<string, Row>()
export const commissionInfoFields: Record<string,string> = {
  contact:'consignor', phone:'consignorPhone', commissionDate:'entrustDate', erpContract:'erpProjectNo', erpProjectType:'erpType',
  contractParty:'contractPartyA', payer:'otherPartyA', customerAddress:'clientAddr', customerLegalRepresentative:'clientLegal',
  customerPhone:'clientPhone', customerPostcode:'clientZip', projectRegistrationCode:'projectRecordNo', projectTradingCode:'projectTradeCode',
  projectAddress:'projectAddr', handlingDepartmentId:'handleDept', handlerPhone:'handlerPhone', invoiceType:'invoiceType', taxpayerNumber:'taxNo',
  invoiceCompany:'companyName', invoiceAddress:'bizAddr', bankName:'bank', bankAccount:'account',
}
export function commissionPayload(input: Row, previous?: Row): Row {
  const info = { ...previous?.info }
  for (const [field,key] of Object.entries(commissionInfoFields)) if (field in input) info[key]=string(input[field])
  return { contractNo:string(input.contract), client:string(input.customer), projectName:string(input.name), department:string(input.handlingDepartmentId),
    projectType: previous?.projectType || string(input.erpProjectType), info }
}
const string = (value: unknown) => value == null ? '' : String(value)
const date = (value: unknown) => string(value).match(/^\d{4}-\d{2}-\d{2}/)?.[0] || ''
const money = (value: unknown) => value === '' || value == null || !Number.isFinite(Number(value)) ? null : Number(value)
export const listBindings: Record<string, { path: string; view?: string; entity: 'commission' | 'sample' }> = {
  '/commissions/query': { path: '/api/entrust/query', entity: 'commission' },
  '/samples/query': { path: '/api/samples/query', view: 'register', entity: 'sample' },
  '/samples/inbound/query': { path: '/api/samples/query', view: 'inbound', entity: 'sample' },
  '/samples/outbound/query': { path: '/api/samples/query', view: 'outbound', entity: 'sample' },
  '/samples/flow/query': { path: '/api/samples/query', view: 'flow_query', entity: 'sample' },
  '/samples/data-entry/query': { path: '/api/reports/query', view: 'data_entry', entity: 'sample' },
  '/samples/data-query/query': { path: '/api/reports/query', view: 'query', entity: 'sample' },
  '/samples/data-changes/query': { path: '/api/reports/query', view: 'data_change', entity: 'sample' },
  '/reports/query/list': { path: '/api/reports/query', view: 'query', entity: 'sample' },
}
export function mapCommission(row: Row, fullDetail = true): Row {
  if (row.id == null || !row.entrustNo) throw new AppError('UNAVAILABLE', '委托列表缺少平台唯一标识，已停止映射。')
  if (!['委托中','委托完成'].includes(row.status)) throw new AppError('UNAVAILABLE', '平台返回了尚未映射的委托登记状态。')
  if(fullDetail) commissionSnapshots.set(`${profile.value?.account || ''}:${row.id}`, structuredClone(row))
  const info = row.info || {}
  const department = row.handlerDepartment || info.handleDept || row.department || ''
  if (department && !registrationDepartments.some(d => d.id === department)) registrationDepartments.push({id:department,name:department})
  return { id: string(row.id), code: row.entrustNo, name: row.projectName || '', customer: row.client || '',
    status: row.status === '委托完成' ? '已完成' : '未完成', platformStatus:row.status, dataStatus:row.dataStatus, contract: row.contractNo || '', owner: row.owner || '',
    createdAt: date(row.date), commissionDate: date(row.entrustDate), version: 0,
    contact: row.consignor || info.consignor || '', phone: row.consignorPhone || info.consignorPhone || '', sampleCount: row.sampleCount,
    receivableAmount: money(row.amount), departmentId: row.department || '',
    erpContract: row.erpProjectNo || '', erpProjectType: row.erpProjectType || '',
    contractParty: row.contractPartyA || info.contractPartyA || '', payer: info.otherPartyA || '', customerAddress: row.clientAddress || info.clientAddr || '',
    handlingDepartmentId: department, notes: info.remark || '',
    customerLegalRepresentative: info.clientLegal || '', customerPhone: info.clientPhone || '', customerPostcode: info.clientZip || '',
    projectRegistrationCode: info.projectRecordNo || '', projectTradingCode: info.projectTradeCode || '', projectAddress: info.projectAddr || '',
    handlerPhone: info.handlerPhone || '', invoiceType: info.invoiceType || '', taxpayerNumber: info.taxNo || '',
    invoiceCompany: info.companyName || '', invoiceAddress: info.bizAddr || '', bankName: info.bank || '', bankAccount: info.account || '',
    projects: [],
  }
}
export function mapSample(row: Row): Row {
  if (!row.reportNo || !row.sampleNo) throw new AppError('UNAVAILABLE', '样品列表缺少报告号或样品号，已停止映射。')
  if (!row.voided && !['登记中', '登记完成'].includes(row.sampleRegState)) throw new AppError('UNAVAILABLE', '平台返回了尚未映射的样品登记状态。')
  // Platform report.version is a document version, NOT a concurrency token.
  // No mutating operation uses the template's numeric version placeholder.
  const dates = row.workflowDates || {}
  return { ...row, id: row.reportNo, code: row.sampleNo, reportCode: row.reportNo,
    status: row.voided ? 'voided' : row.sampleRegState === '登记中' ? 'pending' : 'completed',
    version: 0, platformDocumentVersion: row.version, platformLifecycleStatus:row.status, dataStatus: row.dataStatus || row.status,
    name: row.sampleOrProjectName || '', customer: row.client || '', owner: row.registrar || row.owner || '',
    createdAt: date(row.sampleRegisteredAt), commissionDate: date(row.entrustDate),
    commissionId: row.entrustId == null ? '' : string(row.entrustId), commissionCode: row.entrustNo || '', commissionName: row.projectName || '', commissionOwner: row.handler || '',
    parameters: row.testItems || row.project || '', projectName: row.schemeDisplay || row.schemeName || '', engineeringName: row.projectName || '', testPlan: row.schemeCode || '',
    category: row.testCategory || '', sampleType: ({普通:'原始样品',英文:'英文报告样品',分项:'分项/阶段性报告样品',补充:'补充报告'} as Record<string,string>)[row.reportCategory] || row.reportCategory || '', quantity: row.quantity ?? null, unit: row.unit || '',
    attachmentCount: row.attachmentCount ?? null, standardPrice: money(row.amount), discountPrice: money(row.discountPrice), actualPrice: money(row.actualPrice),
    erpContractNumber: row.erpContractNo || '', erpProjectNumber: row.erpProjectNo || '', contractType: row.erpProjectType || '',
    contact: row.consignor || '', phone: row.consignorPhone || '', customerAddress: row.clientAddress || '',
    contractCode: row.erpContractNo || '', site: row.site || '', groupNumber: row.groupNumber || '',
    requestedTestDate: date(row.deadline), inspector: row.owner || '', assignedBy: row.assignedBy || '',
    assignedDate: date(row.assignedDate), testStartDate: date(row.testStartDate), testEndDate: date(row.testEndDate),
    releaseId: row.currentDocumentVersionId == null ? '' : string(row.currentDocumentVersionId),
    form: row.reportFormat || '', signingStatus: row.sign || '', reportArchiveStatus: row.archiveState || '',
    collectionDate: date(row.samplePickup?.pickupDate), recipient: row.samplePickup?.person || '',
    checkDate: date(dates.check), auditDate: date(dates.review), approvalDate: date(dates.approval),
    canAssign: false, canUndoAssign: false, canPrintTask: false, canReturn: false, canVoid: false, canEdit: false,
    canComplete: false, canUndo: false, canView: false, canManageOriginals: false,
  }
}
function selected(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0
  if (value && typeof value === 'object') return Object.values(value).some(selected)
  return value !== undefined && value !== null && value !== '' && value !== false
}
const queryFields: Record<string, string> = { code: 'code', sampleCode: 'code', reportCode: 'reportCode', customer: 'customer', owner: 'owner', contract: 'contract', category: 'category', commissionCode: 'commissionCode', dataStatus: 'dataStatus', sampleType: 'sampleType', site: 'site', checkStatus: 'checkStatus' }
export function mapReportStage(row: Row, stage: 'review' | 'approval'): Row {
  const label = stage === 'review' ? '审核' : '批准'
  if (!['active', 'recall'].includes(row.rowProjection)) throw new AppError('UNAVAILABLE', '平台未返回报告环节投影，无法区分待处理与可撤销记录。')
  return { ...mapSample(row), checkStatus: `${row.rowProjection === 'recall' ? '已' : '未'}${label}`,
    platformStageFilter: `报告${label}${row.rowProjection === 'recall' ? '完成' : '中'}`,
    checker: '', checkDate: '', reportReviewer: '', reportReviewDate: '', reportChecker: '', reportCheckDate: '',
    changeCount: null, canCheck: false, canUndoCheck: false, canVoid: false }
}
export function pageRows(rows: Row[], query: Row = {}) {
  const handled = new Set([...Object.keys(queryFields), 'page', 'pageSize', 'sort', 'direction', 'searchField', 'keyword', 'contains', 'status', 'from', 'to', 'commissionFrom', 'commissionTo', 'commissionId', 'commissionIds', 'ids', 'workspace', 'plans', 'dateField', 'stage'])
  for (const [key,value] of Object.entries(query)) if (!handled.has(key) && selected(value)) throw new AppError('UNAVAILABLE', `平台尚未对齐筛选字段 ${key}，未忽略此条件。`)
  if (selected(query.plans)) throw new AppError('UNAVAILABLE', '检测方案分组筛选需要对齐平台方案标识，当前未忽略筛选条件。')
  let filtered = rows.filter(row => {
    for (const [key,field] of Object.entries(queryFields)) {
      if(key==='dataStatus' && query[key]==='委托登记中' && 'sampleRegState' in row) { if(row.sampleRegState!=='登记中') return false; continue }
      if(key==='dataStatus' && query[key]==='完成登记' && 'sampleRegState' in row) { if(row.sampleRegState!=='登记完成'||row.platformLifecycleStatus!=='待合同评审') return false; continue }
      if (selected(query[key]) && !string(row[field]).toLocaleLowerCase().includes(string(query[key]).toLocaleLowerCase())) return false
    }
    if (selected(query.status) && row.status !== query.status && row.dataStatus !== query.status && row.platformStageFilter !== query.status) return false
    if (query.commissionId && row.commissionId !== query.commissionId) return false
    if (query.commissionIds?.length && !query.commissionIds.includes(row.commissionId)) return false
    if (query.ids?.length && !query.ids.includes(row.id)) return false
    const search = string(query.keyword || query.contains).toLocaleLowerCase()
    if (search) {
      const text = query.searchField && query.searchField !== 'all' ? string(row[query.searchField]) : Object.values(row).filter(v => typeof v === 'string').join(' ')
      if (!text.toLocaleLowerCase().includes(search)) return false
    }
    const value = string(row[query.dateField || 'commissionDate'])
    const from = query.from || query.commissionFrom, to = query.to || query.commissionTo
    return !((from && (!value || value < from)) || (to && (!value || value > to)))
  })
  if (query.sort) filtered = filtered.slice().sort((a,b) => string(a[query.sort]).localeCompare(string(b[query.sort]), 'zh-CN', { numeric: true }) * (query.direction === 'desc' ? -1 : 1))
  const page = Math.max(1, Number(query.page) || 1), pageSize = Math.max(1, Math.min(200, Number(query.pageSize) || 20))
  const plans = [...new Map(rows.filter(r => r.testPlan).map(r => [r.testPlan, { id: r.testPlan, name: r.projectName }])).values()]
  return { items: filtered.slice((page-1)*pageSize, page*pageSize), total: filtered.length, page, pageSize,
    sites: [...new Set(rows.map(r => r.site).filter(Boolean))],
    planSelection: { selection: { groupIds: [], planIds: [], excludedPlanIds: [] }, count: 0, total: plans.length, previews: [], groups: {} } }
}
async function scopedRows(path: string, view: string | undefined, signal?: AbortSignal) {
  const result = await platformRequest<{ rows: Row[]; total: number }>(path, { method: 'POST', body: view ? { view } : {}, signal })
  if (!Array.isArray(result.rows) || !Number.isInteger(result.total) || result.total !== result.rows.length) throw new AppError('UNAVAILABLE', '平台未返回完整授权列表，已停止本地筛选，避免分页漏项。')
  return result.rows
}
export async function platformAdapter<T>(path: string, method: string, data?: unknown, signal?: AbortSignal, _blob = false): Promise<T> {
  const query = (data || {}) as Row
  if (['/test-plans/selection','/test-plans/query'].includes(path) && method === 'POST') return await planRequest(path,query,signal) as T
  if (path === '/commissions/defaults' && method === 'GET') {
    const departments = await platformRequest<{rows:{name:string}[]}>('/api/entrust/handle-departments',{signal})
    registrationDepartments.splice(0,registrationDepartments.length,...departments.rows.map(row=>({id:row.name,name:row.name})))
    const commissionDate = new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date())
    return {commissionDate} as T // suggestion only; create endpoint owns the persisted business date
  }
  if (path === '/organizations/query' && method === 'POST') {
    const page = Math.max(1,Number(query.page)||1), size=Math.min(100,Math.max(1,Number(query.pageSize)||20))
    const params=new URLSearchParams({keyword:string(query.keyword),page:string(page),size:string(size)})
    const result=await platformRequest<{rows:Row[];total:number}>(`/api/customers/search?${params}`,{signal})
    if(!Array.isArray(result.rows)||!Number.isInteger(result.total)) throw new AppError('UNAVAILABLE','客户查询返回结构异常。')
    return {items:result.rows.map(row=>({id:string(row.code||row.name),name:row.name})),total:result.total,page,pageSize:size} as T
  }
  if (path === '/contracts/query' && method === 'POST') {
    if (query.from || query.to) throw new AppError('UNAVAILABLE','平台合同库接口未提供签订日期，不能以登记日期代替此筛选。')
    if (query.ownDepartment) {
      const rows = await scopedRows('/api/agreements/query',undefined,signal)
      const mapped=rows.filter(row=>row.status==='已登记' && row.department===profile.value?.dataScope.department).map(row=>({id:row.agreementNo,code:row.agreementNo,name:row.projectName,customer:row.client,projectName:row.projectName,projectAddress:row.info?.projectAddr||'',erpProjectType:row.erpProjectType||row.erpType||'',erpContract:row.erpProjectNo||'',departmentId:row.department,signedDate:'',constructionCompany:row.info?.constructionCompany||'',registrationStatus:'已登记'}))
      const {ownDepartment:_own,...filters}=query
      return pageRows(mapped,filters) as T
    }
    const result=await platformRequest<{rows:Row[]}>('/api/agreements/contract-library',{signal})
    if (!Array.isArray(result.rows)) throw new AppError('UNAVAILABLE','平台合同库返回结构异常。')
    const {ownDepartment:_own,...filters}=query
    return pageRows(result.rows.map(row=>({id:row.contractNo,code:row.contractNo,name:row.projectName,customer:row.client,projectName:row.projectName,projectAddress:row.projectAddr,erpProjectType:row.erpType||row.category,erpContract:row.projectCode||'',departmentId:row.bizDept||'',signedDate:'',constructionCompany:'',registrationStatus:'已登记'})),filters) as T
  }
  const saveMatch = /^\/commissions(?:\/(\d+))?$/.exec(path)
  if(saveMatch && (method === 'PUT' || method === 'POST')) {
    if(!query.input || (method==='PUT' && !saveMatch[1]) || (method==='POST' && saveMatch[1])) throw new AppError('BAD_REQUEST','委托保存协议不合法。')
    const id=saveMatch[1], previous=id?commissionSnapshots.get(`${profile.value?.account || ''}:${id}`):undefined
    if(id && !previous) throw new AppError('VERSION_CONFLICT','请重新打开委托后保存，避免丢失平台扩展字段。')
    const result=await platformRequest<Row>(id?`/api/entrust/${id}`:'/api/entrust/create',{method,body:commissionPayload(query.input,previous),signal})
    return mapCommission(result) as T
  }
  const actionMatch=/^\/commissions\/(\d+)\/actions$/.exec(path)
  if(actionMatch && method==='POST' && ['complete','uncomplete'].includes(query.actionId)) {
    const result=await platformRequest<Row>(`/api/entrust/${actionMatch[1]}/${query.actionId}`,{method:'POST',body:{},signal})
    return mapCommission(result) as T
  }
  const commissionMatch = /^\/commissions\/([^/]+)(?:\/summary)?$/.exec(path)
  if (commissionMatch && method === 'GET') {
    const id = decodeURIComponent(commissionMatch[1]!)
    if (!/^\d+$/.test(id)) throw new AppError('BAD_REQUEST', '委托标识必须使用平台返回的数字 ID。')
    const row = await platformRequest<Row>(`/api/entrust/${id}`,{signal})
    if (!row) throw new AppError('NOT_FOUND', '委托不存在或不在当前账号的数据范围内。')
    return mapCommission(row) as T
  }
  let binding = listBindings[path]
  if (path === '/samples/query' && query.workspace === 'review') binding = { path: '/api/reports/query', view: 'contract_review', entity: 'sample' }
  if (path === '/samples/query' && query.workspace === 'query') binding = { path: '/api/reports/query', view: 'query', entity: 'sample' }
  if (path === '/samples/report-check/query') {
    // The platform removed the separate check stage. 'interim_report' means
    // 中间报告 and must never be substituted for the template's 报告校核.
    const views: Record<string,string> = { review: 'review', approval: 'approval' }
    if (!views[query.stage]) throw new AppError('UNAVAILABLE', '平台当前流程不支持独立报告校核节点，未代替为其他审核环节。')
    if ((query.from || query.to) && query.dateField && query.dateField !== 'commissionDate') throw new AppError('UNAVAILABLE', '平台审核列表仅提供委托日期；原链接中的检测或审核日期条件无法执行，请重新选择委托日期。')
    binding = { path: '/api/reports/query', view: views[query.stage], entity: 'sample' }
  }
  if (binding && method === 'POST') {
    const handled = new Set([...Object.keys(queryFields), 'page','pageSize','sort','direction','searchField','keyword','contains','status','from','to','commissionFrom','commissionTo','commissionId','commissionIds','ids','workspace','plans','dateField','stage'])
    for(const [key,value] of Object.entries(query)) if(!handled.has(key)&&selected(value)) throw new AppError('UNAVAILABLE', `平台尚未对齐筛选字段 ${key}，未忽略此条件。`)
    const presentation=binding.entity==='commission'?'commission':path.includes('data-entry')||path.includes('data-changes')?'entry':path.includes('flow')?'flow':path.includes('inbound')?'inbound':path.includes('outbound')?'outbound':path.includes('report-check')||path.includes('reports/')?'report':'registration-sample'
    const filters:Row={...query,fields:{...(query.fields||{})}}
    for(const [key,field]of Object.entries(queryFields))if(selected(query[key])&&!['dataStatus','sampleType','status','code'].includes(key))filters.fields[field]=query[key]
    if(query.commissionId)filters.commissionIds=[query.commissionId]
    const result=await platformRequest<{rows:Row[];total:number;page:number;pageSize:number}>(binding.path,{method:'POST',body:{...filters,serverPage:true,adapter:'platform',projection:'list',view:binding.view,presentation},signal})
    const mapRow = path === '/samples/report-check/query' ? (row: Row) => mapReportStage(row, query.stage) : binding.entity === 'commission' ? (row:Row)=>mapCommission(row,false) : mapSample
    return {items:result.rows.map(mapRow),total:result.total,page:result.page,pageSize:result.pageSize} as T
  }
  throw new AppError('UNAVAILABLE', `此操作尚未完成平台契约适配，未提交业务数据。（${method} ${path.split('?')[0]}）`)
}
