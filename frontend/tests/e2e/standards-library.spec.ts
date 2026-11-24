import { test, expect, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { toolbarButton, openToolbarExport } from './helpers/toolbar'
const registrationCsv = (rows: string[][]) => rows.map(row => row.map(value => '"' + value.replaceAll('"', '""') + '"').join(',')).join('\r\n')
import { standardColumns } from '../../src/types/quality/standards'
const label = '检测标准基础信息库', base = '/api/registration/quality/standards/library', headers = { 'X-Demo-Actor': 'admin' }
async function search(page: Page, name: string) { const form = page.getByRole('form', { name: `${label}查询`, exact: true }); await form.getByLabel('标准名称').fill(name); await form.getByRole('button', { name: '查询', exact: true }).click() }
async function action(page: Page, name: string) { await page.getByRole('table', { name: `${label}列表`, exact: true }).locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click(); await page.getByRole('menuitem', { name, exact: true }).click() }
for (const width of [1440, 390]) test(`standards CRUD, categories, import and export at ${width}`, async ({ page }, info) => {
  test.setTimeout(90000)
  await page.setViewportSize({ width, height: 1000 }); await page.request.post('/api/registration/session'); await page.goto('/#/quality/standards/library')
  const table = page.getByRole('table', { name: `${label}列表`, exact: true })
  await expect(table.locator('tbody tr')).toHaveCount(6)
  await expect(await toolbarButton(page, label, '分组关联')).toBeDisabled()
  // Close a possible toolbar overflow before opening the primary action.
  await page.keyboard.press('Escape')
  await (await toolbarButton(page, label, '新增')).click()
  let dialog = page.getByRole('dialog', { name: '新增检测标准基础信息', exact: true })
  await expect(dialog.getByLabel('标准编号')).toBeVisible()
  await dialog.getByRole('button', { name: '保存', exact: true }).click(); await expect(dialog.locator('[data-field-feedback]').first()).toBeVisible()
  await dialog.getByLabel('标准编号').fill('UI-2026'); await dialog.getByLabel('标准名称').fill('界面测试标准'); await dialog.getByLabel('受控号', { exact: true }).fill('UI-01')
  await dialog.getByRole('group', { name: '使用部门', exact: true }).getByRole('checkbox', { name: '实验室', exact: true }).uncheck(); await dialog.getByLabel('发放数量').fill('3'); await dialog.getByLabel('发放人').fill('张三'); await dialog.getByLabel('存放地点').fill('资料柜')
  await dialog.getByLabel('标准资质类别').selectOption('检测'); await dialog.getByLabel('是否英文标准').selectOption({ label: '是' }); await dialog.getByLabel('是否在资质范围外').check()
  await dialog.getByLabel('类别', { exact: true }).fill('用户自行输入类别'); await dialog.getByLabel('备注').fill('完整导出备注')
  await expect(dialog.getByLabel('替换标准号')).toBeDisabled(); await expect(dialog.getByLabel('延期时间（天）')).toHaveAttribute('readonly', '')
  await expect(dialog.locator('.modal-dialog')).toHaveCSS('transform', 'none'); await dialog.screenshot({ path: info.outputPath(`standard-new-${width}.png`) })
  await dialog.getByRole('button', { name: '保存', exact: true }).click(); await expect(dialog).toBeHidden()
  await search(page, '界面测试标准'); await expect(table.locator('tbody tr')).toHaveCount(1); await expect(table).toContainText('用户自行输入类别')
  await action(page, '查看'); dialog = page.getByRole('dialog', { name: '查看检测标准基础信息', exact: true }); await expect(dialog.getByLabel('标准编号')).toBeDisabled(); await dialog.getByRole('button', { name: '返回', exact: true }).click(); await expect(dialog).toBeHidden()
  await action(page, '编辑'); dialog = page.getByRole('dialog', { name: '编辑检测标准基础信息', exact: true }); await expect(dialog.getByLabel('标准名称')).toHaveValue('界面测试标准'); await expect(dialog.getByLabel('类别', { exact: true })).toHaveValue('用户自行输入类别'); await dialog.getByLabel('备注').fill('编辑后的完整导出备注'); await dialog.getByRole('button', { name: '保存', exact: true }).click(); await expect(dialog).toBeHidden()
  await table.locator('tbody tr').getByRole('checkbox').check(); await (await toolbarButton(page, label, '分组关联')).click()
  dialog = page.getByRole('dialog', { name: '分组关联', exact: true }); await expect(dialog.getByRole('checkbox', { name: '国家标准', exact: true })).not.toBeChecked(); await dialog.getByRole('checkbox', { name: '行业标准', exact: true }).check(); await dialog.getByRole('button', { name: '确认', exact: true }).click(); await expect(dialog).toBeHidden(); await expect(table).toContainText('用户自行输入类别'); await expect(table).not.toContainText('行业标准')
  await action(page, '编辑'); dialog = page.getByRole('dialog', { name: '编辑检测标准基础信息', exact: true }); await expect(dialog.getByLabel('类别', { exact: true })).toHaveValue('用户自行输入类别'); await dialog.getByRole('button', { name: '保存', exact: true }).click(); await expect(dialog).toBeHidden()
  await table.locator('tbody tr').getByRole('checkbox').check(); await (await toolbarButton(page, label, '分组关联')).click(); dialog = page.getByRole('dialog', { name: '分组关联', exact: true }); await expect(dialog.getByRole('checkbox', { name: '行业标准', exact: true })).toBeChecked(); await dialog.getByRole('button', { name: '取消', exact: true }).click(); await expect(dialog).toBeHidden()
  await table.locator('tbody tr').getByRole('checkbox').check(); await openToolbarExport(page, label)
  const downloaded = page.waitForEvent('download'); await page.getByRole('button', { name: /导出已选记录/ }).click(); const csv = await readFile((await (await downloaded).path())!, 'utf8'); expect(csv).toContain('编辑后的完整导出备注'); expect(csv).toContain('是否英文标准'); expect(csv).not.toContain('DEMO-1-2026')
  await page.getByRole('button', { name: /更多筛选/ }).click(); const form = page.getByRole('form', { name: `${label}查询`, exact: true }); await form.getByLabel('标准资质类别').selectOption('校准'); await form.getByRole('button', { name: '查询', exact: true }).click(); await expect(table).toContainText('暂无符合条件'); await form.getByLabel('标准资质类别').selectOption('检测'); await form.getByRole('button', { name: '查询', exact: true }).click(); await expect(table).toContainText('界面测试标准')
  await page.screenshot({ path: info.outputPath(`standard-list-${width}.png`), fullPage: true }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await action(page, '删除'); dialog = page.getByRole('dialog', { name: '删除检测标准基础信息', exact: true }); await dialog.getByRole('button', { name: '确认删除', exact: true }).click(); await expect(dialog).toBeHidden(); await expect(table).toContainText('暂无符合条件')
  const values: Record<string, string> = { controlNumber: 'IMPORT-UI', code: 'IMPORT-UI', name: '导入测试标准', implementedAt: '2026-01-01', departments: '', category: '导入自由文本类别', qualification: '检测' }
  await (await toolbarButton(page, label, '导入')).click(); dialog = page.getByRole('dialog', { name: '导入检测标准', exact: true })
  await dialog.getByLabel('导入文件').setInputFiles({ name: 'standards.csv', mimeType: 'text/csv', buffer: Buffer.from(registrationCsv([standardColumns.map(c => c.label), standardColumns.map(c => values[c.key] || '')])) }); await dialog.getByRole('button', { name: '导入', exact: true }).click(); await expect(dialog).toBeHidden(); await search(page, '导入测试标准'); await expect(table).toContainText('IMPORT-UI')
  const download = page.waitForEvent('download'); await (await toolbarButton(page, label, '下载模板')).click(); expect((await download).suggestedFilename()).toBe('检测标准导入模板.csv')
})
test('standard readonly roles, department view, version conflicts and category linkage', async ({ page }) => {
  await page.request.post('/api/registration/session'); await page.goto('/#/quality/standards/library')
  const table = page.getByRole('table', { name: `${label}列表`, exact: true }); await expect(table.locator('tbody tr')).toHaveCount(6)
  await action(page, '编辑'); let dialog = page.getByRole('dialog', { name: '编辑检测标准基础信息', exact: true }); await expect(dialog.getByLabel('标准编号')).toHaveValue('DEMO-1-2026')
  const row = await (await page.request.post(`${base}/detail`, { headers, data: { id: 'standard-1' } })).json()
  expect((await page.request.post(`${base}/save`, { headers, data: { ...row, notes: '并发修改' } })).ok()).toBe(true)
  await dialog.getByRole('button', { name: '保存', exact: true }).click(); await expect(dialog).toContainText('已更新'); await dialog.getByRole('button', { name: '重新加载', exact: true }).click(); await expect(dialog.getByLabel('备注')).toHaveValue('并发修改'); await dialog.getByRole('button', { name: '取消', exact: true }).click(); await expect(dialog).toBeHidden()
  await page.evaluate(() => { location.hash = '/quality/standards/department-library' }); await expect(page.getByRole('table', { name: '检测标准基础信息库[科室]列表', exact: true }).locator('tbody tr')).toHaveCount(5)
  await page.evaluate(() => localStorage.setItem('lims.identity.v1', 'reviewer')); await page.goto('/#/quality/standards/library'); await page.reload(); await expect(table).toContainText('DEMO-1-2026')
  await expect(await toolbarButton(page, label, '新增')).toBeDisabled(); await expect(await toolbarButton(page, label, '导入')).toBeDisabled(); await page.keyboard.press('Escape')
  await table.locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click(); await expect(page.getByRole('menuitem', { name: '编辑', exact: true })).toBeDisabled(); await expect(page.getByRole('menuitem', { name: '删除', exact: true })).toBeDisabled()
})
