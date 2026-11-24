import { describe, expect, it } from 'vitest'
import { commissionColumns, commissionCell, defaultCommissionColumns, parseCommissionColumns, sampleCell } from '../../src/services/commissions/registrationColumns'
import { seedRegistration } from '../../server/registrationDomain'
import { summaryCommission, summarySample, summaryInquirySample } from '../../server/registrationSummary'
import { inquirySampleCell } from '../../src/services/commissions/inquirySampleColumns'
import { emptySampleDetails } from '../../src/types/commissions/sampleForm'

describe('commission column settings and values', () => {
  it('maps inquiry fields to saved sample form values without guessing unresolved columns', () => {
    const record = seedRegistration().samples[0]!
    Object.assign(record, { quantity: 3, category: '校准', contact: '不可使用的根联系人', phone: '不可使用的根电话', erpContractNumber: 'KD-CONTRACT-456' })
    Object.assign(record.commissionInfo, { erpContract: 'KD-123', commissionDate: '2026-01-01', contact: '样品委托人', phone: '123456', customerAddress: '样品单位地址', name: '项目甲' })
    record.details = { ...emptySampleDetails(), testPlan: '方案乙', manufacturer: '厂家丙', samplingQuantity: '0', specification: '型号丁',
      productCode: '此编号不能推测为批号', trademark: '商标戊', inspector: '主检己', standardPrice: '0', paymentStatus: '已缴费', paidAmount: '500', reportDelivery: '快递' }
    const row = summaryInquirySample({ ...record, commissionCode: '委托编号', commissionName: '项目甲' })
    expect(row).toMatchObject({ erpContractNumber: 'KD-CONTRACT-456', commissionDate: '2026-01-01', contact: '样品委托人', phone: '123456', customerAddress: '样品单位地址',
      projectName: '项目甲', testPlan: '方案乙', manufacturer: '厂家丙', samplingQuantity: '0', specification: '型号丁', trademark: '商标戊', inspector: '主检己',
      category: '校准', quantity: 3, standardPrice: 0, paymentStatus: '已缴费', reportDelivery: '快递', discountPrice: null, actualPrice: null })
    for (const key of ['discountPrice', 'actualPrice'] as const) expect(inquirySampleCell(row, key)).toBe('—')
    for (const key of ['nextStatus', 'sampleBatch', 'sampleMaterials', 'erpContract']) expect(row).not.toHaveProperty(key)
    expect(inquirySampleCell(row, 'erpContractNumber')).toBe('KD-CONTRACT-456')
    expect(inquirySampleCell(row, 'samplingQuantity')).toBe('0')
    expect(inquirySampleCell(row, 'standardPrice')).toBe('0.00')
    expect(row).not.toHaveProperty('details'); expect(row).not.toHaveProperty('attachments')
    record.details = undefined; record.commissionInfo.commissionDate = undefined; record.erpContractNumber = undefined
    const empty = summaryInquirySample({ ...record, commissionCode: '', commissionName: '' })
    expect(inquirySampleCell(empty, 'commissionDate')).toBe('—')
    expect(inquirySampleCell(empty, 'samplingQuantity')).toBe('—')
    expect(inquirySampleCell(empty, 'trademark')).toBe('—')
    expect(inquirySampleCell(empty, 'erpContractNumber')).toBe('—')
  })
  it('reads sample plan, project and attachment presence from independent sources', () => {
    const record = seedRegistration().samples[0]!
    record.commissionInfo.name = '项目甲'
    record.details = { ...record.details!, testPlan: '检测方案乙' }
    record.attachments = []
    const summarize = () => summarySample({ ...record, commissionCode: 'WT1', commissionName: '委托名称丙' })
    expect(sampleCell(summarize(), 'projectName')).toBe('项目甲')
    expect(sampleCell(summarize(), 'testPlan')).toBe('检测方案乙')
    expect(sampleCell(summarize(), 'attachmentCount')).toBe('')
    record.attachments.push({ id: 'file1', name: '样品附件.txt', size: 1, type: 'text/plain', dataUrl: 'data:text/plain;base64,YQ==' })
    expect(sampleCell(summarize(), 'attachmentCount')).toBe('有')
    expect(summarize()).not.toHaveProperty('attachments')
    record.details.testPlan = ''
    expect(sampleCell(summarize(), 'testPlan')).toBe('—')
  })
  it('restores defaults, legacy settings and bounded canonical route selections', () => {
    expect(defaultCommissionColumns).toEqual(['code', 'owner', 'customer', 'name', 'status', 'commissionDate', 'receivableAmount'])
    expect(parseCommissionColumns(undefined)).toEqual(defaultCommissionColumns)
    expect(parseCommissionColumns(undefined, '1')).toEqual(['contract', ...defaultCommissionColumns])
    expect(parseCommissionColumns('owner,contract,owner,unknown', '1')).toEqual(['contract', 'code', 'owner'])
    expect(parseCommissionColumns('code', '1')).toEqual(['code'])
    expect(parseCommissionColumns('', '1')).toEqual(['code'])
    expect(parseCommissionColumns('unknown')).toEqual(defaultCommissionColumns)
    expect(parseCommissionColumns(['contract'])).toEqual(defaultCommissionColumns)
    expect(commissionColumns).toHaveLength(11)
  })
  it('keeps absent business values distinct from zero and never substitutes registration dates or contract parties', () => {
    const record = seedRegistration().commissions[0]!
    record.contractParty = '合同甲方不可推断为建设单位'
    record.commissionDate = undefined
    const row = summaryCommission(record)
    expect(commissionCell(row, 'commissionDate')).toBe('—')
    expect(commissionCell(row, 'constructionUnit')).toBe('—')
    expect(commissionCell(row, 'constructionCompany')).toBe('—')
    expect(commissionCell(row, 'receivableAmount')).toBe('—')
    expect(commissionCell({ ...row, receivableAmount: 0 }, 'receivableAmount')).toBe('0.00')
    expect(commissionCell({ ...row, receivableAmount: 1234.5 }, 'receivableAmount')).toBe('1234.50')
    expect(commissionCell({ ...row, receivableAmount: NaN }, 'receivableAmount')).toBe('—')
    expect(commissionCell({ ...row, commissionDate: '2026-01-02' }, 'commissionDate')).toBe('2026-01-02')
    expect(commissionCell(row, 'owner')).toBe(record.owner)
    expect(commissionCell(row, 'contact')).toBe(record.contact)
  })
})
