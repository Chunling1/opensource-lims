import type { RegistrationCommission, RegistrationCommissionRow, RegistrationSample, RegistrationSampleRow } from '../src/types/commissions/registration'

export function summaryCommission(row: RegistrationCommission, sampleCount = 0): RegistrationCommissionRow {
  const { id, code, name, customer, status, contract, owner, createdAt, version, commissionDate, contact } = row
  // Sources for these three fields are not defined yet. Do not infer from contracts or totals.
  return { id, code, name, customer, status, contract, owner, createdAt, version, commissionDate: commissionDate ?? '', contact, sampleCount,
    receivableAmount: null, constructionUnit: null, constructionCompany: null }
}

export function summarySample(row: RegistrationSample & { commissionCode: string; commissionName: string }): RegistrationSampleRow {
  const { id, code, reportCode, sampleType, dataStatus, name, customer, status, category, quantity, unit, owner, createdAt, version, commissionId, commissionCode, commissionName } = row
  const price = row.details?.standardPrice?.trim()
  return { id, code, reportCode, reviewStatus: row.reviewStatus ?? 'unreviewed', sampleType, dataStatus, name, customer, status, category, quantity, unit, owner, createdAt, version, commissionId, commissionCode, commissionName,
    commissionOwner: row.commissionInfo.owner, parameters: row.projects.join('；'), projectName: row.commissionInfo.name,
    testPlan: row.details?.testPlan || '', attachmentCount: row.attachments.length,
    standardPrice: row.reportPricing?.standardPrice ?? (price && Number.isFinite(Number(price)) ? Number(price) : null),
    // Leave unknown prices empty until a pricing result has been saved.
    discountPrice: row.reportPricing?.discountPrice ?? null, actualPrice: row.reportPricing?.amount ?? null }
}

export function summaryInquirySample(row: RegistrationSample & { commissionCode: string; commissionName: string }): RegistrationSampleRow {
  const info = row.commissionInfo, details = row.details
  return { ...summarySample(row), erpContractNumber: row.erpContractNumber || '', commissionDate: info.commissionDate || '',
    manufacturer: details?.manufacturer || '', samplingQuantity: details?.samplingQuantity || '', specification: details?.specification || '',
    trademark: details?.trademark || '', inspector: details?.inspector || '', paymentStatus: details?.paymentStatus || '', reportDelivery: details?.reportDelivery || '',
    contact: info.contact || '', phone: info.phone || '', customerAddress: info.customerAddress || '' }
}
