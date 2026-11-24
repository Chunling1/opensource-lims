// 鉴权服务：默认走内置 mock；当 VITE_USE_BACKEND=1 时改走真实 Flask 后端。
// 后端按账号返回权限点、动作权限和数据范围，前端只负责按返回结果渲染。
import { modules } from '@/data/modules'
import { clearAccessToken, request, setAccessToken } from './http'

// 是否接入真实后端（由 .env / 命令行 VITE_USE_BACKEND 控制）
export const USE_BACKEND = true

export interface PublicSystemStatus {
  businessReadOnly: boolean
  deploymentRole: 'standard' | 'validation'
  environmentLabel: string
  releaseId: string
}

export function fetchPublicSystemStatus(): Promise<PublicSystemStatus> {
  return request<PublicSystemStatus>('/api/public/v1/system/status')
}

export interface DataScope {
  department: string
  scopeType: 'all' | 'department' | 'self' | 'authorization' | 'department_project'
  description: string
}

export interface AuthResponse {
  account: string
  userName: string
  roleKey: string
  roleName: string
  homePath: string
  dataScope: DataScope
  permissions: string[]
  actionPermissions: string[]
  features?: {
    stageSigning?: boolean
    aiAssistant?: boolean
    aiVoice?: boolean
    bimCadExperiment?: boolean
    businessDataCorrection?: boolean
    fullPlatformAuthority?: boolean
    businessReadOnly?: boolean
    deploymentRole?: 'standard' | 'validation'
    environmentLabel?: string
    externalSideEffectsEnabled?: boolean
  }
}

const allPermissions = modules.flatMap((module) => [
  module.permission,
  ...module.pages.map((page) => page.permission),
])

const allActionPermissions = [
  'report.review.pass',
  'report.review.return',
  'report.approval.pass',
  'report.approval.return',
  'report.print.pass',
  'report.print.return',
  'report.attachment.upload',
  'report.pdf.merge',
  'report.pdf.preview',
  'report.pdf.download',
]

