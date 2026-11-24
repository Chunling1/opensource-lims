import type { Actor } from '../lims'
import type { TableColumn } from '../common/table'
import type { RegistrationContract } from '../commissions/commissionForm'
export interface CustomerAccountDraft { name: string; postcode: string; address: string; contact: string; mobile: string; phone: string; fax: string; email: string; notes: string; contractIds: string[] }
export interface CustomerAccount extends CustomerAccountDraft { id: string; code: string; departmentId: string }
export interface CustomerAccountDetail extends CustomerAccount { contracts: RegistrationContract[] }
export interface CustomerAccountQuery { code?: string; name?: string; page?: number; pageSize?: number; ids?: string[] }
export interface CustomerAccountPage { items: CustomerAccount[]; total: number; page: number; pageSize: number }
export interface CustomerCredential { salt: string; hash: string; mustChangePassword: boolean; resetAt: string; resetBy: string }
export const canManageCustomerAccounts = (actor: Actor) => actor.roles.some(role => ['admin', 'commissions'].includes(role))
export const emptyCustomerAccount = (): CustomerAccountDraft => ({ name: '', postcode: '', address: '', contact: '', mobile: '', phone: '', fax: '', email: '', notes: '', contractIds: [] })
export const customerAccountColumns = [
  { key: 'code', label: '客户账号', required: true }, { key: 'name', label: '客户名称', default: true, truncate: 30, fullTitle: true }, { key: 'notes', label: '备注', default: true, truncate: 40, fullTitle: true },
] as const satisfies readonly TableColumn<keyof CustomerAccount>[]
export const customerContractColumns = [
  { key: 'code', label: '合同号' }, { key: 'name', label: '合同名称' }, { key: 'customer', label: '委托方' }, { key: 'projectName', label: '工程名称' }, { key: 'projectAddress', label: '工程地址' }, { key: 'constructionCompany', label: '施工单位' }, { key: 'registrationStatus', label: '登记状态' },
] as const satisfies readonly TableColumn<keyof RegistrationContract>[]
