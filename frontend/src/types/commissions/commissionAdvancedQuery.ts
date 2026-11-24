import { commissionSearchFields } from './registration'
import type { RegistrationCommission } from './registration'

// Reuse the basic selector's fields and labels, excluding its aggregate "all" option.
export const commissionAdvancedFields = [
  ...commissionSearchFields.filter(field => field.value !== 'all').map(field => ({ key: field.value, label: field.label })),
  { key: 'contract', label: '合同号' },
  { key: 'projectRegistrationCode', label: '工程备案编号' },
  { key: 'projectTradingCode', label: '工程编码（交易中心）' },
] as const satisfies readonly { key: keyof RegistrationCommission; label: string }[]
export type CommissionAdvancedFields = Partial<Record<typeof commissionAdvancedFields[number]['key'], string>>
export interface CommissionAdvancedDraft {
  fields: CommissionAdvancedFields
  status: string
  useDate: boolean
  from: string
  to: string
}