const accountProfiles: Record<string, Omit<AuthResponse, 'account'>> = import.meta.env.VITE_USE_BACKEND === '1' ? {} : {
  shouli: {
    userName: '受理小张',
    roleKey: 'acceptance',
    roleName: '受理人员',
    homePath: '/inspection/entrust/registration',
    dataScope: {
      department: '市场受理科',
      scopeType: 'self',
      description: '仅查看本人登记的委托单',
    },
    permissions: [
      'dashboard.view',
      'entrust.view',
      'entrust.registration.view',
      'entrust.contract_review.view',
      'entrust.query.view',
      'entrust.change.view',
      'entrust.void_approval.view',
      'report.view',
      'report.query.view',
      'online_entrust.view',
      'online_entrust.application.view',
      'online_entrust.query.view',
    ],
    actionPermissions: ['report.pdf.preview'],
  },
  yangpin: {
    userName: '样品老周',
    roleKey: 'sample_admin',
    roleName: '样品管理员',
    homePath: '/inspection/sample/inbound',
    dataScope: {
      department: '样品库',
      scopeType: 'department',
      description: '仅查看本库房在管样品',
    },
    permissions: [
      'dashboard.view',
      'sample.view',
      'sample.inbound.view',
      'sample.outbound.view',
      'sample.disposal.view',
      'sample.flow_query.view',
      'testing.view',
      'testing.task_query.view',
    ],
    actionPermissions: [],
  },
  jiance: {
    userName: '李主检',
    roleKey: 'tester',
    roleName: '检测人员',
    homePath: '/inspection/testing/data_entry',
    dataScope: {
      department: '建材检测室',
      scopeType: 'self',
      description: '仅查看本人承担的检测任务和报告',
    },
    permissions: [
      'dashboard.view',
      'sample.view',
      'sample.flow_query.view',
      'testing.view',
      'testing.assignment.view',
      'testing.sample_pickup.view',
      'testing.task_query.view',
      'testing.data_entry.view',
      'testing.data_check.view',
      'testing.data_change.view',
      'testing.completed_sample_handling.view',
      'report.view',
      'report.query.view',
    ],
    actionPermissions: [
      'report.attachment.upload',
      'report.pdf.merge',
      'report.pdf.preview',
    ],
  },
  shenhe: {
    userName: '审核陈工',
    roleKey: 'reviewer',
    roleName: '报告审核人',
    homePath: '/inspection/report/review',
    dataScope: {
      department: '建材检测室',
      scopeType: 'department',
      description: '仅查看本科室提交的待处理报告',
    },
    permissions: [
      'dashboard.view',
      'entrust.view',
      'entrust.query.view',
      'sample.view',
      'sample.flow_query.view',
      'testing.view',
      'testing.task_query.view',
      'report.view',
      'report.review.view',
      'report.query.view',
      'report.interim_report.view',
      'statistics.view',
      'statistics.record_query.view',
    ],
    actionPermissions: [
      'report.review.pass',
      'report.review.return',
      'report.pdf.preview',
      'report.pdf.download',
    ],
  },
  jiance2: {
    userName: '王主检',
    roleKey: 'tester',
    roleName: '检测人员',
    homePath: '/inspection/testing/data_entry',
    dataScope: {
      department: '结构检测室',
      scopeType: 'self',
      description: '仅查看本人承担的检测任务和报告',
    },
    permissions: [
      'dashboard.view',
      'sample.view',
      'sample.flow_query.view',
      'testing.view',
      'testing.assignment.view',
      'testing.sample_pickup.view',
      'testing.task_query.view',
      'testing.data_entry.view',
      'testing.data_check.view',
      'testing.data_change.view',
      'testing.completed_sample_handling.view',
      'report.view',
      'report.query.view',
    ],
    actionPermissions: [
      'report.attachment.upload',
      'report.pdf.merge',
      'report.pdf.preview',
    ],
  },
  shenhe2: {
    userName: '审核孙工',
    roleKey: 'reviewer',
    roleName: '报告审核人',
    homePath: '/inspection/report/review',
    dataScope: {
      department: '结构检测室',
      scopeType: 'department',
      description: '仅查看本科室提交的待处理报告',
    },
    permissions: [
      'dashboard.view',
      'entrust.view',
      'entrust.query.view',
      'sample.view',
      'sample.flow_query.view',
      'testing.view',
      'testing.task_query.view',
      'report.view',
      'report.review.view',
      'report.query.view',
      'report.interim_report.view',
      'statistics.view',
      'statistics.record_query.view',
    ],
    actionPermissions: [
      'report.review.pass',
      'report.review.return',
      'report.pdf.preview',
      'report.pdf.download',
    ],
  },
  pizhun: {
    userName: '批准赵总工',
    roleKey: 'approver',
    roleName: '报告批准人',
    homePath: '/inspection/report/approval',
    dataScope: {
      department: '报告中心',
      scopeType: 'authorization',
      description: '仅查看授权签字范围内待批准报告',
    },
    permissions: [
      'dashboard.view',
      'report.view',
      'report.approval.view',
      'report.query.view',
      'statistics.view',
      'statistics.release_status.view',
    ],
    actionPermissions: [
      'report.approval.pass',
      'report.approval.return',
      'report.pdf.preview',
      'report.pdf.download',
    ],
  },
  dayin: {
    userName: '发放小钱',
    roleKey: 'printer',
    roleName: '打印发放员',
    homePath: '/inspection/report/print',
    dataScope: {
      department: '报告中心',
      scopeType: 'all',
      description: '查看全院待签发报告',
    },
    permissions: [
      'dashboard.view',
      'report.view',
      'report.print.view',
      'report.query.view',
    ],
    actionPermissions: [
      'report.print.pass',
      'report.print.return',
      'report.pdf.preview',
      'report.pdf.download',
    ],
  },
  caiwu: {
    userName: '财务小刘',
    roleKey: 'finance',
    roleName: '财务人员',
    homePath: '/inspection/finance/pricing',
    dataScope: {
      department: '财务科',
      scopeType: 'all',
      description: '查看全院费用、收款与结算数据',
    },
    permissions: [
      'dashboard.view',
      'entrust.view',
      'entrust.query.view',
      'finance.view',
      'finance.pricing.view',
      'finance.payment_registration.view',
      'finance.payment_confirmation.view',
      'finance.invoice.view',
      'finance.settlement.view',
      'finance.finance_reports.view',
      'finance.finance_statistics.view',
      'finance.account_refund.view',
      'statistics.view',
      'statistics.test_output_value.view',
    ],
    actionPermissions: [],
  },
  admin: {
    userName: '系统管理员',
    roleKey: 'admin',
    roleName: '系统管理员',
    homePath: '/inspection/dashboard',
    dataScope: {
      department: '信息中心',
      scopeType: 'all',
      description: '不受数据范围限制',
    },
    permissions: allPermissions,
    actionPermissions: allActionPermissions,
    features: { bimCadExperiment: true },
  },
}

