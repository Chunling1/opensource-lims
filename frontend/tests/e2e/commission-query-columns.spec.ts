import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const headings = '样品编号、委托编号、报告编号、外部ERP合同编号、样品类型、委托日期、样品/工程名称、检测参数、数据状态、检测方案、委托单位、项目名称、生产单位、样品数量、抽样数量、规格型号、商标、检验类别、指定主检人、标准价格费用、折扣价格费用、实际价格费用、收费情况、报告交付方式、样品登记人、委托经办人、委托人、委托人电话、委托单位地址'.split('、')
const defaults = ['样品编号', '报告编号', '样品类型', '样品/工程名称', '检测参数', '数据状态', '委托单位', '样品登记人']

test('inquiry uses its own 29 columns, preserves visibility and exports the same order', async ({ page }, testInfo) => {
  await page.goto('/#/commissions/query?scope=all&sSort=code&sDirection=asc')
  const region = page.getByRole('region', { name: '样品列表区域', exact: true })
  const table = region.getByRole('table', { name: '样品列表', exact: true })
  await expect(table.locator('tbody tr')).toHaveCount(10)
  await expect(table.locator('thead th')).toHaveText(['', ...defaults, ''])
  await table.locator('tbody tr').first().getByRole('checkbox').check()
  let queries = 0
  page.on('request', request => { if (new URL(request.url()).pathname.endsWith('/samples/query')) queries++ })
  await region.getByRole('button', { name: '显示', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '样品显示列', exact: true })
  await expect(dialog.getByRole('checkbox')).toHaveCount(29)
  for (const heading of headings) {
    const checkbox = dialog.getByRole('checkbox', { name: heading, exact: true })
    if (!await checkbox.isChecked()) await checkbox.check()
  }
  await dialog.getByRole('button', { name: '完成', exact: true }).click()
  await expect(table.locator('thead th')).toHaveText(['', ...headings, ''])
  await expect(table.locator('tbody tr').first().getByRole('checkbox')).toBeChecked()
  expect(queries).toBe(0)
  const first = table.locator('tbody tr').first(), cells = first.locator('td')
  for (const label of ['外部ERP合同编号', '折扣价格费用', '实际价格费用']) await expect(cells.nth(headings.indexOf(label) + 1)).toHaveText('—')
  await region.getByRole('button', { name: '导出', exact: true }).click()
  const downloading = page.waitForEvent('download')
  await region.getByRole('button', { name: '导出已选记录（1）', exact: true }).click()
  const csv = await readFile((await (await downloading).path())!, 'utf8')
  expect(csv.replace(/^\uFEFF/, '').split('\r\n')[0]).toBe(headings.map(label => `"${label}"`).join(','))
  expect(csv.split('\r\n')).toHaveLength(2)
  await page.reload()
  await expect(table.locator('thead th')).toHaveText(['', ...headings, ''])
  for (const [width, theme] of [[1440, 'light'], [390, 'dark']] as const) {
    await page.setViewportSize({ width, height: 900 })
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await table.scrollIntoViewIfNeeded()
    await table.locator('..').evaluate(element => { element.scrollLeft = element.scrollWidth })
    await expect(table.getByRole('columnheader', { name: '委托单位地址', exact: true })).toBeInViewport()
    await page.screenshot({ path: testInfo.outputPath(`inquiry-columns-${width}-${theme}.png`) })
  }
  await region.getByRole('button', { name: '样品更多操作', exact: true }).click()
  await region.getByRole('button', { name: '显示', exact: true }).click()
  await dialog.getByRole('button', { name: '恢复默认', exact: true }).click()
  await dialog.getByRole('button', { name: '完成', exact: true }).click()
  await expect(table.locator('thead th')).toHaveText(['', ...defaults, ''])
})
