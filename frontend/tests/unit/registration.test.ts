import { sampleWorkflowDateFields } from '../../src/types/commissions/sampleWorkflow'
import { emptySampleDetails } from '../../src/types/commissions/sampleForm'
import { describe, expect, it } from 'vitest'
import { createRegistrationService, seedRegistration, registrationCsv } from '../../server/registrationDomain'
import { registrationReturn } from '../../src/services/commissions/registrationService'
import type { Actor } from '../../src/types/lims'
import type { RegistrationState, RegistrationSampleInput } from '../../src/types/commissions/registration'

const admin: Actor = { id: 'admin', name: '演示用户', roles: ['admin'], departmentId: 'lab', scope: 'all' }
function setup() {
  let actor = { ...admin }, state = seedRegistration(), rejectWrite = false
  const service = createRegistrationService({ actor: () => actor, read: () => state, write: next => { if (rejectWrite) throw new Error('disk full'); state = structuredClone(next) } })
  return { service, state: () => structuredClone(state), as: (next: Actor) => { actor = next }, change: (mutate: (s: RegistrationState) => void) => mutate(state), failWrite: () => { rejectWrite = true } }
}
const sampleInput: RegistrationSampleInput = { details: { ...emptySampleDetails(), testPlanId: 'general-1' }, name: '关联演示水样', customer: '华清环境检测中心', commissionId: 'demo-wt-1', category: '委托', quantity: 2, unit: '瓶', storage: '冷藏', contact: '张老师', phone: '', projects: ['pH 值'], notes: '' }