export const demoAccounts = Object.entries(accountProfiles).map(([account, profile]) => ({
  account,
  roleName: profile.roleName,
}))

export function mockLogin(account: string, password: string): Promise<AuthResponse> {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const profile = accountProfiles[account.trim()]
      if (!profile || !password) {
        reject(new Error('账号或密码错误'))
        return
      }
      resolve({ account: account.trim(), ...profile })
    }, 300)
  })
}

// 模拟后端按数据范围过滤报告清单：对应 POST /api/reports/query
export function filterReportsByScope<T extends { department: string; owner: string; status: string }>(
  rows: T[],
  scope: DataScope,
  userName: string,
): T[] {
  switch (scope.scopeType) {
    case 'all':
      return rows
    case 'self':
      return rows.filter((row) => row.owner === userName)
    case 'authorization':
      return rows.filter((row) => row.status === '待批准')
    case 'department':
    default:
      return rows.filter((row) => row.department === scope.department)
  }
}

// ---------- 真实后端调用（USE_BACKEND 时启用）----------

interface BackendAuth extends AuthResponse {
  token: string
  tokenType: string
}

async function backendLogin(account: string, password: string, captcha = {}): Promise<AuthResponse> {
  const data = await request<BackendAuth>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ account: account.trim(), password, ...captcha }),
  })
  setAccessToken(data.token)
  return data
}

export function fetchAuthProfile(): Promise<AuthResponse> {
  return request<AuthResponse>('/api/auth/profile', { signal: AbortSignal.timeout(10000) })
}

// 首次登录/主动改密（流程图 #1）
export function changePasswordRequest(account: string, oldPassword: string, newPassword: string, captcha = {}) {
  return request<null>('/api/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ account: account.trim(), oldPassword, newPassword, ...captcha }),
  })
}

export interface ReportRow {
  reportNo: string
  sampleNo: string
  entrustNo?: string
  project: string
  client: string
  template: string
  version: string
  status: string
  sign: string
  deadline: string
  department: string
  owner: string
  outOfScope?: boolean
  scopeStatus?: string
  outOfScopeNote?: string
  sampleStatus?: string
  stamped?: boolean
  returnInfo?: { source?: string; by?: string; date?: string; note?: string } | null
  sampleRegState?: string
  archiveState?: string
  distributionComplete?: boolean
  voided?: boolean
  dataStatus?: string
  projectName?: string
  erpProjectNo?: string
  erpProjectType?: string
  erpContractNo?: string
  handler?: string
  handlerDepartment?: string
  registrar?: string
  sampleOrProjectName?: string
  testItems?: string
  schemeName?: string
  amount?: string
  reportCategory?: string
  reportFormat?: string
  testCategory?: string
  sampleRegisteredAt?: string
  sendDate?: string
  reportTitle?: string
  sealRequirement?: string
  samplingUnit?: string
  sampler?: string
  samplingTime?: string
  consignor?: string
  consignorPhone?: string
  clientAddress?: string
  reviewer?: string
  reviewedAt?: string
  dataEntryCompletionAccount?: string
  dataEntryCompletionUserName?: string
  allowedActions?: string[]
  todoView?: string
  rowProjection?: 'active' | 'recall'
}

export type ReportListView = 'dashboard' | 'query' | 'contract_review' | 'data_entry' | 'data_change'
  | 'review' | 'interim_report' | 'approval' | 'print' | 'release' | 'archive' | 'change_request'

async function backendReports(view: ReportListView): Promise<ReportRow[]> {
  const data = await request<{ rows: ReportRow[]; total: number }>('/api/reports/query', {
    method: 'POST',
    body: JSON.stringify({ view }),
  })
  return data.rows
}

