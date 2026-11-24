import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

test('real IndexedDB workflow produces a downloadable Chinese PDF and isolated identities', async ({ page }) => {
  test.setTimeout(90000)
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message))
  await page.goto('/#/dashboard'); await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
  const reportId = await page.evaluate(async () => {
    const servicePath = '/src/services/business/limsService.ts', sessionPath = '/src/stores/session.ts', modulesPath = '/src/services/business/modules.ts', samplePath = '/src/services/samples/sampleService.ts'
    const { limsService: service } = await import(servicePath), { switchIdentity } = await import(sessionPath), { moduleMap, initialFields } = await import(modulesPath), { sampleService } = await import(samplePath)
    const create = (kind: string, name: string, data: object) => service.save(kind, { name, data: { ...initialFields(moduleMap[kind]), ...data } })
    const act = async (kind: string, id: string, action: string, data = {}) => { const { record } = await service.detail(kind, id); return service.act(kind, id, action, record.version, '端到端核验', data) }
    const approve = async (id: string, actor = 'reviewer') => { await switchIdentity(actor); const approval = (await service.approvals()).find((p: { entityId: string; status: string }) => p.entityId === id && p.status === 'pending'); await service.decide(approval.id, true, '审核通过'); await switchIdentity('admin') }
    const order = await create('commissions', '端到端委托', { customerId: 'customer-0', projectIds: ['project-0'], source: '客户送样', settlement: '预付', discount: 0, taxRate: 0, dueDate: '2099-01-01', requirements: '水质检测' }); await act('commissions', order.id, 'submit'); await approve(order.id)
    const sample = (await sampleService.list({ customer: '华清环境检测中心', status: 'received' })).items[0]
    const link = await create('sampleLinks', '关联样品', { sampleId: sample.id, commissionId: order.id }); await act('sampleLinks', link.id, 'link')
    const movement = await create('movements', '入库', { sampleId: sample.id, operation: '入库', locationId: 'location-1', quantity: 1, assigneeId: 'admin', destination: '冷藏' }); await act('movements', movement.id, 'post')
    const task = await create('tasks', '水质检测任务', { commissionId: order.id, sampleId: sample.id, projectId: 'project-0', methodId: 'method-0', assigneeId: 'admin', equipmentId: 'equipment-1', consumption: 0, dueDate: '2099-01-01' }); await act('tasks', task.id, 'assign', { assigneeId: 'admin' }); await act('tasks', task.id, 'start'); await act('tasks', task.id, 'record', { resultType: '定量', rawValue: 7.2, qualitative: '', rawRecord: '测量稳定', qc: '通过', recordField0: '23', recordField1: '已完成', recordTable: '[["7.2","稳定"]]' }); await act('tasks', task.id, 'submit'); await approve(task.id)
    const report = await create('reports', '正式检测报告', { commissionId: order.id, templateId: 'template-1', conclusion: '所检项目符合要求' }); await act('reports', report.id, 'submit'); await approve(report.id); await switchIdentity('reviewer'); await act('reports', report.id, 'sign'); await approve(report.id, 'approver')
    await switchIdentity('finance'); const payment = await create('payments', '测试收款', { commissionId: order.id, amount: 100, method: '银行转账', reference: 'P1', paidDate: '2026-09-17' }); await act('payments', payment.id, 'post'); await switchIdentity('admin'); await act('reports', report.id, 'release')
    return report.id as string
  })
  const download = page.waitForEvent('download')
  await page.evaluate(async id => {
    const path = '/src/services/reports/reportPdf.ts'
    const { generateReportPdf, downloadBlob } = await import(path)
    downloadBlob(await generateReportPdf(id), 'report.pdf')
  }, reportId)
  const result = await download
  const bytes = await readFile((await result.path())!); expect(bytes.subarray(0, 4).toString()).toBe('%PDF'); expect(bytes.length).toBeGreaterThan(10000)
  await page.goto('/#/identity'); await page.getByRole('button', { name: '第二实验室检测员', exact: true }).click()
  const denied = await page.evaluate(async id => {
    const path = '/src/services/business/limsService.ts'
    const { limsService } = await import(path)
    try { await limsService.detail('reports', id); return false }
    catch (error) { return (error as { code?: string }).code === 'FORBIDDEN' }
  }, reportId)
  expect(denied).toBe(true)
  await page.goto('/#/identity'); await page.getByRole('button', { name: '演示用户', exact: true }).click()
  expect(errors).toEqual([])
})