describe('isolated registration demo', () => {
  const attachment = { name: 'sample.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' }
  it.each([
    '委托登记中', '完成登记', '委托登记完成', '合同评审中', '评审完成', '合同评审完成',
    '样品入库中', '样品入库完成', '样品出库中', '样品出库完成', '样品待领取', '样品已领取',
    '任务分配中', '任务分配完成', '任务处理中', '任务处理完成', '检测数据录入中', '委托更改中', '检测更改中',
  ])('manages attachments in editable workflow stages: %s', async dataStatus => {
    const x = setup()
    x.change(state => { Object.assign(state.samples[0]!, { status: 'completed', reviewStatus: 'approved', dataStatus }) })
    const before = x.state().samples[0]!
    expect(await x.service.attachments(before.id, 'samples')).toMatchObject({ canManageAttachments: true })
    const added = await x.service.attach(before.id, before.version, attachment, 'samples')
    expect(added.canManageAttachments).toBe(true)
    expect(added.attachments).toHaveLength(1)
    expect(added.version).toBe(before.version + 1)
    expect(await x.service.sample(before.id)).toMatchObject({ dataStatus, attachments: added.attachments })
    const removed = await x.service.deleteAttachment(before.id, added.version, added.attachments[0]!.id, 'samples')
    expect(removed.canManageAttachments).toBe(true)
    expect(removed.attachments).toEqual([])
    expect(removed.events.at(-1)).toMatchObject({ action: '删除附件', reason: attachment.name })
    expect(x.state().samples[0]).toEqual({ ...before, version: before.version + 2, events: removed.events })
  })
  it.each([
    '检测数据录入完成', '检测数据校核中', '检测数据校核完成', '报告校核中', '报告校核完成',
    '报告审核中', '报告审核完成', '报告批准中', '报告批准完成', '报告打印中', '报告打印完成',
    '报告更改中', '报告更改审批中', '任务已取消', '终止', '样品待处置', '样品已处置', '未知状态',
  ])('keeps attachments readable but rejects writes after data entry or in inactive states: %s', async dataStatus => {
    const x = setup(), added = await x.service.attach('demo-yp-1', 1, attachment, 'samples')
    x.change(state => { Object.assign(state.samples[0]!, { status: 'completed', dataStatus }) })
    const before = x.state()
    expect(await x.service.attachments(added.id, 'samples')).toMatchObject({ canManageAttachments: false, attachments: added.attachments })
    await expect(x.service.attach(added.id, added.version, attachment, 'samples')).rejects.toThrow('检测数据录入完成前')
    await expect(x.service.deleteAttachment(added.id, added.version, added.attachments[0]!.id, 'samples')).rejects.toThrow('检测数据录入完成前')
    expect((await x.service.sample(added.id)).attachments).toEqual(added.attachments)
    expect(x.state()).toEqual(before)
  })
  it('does not substitute other event dates for missing flow facts', async () => {
    const x = setup(), query = { ids: ['demo-yp-30'], status: '样品已处置', dates: { outbound: { from: '2000-01-01', to: '2100-01-01' } } }
    expect((await x.service.flowSamples(query)).total).toBe(1)
    x.change(state => { state.samples.find(row => row.id === 'demo-yp-30')!.outboundInfo = undefined })
    expect((await x.service.flowSamples(query)).total).toBe(0)
    expect((await x.service.flowSamples({ ...query, dates: undefined })).items[0]!.outboundDate).toBe('')
  })
  it('returns and exports inbound columns from the saved sample commission and sample fields', async () => {
    const x = setup()
    x.change(state => {
      const sample = state.samples.find(row => row.id === 'demo-yp-31')!
      Object.assign(sample.commissionInfo, { customerAddress: '委托单位地址示例', contact: '委托联系人', phone: '010-12345678' })
      sample.contact = '其他联系人'; sample.phone = '其他电话'; sample.notes = '样品备注'
      sample.details = { ...emptySampleDetails(), ...sample.details, manufacturer: '生产单位示例', mailingAddress: '邮寄地址示例', internalNotes: '内部备注不应出现在备注列' }
    })
    const query = { ids: ['demo-yp-31'] }
    const result = await x.service.inboundSamples(query)
    expect(result.items).toHaveLength(1)
    expect(result.items[0]).toMatchObject({ customerAddress: '委托单位地址示例', contact: '委托联系人', phone: '010-12345678', manufacturer: '生产单位示例', notes: '样品备注', mailingAddress: '邮寄地址示例' })
    const csv = await x.service.exportInboundSamples(query)
    expect(csv.split('\r\n')[0]).toBe('\uFEFF"样品编号","委托编号","报告编号","数据状态","检测方案","样品/工程名称","委托日期","样品登记人","合同编号","委托单位","委托单位地址","委托人","委托人电话","生产单位","备注","邮寄地址"')
    for (const value of ['委托单位地址示例', '委托联系人', '010-12345678', '生产单位示例', '样品备注', '邮寄地址示例']) expect(csv).toContain(value)
    expect(csv).not.toContain('内部备注不应出现在备注列')
    expect(csv).not.toContain('其他联系人')
  })

  it('matches optional workflow dates inclusively and conclusions exactly without inventing missing facts', async () => {
    const x = setup()
    const dates = Object.fromEntries(sampleWorkflowDateFields.map(({ key }) => [key, { from: '2024-03-01', to: '2024-03-01' }]))
    expect((await x.service.samples({ sampleWorkflow: { dates } }, 'query')).total).toBe(0)
    expect((await x.service.samples({ sampleWorkflow: { conclusion: 'qualified' } }, 'query')).total).toBe(0)
    x.change(state => {
      state.samples[0]!.workflow = { ...Object.fromEntries(sampleWorkflowDateFields.map(({ key }) => [key, '2024-03-01'])), conclusion: 'qualified' }
      state.samples[1]!.workflow = { testStartDate: '2024-03-02', conclusion: 'unqualified' }
    })
    const query = { sampleWorkflow: { dates, conclusion: 'qualified' as const } }
    expect((await x.service.samples(query, 'query')).items.map(row => row.id)).toEqual(['demo-yp-1'])
    expect((await x.service.samples({ sampleWorkflow: { conclusion: 'unqualified' } }, 'query')).items.map(row => row.id)).toEqual(['demo-yp-2'])
    for (const { key } of sampleWorkflowDateFields) {
      expect((await x.service.samples({ sampleWorkflow: { dates: { [key]: { from: '2024-03-01', to: '2024-03-01' } } } }, 'query')).items.map(row => row.id)).toEqual(['demo-yp-1'])
      expect((await x.service.samples({ sampleWorkflow: { dates: { ...dates, [key]: { from: '2024-03-02', to: '2024-03-03' } } } }, 'query')).total).toBe(0)
      await expect(x.service.samples({ sampleWorkflow: { dates: { [key]: { from: '2024-02-30', to: '2024-03-01' } } } }, 'query')).rejects.toThrow('范围')
      await expect(x.service.samples({ sampleWorkflow: { dates: { [key]: { from: '2024-03-02', to: '2024-03-01' } } } }, 'query')).rejects.toThrow('范围')
    }
    expect((await x.service.samples({ ...query, sampleAdvanced: { code: 'SP2026090002' } }, 'query')).total).toBe(0)
    expect((await x.service.samples({ ...query, commissionIds: ['demo-wt-2'] }, 'query')).total).toBe(0)
    const csv = await (await x.service.export('samples', query, 'query')).text()
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).toContain('SP2026090001')
    expect((await x.service.samples({ sampleWorkflow: {} }, 'query')).total).toBe(x.state().samples.length)
    x.as({ ...admin, roles: ['samples'], scope: 'department', departmentId: 'lab2' })
    expect((await x.service.samples(query, 'query')).total).toBe(0)
  })

  it('matches all sample advanced fields on saved snapshots before pagination and export', async () => {
    const x = setup()
    x.change(state => {
      const row = state.samples[0]!
      Object.assign(row.commissionInfo, { code: 'Snapshot-ABC', name: 'Project-ABC', contract: 'Contract-ABC', projectRegistrationCode: 'Record-ABC', projectTradingCode: 'Trading-ABC', erpContract: 'Erp-ABC', customer: 'Customer-ABC', owner: 'Handler-ABC', contact: 'Contact-ABC', commissionDate: '2024-03-01' })
      Object.assign(row, { name: 'Product-ABC', owner: 'Registrar-ABC', projects: ['检测甲', 'Parameter-ABC'] })
      row.details = { ...emptySampleDetails(), manufacturer: '厂家甲；Factory-ABC', specification: 'Spec-ABC', inspector: 'Inspector-ABC' }
      row.events.push({ action: '开始合同评审', actor: 'Reviewer-ABC', at: new Date().toISOString(), reason: '' })
      state.samples[1]!.commissionInfo.commissionDate = undefined
      state.commissions[0]!.name = 'LiveProjectOnly'
    })
    const fields = { code: 'sp2026090001', reportCode: 'bg2026090001', commissionCode: 'snapshot-abc', projectName: 'project-abc', contract: 'contract-abc', projectRegistrationCode: 'record-abc', projectTradingCode: 'trading-abc', erpContract: 'erp-abc', customer: 'customer-abc', commissionOwner: 'handler-abc', contact: 'contact-abc', name: 'product-abc', owner: 'registrar-abc', projects: 'parameter-abc', manufacturer: 'factory-abc', specification: 'spec-abc', inspector: 'inspector-abc', reviewer: 'reviewer-abc' }
    const query = { sampleAdvanced: fields, commissionFrom: '2024-03-01', commissionTo: '2024-03-01' }
    expect((await x.service.samples(query, 'query')).items.map(row => row.id)).toEqual(['demo-yp-1'])
    for (const key of Object.keys(fields) as (keyof typeof fields)[]) {
      expect((await x.service.samples({ sampleAdvanced: { [key]: fields[key] } }, 'query')).total).toBe(1)
      expect((await x.service.samples({ ...query, sampleAdvanced: { ...fields, [key]: 'MissingValue' } }, 'query')).total).toBe(0)
    }
    expect((await x.service.samples({ sampleAdvanced: { projectName: 'LiveProjectOnly' } }, 'query')).total).toBe(0)
    expect((await x.service.samples({ ...query, dataStatus: '评审完成' }, 'query')).total).toBe(0)
    expect((await x.service.samples({ ...query, sampleType: '英文报告样品' }, 'query')).total).toBe(0)
    expect((await x.service.samples({ ...query, commissionIds: ['demo-wt-2'] }, 'query')).total).toBe(0)
    expect((await x.service.samples({ ...query, commissionFrom: '2024-03-02', commissionTo: '2024-03-03' }, 'query')).total).toBe(0)
    expect((await x.service.samples({ sampleAdvanced: { code: 'SP2026090002' }, commissionFrom: '2024-01-01' }, 'query')).total).toBe(0)
    expect((await x.service.samples({ sampleAdvanced: { code: 'SP2026090002' } }, 'query')).total).toBe(1)
    expect((await x.service.samples({ sampleAdvanced: {}, page: 2, pageSize: 10 }, 'query')).items).toHaveLength(10)
    const csv = await (await x.service.export('samples', query, 'query')).text()
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).toContain('SP2026090001')
    x.as({ ...admin, roles: ['samples'], scope: 'department', departmentId: 'lab2' })
    expect((await x.service.samples(query, 'query')).total).toBe(0)
  })

  it('matches commission advanced fields together with inclusive optional commission dates and export scope', async () => {
    const x = setup()
    x.change(state => {
      const row = state.commissions[0]!
      Object.assign(row, { commissionDate: '2024-03-01', projectRegistrationCode: 'Record-ABC', projectTradingCode: 'Trading-ABC' })
      state.commissions[1]!.commissionDate = undefined
    })
    const row = x.state().commissions[0]!
    const fields = { code: row.code.toLowerCase(), contact: row.contact, owner: row.owner, name: row.name, customer: row.customer, contract: row.contract.toLowerCase(), projectRegistrationCode: 'record-abc', projectTradingCode: 'trading-abc' }
    const conditions = { commissionAdvanced: fields, from: '2024-03-01', to: '2024-03-01' }
    expect((await x.service.commissions(conditions)).items.map(row => row.id)).toEqual(['demo-wt-1'])
    for (const key of Object.keys(fields) as (keyof typeof fields)[]) {
      expect((await x.service.commissions({ commissionAdvanced: { [key]: fields[key] } })).total).toBeGreaterThan(0)
      expect((await x.service.commissions({ ...conditions, commissionAdvanced: { ...fields, [key]: 'NoMatchValue' } })).total).toBe(0)
    }
    expect((await x.service.commissions({ ...conditions, from: '2024-03-02', to: '2024-03-03' })).total).toBe(0)
    expect((await x.service.commissions({ commissionAdvanced: { code: 'WT202609002' }, from: '2024-01-01' })).total).toBe(0)
    expect((await x.service.commissions({ commissionAdvanced: { code: 'WT202609002' } })).total).toBe(1)
    expect((await x.service.commissions({ commissionAdvanced: {} })).total).toBe(14)
    expect((await x.service.commissions({ commissionAdvanced: {}, page: 2, pageSize: 5 })).items).toHaveLength(5)
    const csv = await (await x.service.export('commissions', conditions, 'query')).text()
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).toContain(row.code)
    x.as({ ...admin, roles: ['commissions'], scope: 'department', departmentId: 'lab2' })
    expect((await x.service.commissions(conditions)).total).toBe(0)
  })

  it('uses OR for all basic commission content and AND for separately entered advanced fields', async () => {
    const x = setup()
    x.change(state => {
      state.commissions[0]!.name = 'MatchToken in name'
      state.commissions[1]!.customer = 'MatchToken in customer'
      state.commissions[2]!.name = 'MatchToken in name'
      state.commissions[2]!.customer = 'MatchToken in customer'
    })
    expect((await x.service.commissions({ searchField: 'all', contains: 'matchtoken', sort: 'code', direction: 'asc' })).items.map(row => row.id)).toEqual(['demo-wt-1', 'demo-wt-2', 'demo-wt-3'])
    const query = { commissionAdvanced: { name: 'matchtoken', customer: 'matchtoken' } }
    expect((await x.service.commissions(query)).items.map(row => row.id)).toEqual(['demo-wt-3'])
    expect((await x.service.commissions({ ...query, commissionAdvanced: { ...query.commissionAdvanced, owner: 'missing' } })).total).toBe(0)
    expect((await x.service.commissions({ ...query, status: '已完成' })).total).toBe(0)
    expect((await x.service.commissions({ commissionAdvanced: { name: 'matchtoken', customer: '' } })).total).toBe(2)
    const csv = await (await x.service.export('commissions', query, 'query')).text()
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).toContain('WT202609003')
  })

  it('queries inquiry fields from sample snapshots and keeps basic workspace searches unchanged', async () => {
    const x = setup()
    x.change(state => {
      const row = state.samples[0]!
      row.name = 'UniqueProductABC'
      row.owner = 'UniqueRegistrarABC'
      row.commissionInfo.owner = 'UniqueHandlerABC'
      row.commissionInfo.customer = 'UniqueCustomerABC'
      row.commissionInfo.contact = 'UniqueContactABC'
      row.details = { ...emptySampleDetails(), manufacturer: '厂家一；UniqueFactoryABC\n厂家三' }
      row.events.push({ action: '开始合同评审', actor: 'UniqueReviewerABC', at: new Date().toISOString(), reason: '' })
      state.commissions[0]!.owner = 'LiveHandlerOnly'
    })
    for (const [searchField, contains] of [
      ['commissionOwner', 'uniquehandlerabc'], ['owner', 'uniqueregistrarabc'], ['reviewer', 'uniquereviewerabc'],
      ['customer', 'uniquecustomerabc'], ['name', 'uniqueproductabc'], ['contact', 'uniquecontactabc'], ['manufacturer', 'uniquefactoryabc'],
    ] as const) {
      expect((await x.service.samples({ searchField, contains }, 'query')).items.map(row => row.id)).toEqual(['demo-yp-1'])
      expect((await x.service.samples({ searchField: 'all', contains }, 'query')).items.map(row => row.id)).toEqual(['demo-yp-1'])
    }
    expect((await x.service.samples({ searchField: 'commissionOwner', contains: 'LiveHandlerOnly' }, 'query')).total).toBe(0)
    expect((await x.service.samples({ searchField: 'all', contains: 'uniqueproductabc' })).total).toBe(0)
    expect((await x.service.samples({ searchField: 'manufacturer', contains: 'uniquefactoryabc', commissionIds: ['demo-wt-2'] }, 'query')).total).toBe(0)
    const csv = await (await x.service.export('samples', { searchField: 'manufacturer', contains: 'uniquefactoryabc' }, 'query')).text()
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).toContain('SP2026090001')
    x.change(state => state.samples[0]!.events.push({ action: '撤销评审', actor: 'DifferentActor', at: new Date().toISOString(), reason: '' }))
    expect((await x.service.samples({ searchField: 'reviewer', contains: 'UniqueReviewerABC' }, 'query')).total).toBe(0)
  })

  it('filters sample commission dates from their snapshots and excludes missing dates', async () => {
    const x = setup()
    x.change(state => {
      for (const row of state.samples) row.commissionInfo.commissionDate = ''
      state.samples[0]!.commissionInfo.commissionDate = '2024-03-01'
      state.samples[1]!.commissionInfo.commissionDate = '2024-03-02'
      state.commissions[0]!.commissionDate = '2030-01-01'
    })
    const range = { commissionFrom: '2024-03-01', commissionTo: '2024-03-01' }
    expect((await x.service.samples(range)).items.map(row => row.id)).toEqual(['demo-yp-1'])
    expect((await x.service.samples({ commissionFrom: '2024-03-02' })).total).toBe(1)
    expect((await x.service.samples({ commissionTo: '2024-03-02' })).total).toBe(2)
    expect((await x.service.samples({ commissionFrom: '', commissionTo: '' })).total).toBe(x.state().samples.length)
    const csv = await (await x.service.export('samples', range)).text()
    expect(csv.split('\r\n')).toHaveLength(2)
    expect(csv).toContain('SP2026090001')
  })

  it('seeds commission dates in the recent two weeks and copies them into sample snapshots', async () => {
    const state = seedRegistration(new Date(2028, 0, 3, 12))
    expect(state.commissions[0]!.commissionDate).toBe('2028-01-03')
    expect(state.commissions.at(-1)!.commissionDate).toBe('2027-12-21')
    expect(state.commissions.every(row => row.commissionDate! >= '2027-01-03' && row.commissionDate! <= '2028-01-03')).toBe(true)
    for (const sample of state.samples) expect(sample.commissionInfo?.commissionDate).toBe(state.commissions.find(row => row.id === sample.commissionId)!.commissionDate)
    const service = createRegistrationService({ actor: () => admin, read: () => state, write: () => {} })
    expect((await service.commissions({ from: '2027-01-03', to: '2028-01-03' })).total).toBe(14)
    state.commissions[0]!.commissionDate = undefined
    expect((await service.commissions({ from: '2027-01-03', to: '2028-01-03' })).total).toBe(13)
  })

  it('sorts and filters by commission date before pagination without substituting registration dates', async () => {
    const x = setup()
    x.change(s => { for (const row of s.commissions) row.commissionDate = undefined; for (let i = 0; i < 7; i++) s.commissions[i]!.commissionDate = `2025-01-${String(7 - i).padStart(2, '0')}` })
    const ascending = await x.service.commissions({ sort: 'commissionDate', direction: 'asc', pageSize: 5 })
    expect(ascending.items.map(row => row.id)).toEqual(['demo-wt-7', 'demo-wt-6', 'demo-wt-5', 'demo-wt-4', 'demo-wt-3'])
    const second = await x.service.commissions({ sort: 'commissionDate', direction: 'asc', page: 2, pageSize: 5 })
    expect(second.items.slice(0, 2).map(row => row.id)).toEqual(['demo-wt-2', 'demo-wt-1'])
    expect(second.items[2].commissionDate).toBeUndefined()
    const descending = await x.service.commissions({ sort: 'commissionDate', direction: 'desc', pageSize: 5 })
    expect(descending.items.map(row => row.id)).toEqual(['demo-wt-1', 'demo-wt-2', 'demo-wt-3', 'demo-wt-4', 'demo-wt-5'])
    expect((await x.service.commissions({ from: '2025-01-01', to: '2025-01-31' })).total).toBe(7)
    expect((await x.service.commissions({ from: '2026-09-18', to: '2026-09-18' })).total).toBe(0)
    expect((await x.service.commissions({ from: '2025-01-07', to: '2025-01-07' })).items.map(row => row.id)).toEqual(['demo-wt-1'])
    expect((await x.service.commissions({ from: '2025-01-07' })).total).toBe(1)
    expect((await x.service.commissions({ to: '2025-01-02' })).total).toBe(2)
    expect((await x.service.samples({ from: '2026-09-18', to: '2026-09-18' })).total).toBeGreaterThan(0)
    const selected = await (await x.service.export('commissions', { ids: ['demo-wt-1'] })).text()
    expect(selected.split('\r\n')).toHaveLength(2)
    expect(selected.split('\r\n')[0].split(',')).toHaveLength(11)
    expect(selected).toContain('"2025-01-07","—","张经理","—","—"')
    x.as({ ...admin, roles: ['commissions'], scope: 'department' })
    const scoped = await (await x.service.export('commissions', {})).text()
    expect(scoped.split('\r\n')).toHaveLength(14)
    expect(scoped).not.toContain('WT202609014')
  })
  it('filters commissions by resolved customer, contract, owner and date before pagination', async () => {
    const x = setup(), q = { keyword: '华清', contract: '2026091800000001HT', owner: '演示用户', from: '2026-09-01', to: '2026-09-18', pageSize: 5 }
    x.change(s => { for (const row of s.commissions) row.commissionDate = row.createdAt.slice(0, 10) })
    const rows = await x.service.commissions(q)
    expect(rows.total).toBe(2); expect(rows.items.every(r => r.customer.includes('华清') && r.contract === q.contract)).toBe(true)
    const page = await x.service.commissions({ sort: 'code', direction: 'asc', page: 2, pageSize: 5 })
    expect(page.items[0].id).toBe('demo-wt-6'); expect(page.items).toHaveLength(5)
  })
  it('filters samples by the actual association and maintains independent status and pagination', async () => {
    const x = setup(), rows = await x.service.samples({ commissionId: 'demo-wt-1', status: 'pending' })
    expect(rows.total).toBeGreaterThan(0); expect(rows.items.every(s => s.commissionId === 'demo-wt-1' && s.status === 'pending')).toBe(true)
    expect((await x.service.samples({ keyword: '华清' })).total).toBe(0)
    expect((await x.service.samples({ page: 999, pageSize: 20 })).page).toBe(Math.ceil(x.state().samples.length / 20))
    await expect(x.service.samples({ from: '2026-10-01', to: '2026-09-01' })).rejects.toThrow('日期范围')
  })
  it('enforces department scope for reads, exports and related commission information', async () => {
    const x = setup(); x.change(s => { s.samples[0].commissionId = 'demo-wt-14' })
    x.as({ ...admin, id: 'business', roles: ['commissions', 'samples'], scope: 'department' })
    expect((await x.service.commissions()).total).toBe(13)
    const row = await x.service.sample('demo-yp-1'); expect(row.commissionId).toBe(''); expect(row.commissionCode).toBe('')
    await expect(x.service.commission('demo-wt-14')).rejects.toThrow('不可访问')
    const csv = await (await x.service.export('samples', {})).text(); expect(csv).not.toContain('WT202609014')
  })
  it('exports all matching pages or explicit selected IDs, never only the displayed page', async () => {
    const x = setup(), all = await (await x.service.export('samples', { page: 2, pageSize: 10 })).text()
    expect(all.split('\r\n')).toHaveLength(x.state().samples.length + 1)
    const selected = await (await x.service.export('samples', { ids: ['demo-yp-2', 'demo-yp-60'] })).text()
    expect(selected.split('\r\n')).toHaveLength(3); expect(selected).toContain('SP2026090060')
    expect(registrationCsv([['=1+1', 'a"b', 'a,b']])).toContain('"\'=1+1","a""b","a,b"')
  })
  it('creates a sample and its association atomically and requires a parent commission', async () => {
    const x = setup(), before = x.state().samples.length
    const saved = await x.service.saveSample(sampleInput)
    expect(saved.commissionId).toBe('demo-wt-1'); expect(saved.status).toBe('pending'); expect(saved.version).toBe(1)
    expect(x.state().samples).toHaveLength(before + 1)
    await expect(x.service.saveSample({ ...sampleInput, commissionId: '' })).rejects.toThrow('所属委托')
    expect(x.state().samples).toHaveLength(before + 1)
  })
  it('allows independent sample customer information without changing the parent', async () => {
    const x = setup(); x.change(s => { s.commissions[0].customer = '手工填写单位' })
    const saved = await x.service.saveSample({ ...sampleInput, customer: '手工填写单位' })
    expect(saved.customer).toBe('手工填写单位')
    const independent = await x.service.saveSample({ ...sampleInput, customer: '另一家单位' })
    expect(independent.commissionInfo.customer).toBe('另一家单位')
    expect((await x.service.commission('demo-wt-1')).customer).toBe('手工填写单位')
  })
  it('rolls back invalid associations and storage failures without creating an orphan sample', async () => {
    const x = setup(), before = x.state()
    await expect(x.service.saveSample({ ...sampleInput, commissionId: 'demo-wt-5' })).rejects.toThrow('只能关联')
    await expect(x.service.saveSample({ ...sampleInput, commissionId: 'missing' })).rejects.toThrow('不可访问')
    await expect(x.service.saveSample({ ...sampleInput, projects: ['微生物'] })).rejects.toThrow('一致')
    expect(x.state()).toEqual(before)
    x.failWrite(); await expect(x.service.saveSample(sampleInput)).rejects.toThrow('disk full'); expect(x.state()).toEqual(before)
  })
  it('does not expand write or link permissions', async () => {
    const x = setup(); x.as({ ...admin, roles: ['commissions'] })
    await expect(x.service.saveSample(sampleInput)).rejects.toThrow('关联委托的权限')
    await expect(x.service.saveSample({ ...sampleInput, commissionId: '' })).rejects.toThrow('所属委托')
    x.as({ ...admin, roles: ['finance'] })
    await expect(x.service.samples()).rejects.toThrow('无权')
    await expect(x.service.act('commissions', 'demo-wt-1', 'complete', 1)).rejects.toThrow('不允许')
  })
  it('allows old versions while completed samples remain read-only', async () => {
    const x = setup(), s = await x.service.sample('demo-yp-1')
    await x.service.act('samples', s.id, 'complete', s.version)
    await expect(x.service.saveSample({ ...sampleInput, commissionId: s.commissionId }, s.id, 2)).rejects.toThrow('不可修改')
    const another = await x.service.sample(s.id)
    await x.service.act('samples', another.id, 'uncomplete', s.version)
    expect((await x.service.sample(another.id)).status).toBe('pending')
  })
  it('submits a void application with a reason and blocks further writes while awaiting approval', async () => {
    const x = setup(), row = await x.service.sample('demo-yp-1')
    await expect(x.service.act('samples', row.id, 'void', row.version)).rejects.toThrow('申请作废原因')
    const result = await x.service.act('samples', row.id, 'void', row.version, '重复登记')
    expect(result.status).toBe('void_pending')
    expect(result).toMatchObject({ dataStatus: '作废申请中', voidApplication: { reason: '重复登记', previousStatus: 'pending', previousDataStatus: row.dataStatus } })
    expect((await x.service.sample(row.id)).voidApplication?.appliedBy.id).toBe('admin')
    expect(result.events.at(-1)).toMatchObject({ action: '提交作废申请', reason: '重复登记' })
    expect((await x.service.sample(row.id)).status).toBe('void_pending')
    await expect(x.service.printSource('samples', row.id)).rejects.toThrow('仅可查看')
    expect((await x.service.sample('demo-yp-3')).status).toBe('pending')
    await expect(x.service.act('samples', row.id, 'void', result.version, '再次申请')).rejects.toThrow('不允许')
    await expect(x.service.act('samples', row.id, 'complete', result.version)).rejects.toThrow('不允许')
    await expect(x.service.act('samples', row.id, 'uncomplete', result.version)).rejects.toThrow('不允许')
    await expect(x.service.saveSample({ ...sampleInput }, row.id, result.version)).rejects.toThrow('不可修改')
  })
  it('completes and reopens only one commission with scope, version and edit guards', async () => {
    const x = setup(), before = await x.service.commission('demo-wt-1')
    x.change(s => { s.commissions[0].openTasks = 1; s.commissions[0].completedReports = 0 })
    const completed = await x.service.act('commissions', before.id, 'complete', before.version)
    expect(completed.status).toBe('已完成')
    expect(completed.events.at(-1)?.action).toBe('完成')
    expect((await x.service.commission('demo-wt-2')).status).toBe('未完成')
    await expect(x.service.saveCommission(before, before.id, completed.version)).rejects.toThrow('不可修改')
    await expect(x.service.saveSample(sampleInput)).rejects.toThrow('只能关联未完成')
    const reopened = await x.service.act('commissions', before.id, 'uncomplete', before.version)
    expect(reopened.status).toBe('未完成'); expect(reopened.events.at(-1)?.action).toBe('取消完成')
    expect((await x.service.saveCommission(before, before.id, reopened.version)).status).toBe('未完成')
    expect((await x.service.saveSample(sampleInput)).commissionId).toBe(before.id)
    await expect(x.service.act('commissions', 'demo-wt-2', 'submit', 1)).rejects.toThrow('不允许')
    await expect(x.service.act('commissions', 'demo-wt-2', 'uncomplete', 1)).rejects.toThrow('不允许')
    x.as({ ...admin, roles: ['commissions'], scope: 'department' })
    await expect(x.service.act('commissions', 'demo-wt-14', 'uncomplete', 1)).rejects.toThrow('不可访问')
  })
  it('lets new commissions select sample projects when no commission project list is defined', async () => {
    const x = setup(), source = await x.service.commission('demo-wt-1')
    const created = await x.service.saveCommission({ ...source, projects: [] })
    expect(created.status).toBe('未完成')
    const sample = await x.service.saveSample({ ...sampleInput, commissionId: created.id, projects: ['微生物'] })
    expect(sample.projects).toEqual(['微生物'])
    await expect(x.service.saveSample({ ...sampleInput, commissionId: created.id, projects: ['不存在的检测项目'] })).rejects.toThrow('有效检测项目')
  })
  it('preserves completed references while refusing unsafe returns', async () => {
    expect(registrationReturn('/commissions/registration?cPage=2')).toBe('/commissions/registration?cPage=2')
    for (const value of ['//evil.test', '/samples', '/commissions/registration/commissions/new', '/commissions/registration?x=\n']) expect(registrationReturn(value)).toBe('/commissions/registration')
    const x = setup()
    await expect(x.service.attach('demo-wt-5', 1, { name: 'test.txt', type: 'text/plain', dataUrl: 'data:text/plain;base64,YQ==', size: 1 })).rejects.toThrow('已完成')
  })
})