export interface ReportDetailData {
  department?: string
  reportCategory?: string
  mainReportNo?: string
  derivedFrom?: string
  requestedSeal?: string
  editVersion?: number
  testEditVersion?: string
  testDataReviewRequired?: { fields: string[]; message: string }
  erpContractNo?: string
  projectName: string
  summary: { title: string; fields: [string, string][] }[]
  checks: { group: string; status: string; type: 'success' | 'warning' | 'danger'; items: [string, string][] }[]
  attachments: { name: string; type: string; source: string; status: string }[]
  entrustSnapshot?: import('./pipeline').EntrustSnapshot
  rawSample?: Record<string, unknown>
  checkInput?: Record<string, unknown>
  reportPages?: import('./pipeline').ReportPageItem[]
}

// ---------- mock 模式的报告流转持久化（localStorage）----------

const MOCK_STATUS_KEY = 'hn_report_status'
// 报告流转：动作 → 流转后状态（与后端 NODE_FLOW 保持一致）
const MOCK_FLOW: Record<string, string> = {
  'report.review.pass': '待批准',
  'report.approval.pass': '待打印',
  'report.print.pass': '待发放',
  'report.distribution.complete': '已发放',
  'report.contract_review.undo': '待合同评审',
  'report.report_check.undo': '检测录入中',
  'report.review.undo': '待审核',
  'report.approval.undo': '待批准',
  'report.print.undo': '待打印',
}

function loadMockStatus(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(MOCK_STATUS_KEY) || '{}')
  } catch {
    return {}
  }
}
function setMockStatus(reportNo: string, status: string) {
  const map = loadMockStatus()
  map[reportNo] = status
  localStorage.setItem(MOCK_STATUS_KEY, JSON.stringify(map))
}

// 报告流转：后端模式调 /api/reports/<no>/action 落库；mock 模式按流转表算新状态并存 localStorage。
// 两种模式都返回最新状态，刷新后保留。
export interface ReportActionResult {
  esignPending?: boolean
  message?: string
  reportNo: string
  status: string
  dataStatus?: string
  outOfScope?: boolean
  scopeStatus?: string
  outOfScopeNote?: string
  sampleStatus?: string
  stamped?: boolean
  returnPlan?: {
    mode: 'entrust_only' | 'data_only' | 'entrust_and_data'
    targetLabel: string
    afterContractReview?: 'review' | 'data_change'
    afterDataChange?: 'review'
    skipSampleFlow?: boolean
  } | null
}

export async function reportAction(
  reportNo: string,
  action: string,
  payload: object = {},
): Promise<ReportActionResult | null> {
  if (USE_BACKEND) {
    return request<ReportActionResult>(`/api/reports/${reportNo}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, ...payload }),
    })
  }
  let status: string | null = null
  if (action.endsWith('.pass')) status = MOCK_FLOW[action] ?? null
  else if (action.endsWith('.undo')) status = MOCK_FLOW[action] ?? null
  // 退回统一回到检测人员，需重新上传报告与原始记录
  else if (action.endsWith('.return')) status = '退回待重传'
  if (!status) return null
  setMockStatus(reportNo, status)
  return { reportNo, status }
}

// 统一入口：登录与报告清单，按 USE_BACKEND 切换真实后端 / mock
export function loginRequest(account: string, password: string, captcha = {}): Promise<AuthResponse> {
  return USE_BACKEND ? backendLogin(account, password, captcha) : mockLogin(account, password)
}

export function logoutRequest() {
  clearAccessToken()
}

export async function fetchReportRows<T extends ReportRow>(
  mockRows: T[],
  scope: DataScope,
  userName: string,
  view: ReportListView = 'query',
): Promise<ReportRow[]> {
  if (USE_BACKEND) return backendReports(view)
  // 先套用 localStorage 中的流转状态，再按数据范围过滤（authorization 范围依赖最新状态）
  const overrides = loadMockStatus()
  // 兼容旧版本遗留的"已退回"死状态 → 迁移为"退回待重传"，使其能被检测人员接手
  let migrated = false
  for (const key of Object.keys(overrides)) {
    if (overrides[key] === '已退回') {
      overrides[key] = '退回待重传'
      migrated = true
    }
  }
  if (migrated) localStorage.setItem(MOCK_STATUS_KEY, JSON.stringify(overrides))
  const withStatus = mockRows.map((row) => ({ ...row, status: overrides[row.reportNo] ?? row.status }))
  return filterReportsByScope(withStatus, scope, userName)
}
