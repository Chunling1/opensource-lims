import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { emptyEquipment } from '../../src/types/quality/equipmentForm'
import { toolbarButton } from './helpers/toolbar'

for (const width of [1440, 390]) test(`view equipment hides mutation actions in every tab at ${width}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.request.post('/api/registration/session')
  const base = '/api/registration/quality/equipment/ledger', headers = { 'X-Demo-Actor': 'admin' }
  const draft = { ...emptyEquipment(), code: 'READONLY-001', name: '只读验证设备', departmentId: 'lab' }
  const options = await (await page.request.get(`${base}/options`, { headers })).json()
  draft.profile.projects = [options.projects[0]]
  draft.profile.calibrations = [{ id: 'c', organization: '只读检定单位' }]
  draft.profile.maintenance = [{ id: 'm', content: '只读维修内容' }]
  draft.profile.usage = [{ id: 'u', person: '只读使用人' }]
  draft.profile.checks = [{ id: 'k', standard: '只读参考标准' }]
  expect((await page.request.post(`${base}/save`, { headers, data: draft })).ok()).toBe(true)
  await page.goto(`/#/quality/equipment/${width === 390 ? 'department-ledger' : 'ledger'}?code=READONLY-001`)
  const row = page.getByRole('table', { name: '设备台账列表', exact: true }).locator('tbody tr').first()
  await expect(row).toContainText('READONLY-001')
  await row.getByRole('button', { name: /更多操作/ }).click()
  await page.getByRole('menuitem', { name: '查看', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '查看设备', exact: true })
  for (const label of ['检测方案', '检定记录', '维修维护记录', '使用记录', '期间核查记录', '报告信息']) {
    await dialog.getByRole('tab', { name: label, exact: true }).click()
    for (const name of ['新增', '选择方案', '删除', '确认删除']) await expect(dialog.getByRole('button', { name, exact: true, includeHidden: true })).toHaveCount(0)
    if (label === '检测方案' || label === '报告信息') continue
    await dialog.getByRole('table', { name: `${label}列表`, exact: true }).locator('tbody tr').first().getByRole('checkbox').check()
    await expect(await toolbarButton(page, label, '打印')).toBeEnabled()
    await (await toolbarButton(page, label, '查看')).click()
    const detail = page.getByRole('dialog', { name: `查看${label}`, exact: true })
    await expect(detail.locator('input').first()).not.toBeEditable()
    await expect(detail.getByRole('button', { name: '确认', exact: true })).toHaveCount(0)
    await detail.getByRole('button', { name: '返回', exact: true }).click()
    if (label === '检定记录') {
      await dialog.getByRole('table', { name: `${label}列表`, exact: true }).locator('tbody tr').first().getByRole('checkbox').check()
      const downloading = page.waitForEvent('download')
      await (await toolbarButton(page, label, '导出')).click()
      const download = await downloading
      expect(await readFile((await download.path())!, 'utf8')).toContain('只读检定单位')
    }
  }
  await dialog.getByRole('button', { name: '返回', exact: true }).click()
  await page.goto('/#/quality/equipment/ledger?code=READONLY-001')
  await row.getByRole('button', { name: /更多操作/ }).click()
  await page.getByRole('menuitem', { name: '编辑', exact: true }).click()
  const edit = page.getByRole('dialog', { name: '编辑设备', exact: true })
  for (const label of ['检测方案', '检定记录']) {
    await edit.getByRole('tab', { name: label, exact: true }).click()
    await edit.getByRole('table', { name: `${label}列表`, exact: true }).locator('tbody tr').first().getByRole('checkbox').check()
    await expect(await toolbarButton(page, label, '删除')).toBeEnabled()
  }
})
