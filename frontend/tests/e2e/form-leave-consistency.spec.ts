import { test, expect } from '@playwright/test'
import { toolbarButton } from './helpers/toolbar'
const cases = [
  ['equipment/consumables', '易耗品', '新增易耗品', '物质名称'],
  ['equipment/maintenance-costs', '设备维护费用', '新增设备维护费用', '维护项目'],
  ['equipment/types', '设备类型', '新增设备类型', '设备类型'],
  ['standards/groups', '标准分组定义', '新增标准分组', '列表项值'],
  ['standards/library', '检测标准基础信息库', '新增检测标准基础信息', '标准名称'],
  ['environment', '检测试验环境', '新增试验环境', '试验环境描述'],
  ['requests', '日常事务申请', '新增申请', '办理事由'],
  ['documents/library', '文件基础信息库', '新增文件基础信息', '文件名称'],
  ['documents/monitoring', '质量监控计划', '新增质量监控计划', '文件名称'],
  ['personnel/registration', '人员登记', '新增人员', '姓名'],
  ['equipment/ledger', '设备台账', '新增设备', '仪器设备名称'],
] as const
for (const [path, label, title, field] of cases) test(`${label}: unchanged, reverted, canceled and abandoned edits`, async ({ page }) => {
  await page.request.post('/api/registration/session')
  await page.goto(`/#/quality/${path}`)
  await expect(page.getByRole('table', { name: `${label}列表`, exact: true }).locator('tbody tr').first()).toBeVisible()
  const open = async () => { await expect(page.locator('.modal-backdrop')).toHaveCount(0); await (await toolbarButton(page, label, '新增')).click() }
  const form = page.getByRole('dialog', { name: title, exact: true })
  const leave = page.getByRole('dialog', { name: '放弃未保存内容', exact: true })
  await open()
  const input = form.getByRole('textbox', { name: field, exact: true })
  await expect(input).toBeEditable()
  const initial = await input.inputValue()
  await form.getByRole('button', { name: '取消', exact: true }).click()
  await expect(form).toBeHidden(); await expect(leave).toHaveCount(0)
  await open(); await expect(input).toBeEditable()
  await input.fill('未保存字段测试')
  await form.getByRole('button', { name: '取消', exact: true }).click()
  await expect(leave).toBeVisible(); await expect(form).toBeVisible()
  await leave.press('Escape'); await expect(leave).toBeHidden()
  await expect(input).toHaveValue('未保存字段测试')
  await input.fill(initial)
  await form.getByRole('button', { name: '关闭弹窗', exact: true }).click()
  await expect(form).toBeHidden(); await expect(leave).toHaveCount(0)
  await open(); await expect(input).toBeEditable(); await input.fill('放弃字段测试')
  await expect(form.locator('.modal-dialog').first()).toHaveCSS('transform', 'none')
  await form.press('Escape')
  await leave.getByRole('button', { name: '放弃更改', exact: true }).click()
  await expect(form).toBeHidden()
})

test('failed save and route cancellation retain ordinary field edits', async ({ page }) => {
  await page.request.post('/api/registration/session')
  await page.goto('/#/quality/equipment/consumables')
  await expect(page.getByRole('table', { name: '易耗品列表', exact: true })).toBeVisible()
  await (await toolbarButton(page, '易耗品', '新增')).click()
  const form = page.getByRole('dialog', { name: '新增易耗品', exact: true })
  await form.getByRole('textbox', { name: '物质名称', exact: true }).fill('保存失败仍保留')
  await page.route('**/quality/equipment/consumables/save', route => route.fulfill({ status: 500, json: { error: { code: 'INTERNAL', message: '暂时无法保存' } } }))
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form).toContainText('暂时无法保存')
  const url = page.url()
  await page.evaluate(() => { location.hash = '#/quality/equipment/types' })
  const leave = page.getByRole('dialog', { name: '放弃未保存内容', exact: true })
  await leave.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page).toHaveURL(url); await expect(form.getByRole('textbox', { name: '物质名称', exact: true })).toHaveValue('保存失败仍保留')
  await page.evaluate(() => { location.hash = '#/quality/equipment/types' })
  await leave.getByRole('button', { name: '放弃更改', exact: true }).click()
  await expect(page).toHaveURL(/equipment\/types$/)
})
