import { commissionDetailKeys, emptyCommissionDetails, type CommissionFormDetails } from './commissionForm'

export interface CommissionFieldsInput extends CommissionFormDetails {
  name: string; customer: string; contact: string; phone: string; contract: string
}
export interface SampleCommissionInfo extends CommissionFieldsInput { code: string; owner: string }
export const sampleCommissionKeys = ['name', 'customer', 'contact', 'phone', 'contract', ...commissionDetailKeys] as const
export function emptySampleCommission(): SampleCommissionInfo {
  return { ...emptyCommissionDetails(), code: '', owner: '', name: '', customer: '', contact: '', phone: '', contract: '' }
}
export function copySampleCommission(source: SampleCommissionInfo & { departmentId?: string; createdAt?: string }): SampleCommissionInfo {
  const copy = emptySampleCommission()
  for (const key of sampleCommissionKeys) copy[key] = source[key] ?? ''
  copy.code = source.code; copy.owner = source.owner
  copy.handlingDepartmentId = source.handlingDepartmentId || source.departmentId || ''
  copy.commissionDate = source.commissionDate ?? source.createdAt?.slice(0, 10) ?? ''
  return copy
}
