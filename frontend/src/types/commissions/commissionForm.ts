// Optional additions keep previously saved mock commissions compatible.
export interface CommissionFormDetails {
  contractId?: string
  commissionDate?: string
  erpContract?: string
  erpProjectType?: string
  contractParty?: string
  payer?: string
  customerAddress?: string
  customerLegalRepresentative?: string
  customerPhone?: string
  customerPostcode?: string
  projectRegistrationCode?: string
  projectTradingCode?: string
  projectAddress?: string
  handlingDepartmentId?: string
  handlerPhone?: string
  invoiceType?: string
  taxpayerNumber?: string
  invoiceCompany?: string
  invoiceAddress?: string
  bankName?: string
  bankAccount?: string
}

export const commissionDetailKeys = [
  'contractId', 'commissionDate', 'erpContract', 'erpProjectType', 'contractParty', 'payer',
  'customerAddress', 'customerLegalRepresentative', 'customerPhone', 'customerPostcode',
  'projectRegistrationCode', 'projectTradingCode', 'projectAddress', 'handlingDepartmentId',
  'handlerPhone', 'invoiceType', 'taxpayerNumber', 'invoiceCompany', 'invoiceAddress', 'bankName', 'bankAccount',
] as const satisfies readonly (keyof CommissionFormDetails)[]

export const registrationInvoiceTypes = ['增值税普通发票', '增值税专用发票'] as const

export function emptyCommissionDetails(): Required<CommissionFormDetails> {
  return Object.fromEntries(commissionDetailKeys.map(key => [key, key === 'invoiceType' ? registrationInvoiceTypes[0] : ''])) as Required<CommissionFormDetails>
}

export const registrationDepartments: { id: string; name: string }[] = [
  { id: 'lab', name: '实验室' },
  { id: 'lab2', name: '第二实验室' },
  { id: 'quality', name: '质量部' },
  { id: 'ops', name: '综合部' },
]

export interface RegistrationOrganization { id: string; name: string }
export interface RegistrationOrganizationQuery { keyword?: string; page?: number; pageSize?: number }

export interface RegistrationContract {
  id: string; code: string; name: string; customer: string; departmentId: string
  erpContract: string; erpProjectType: string
  signedDate: string; projectName: string; projectAddress: string; constructionCompany: string; registrationStatus: string
}

export const contractSearchFields = [
  { value: 'all', label: '全部' }, { value: 'code', label: '合同编号' }, { value: 'name', label: '合同名称' },
  { value: 'customer', label: '委托方' }, { value: 'projectName', label: '工程名称' },
  { value: 'projectAddress', label: '工程地址' }, { value: 'constructionCompany', label: '施工单位' },
  { value: 'registrationStatus', label: '登记状态' },
] as const
export interface RegistrationContractQuery {
  code?: string; keyword?: string; from?: string; to?: string; ownDepartment?: boolean
  searchField?: typeof contractSearchFields[number]['value']; page?: number; pageSize?: number
}
