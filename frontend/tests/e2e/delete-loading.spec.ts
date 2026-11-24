import { test, expect } from '@playwright/test'
import { emptyPersonnel } from '../../src/types/quality/personnel'

for (const item of [
  { path: '/quality/equipment/ledger', table: '设备台账列表', title: '删除设备', api: /\/ledger\/[^/]+\/detail$/ },
  { path: '/quality/personnel/certificates', table: '上岗证列表', title: '删除上岗证', api: /\/quality\/certificates\/certificates\/[^/?]+$/ },
]) test(`${item.title} keeps confirmation visible during impact checks and can cancel`, async ({ page }) => {
  await page.goto(`/#${item.path}`)
  if (item.title === '删除上岗证') await page.getByRole('tab', { name: '全部上岗证', exact: true }).click()
  const table = page.getByRole('table', { name: item.table, exact: true })
  await table.locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click()
  let release!: () => void, requested = false
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route(item.api, async route => { requested = true; await pending; await route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '核对暂时不可用' } } }).catch(() => {}) }, { times: 1 })
  await page.getByRole('menuitem', { name: '删除', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: item.title, exact: true })
  try {
    await expect.poll(() => requested).toBe(true)
    await expect(dialog).toContainText('确认删除')
    await expect(dialog.getByRole('status')).toHaveText('正在核对关联记录…')
    await expect(dialog.getByText('正在加载…', { exact: true })).toHaveCount(0)
    await expect(dialog.getByRole('button', { name: '确认删除', exact: true })).toBeDisabled()
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
    await expect(dialog).toBeHidden()
  } finally { release() }
  await expect(page.getByText('核对暂时不可用', { exact: true })).toHaveCount(0)
})

test('personnel deletion skips detail reads and preserves confirmation on conflict reload', async ({ page }) => {
  await page.request.post('/api/registration/session')
  const headers = { 'X-Demo-Actor': 'admin' }, base = '/api/registration/quality/personnel'
  const response = await page.request.post(base, { headers, data: { ...emptyPersonnel(), name: '删除核对人员', code: 'DELETE-CHECK', gender: '男', qualification: '工程师', position: '检测员', department: '实验室' } })
  expect(response.ok()).toBe(true)
  const row = await response.json()
  await page.goto('/#/quality/personnel/registration?code=DELETE-CHECK')
  await page.getByRole('table', { name: '人员登记列表' }).getByRole('button', { name: /更多操作/ }).click()
  let reads = 0
  await page.route(`**/quality/personnel/${row.id}`, route => { reads++; return route.continue() })
  await page.getByRole('menuitem', { name: '删除', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '删除人员', exact: true })
  await expect(dialog).toContainText('删除核对人员（DELETE-CHECK）')
  await expect(dialog.getByRole('button', { name: '删除', exact: true })).toBeEnabled()
  expect(reads).toBe(0)
  expect((await page.request.post(`${base}/${row.id}/save`, { headers, data: { ...row, name: '最新人员名称' } })).ok()).toBe(true)
  await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '重新加载', exact: true })).toBeVisible()
  let release!: () => void
  const pending = new Promise<void>(resolve => { release = resolve })
  await page.route(`**/quality/personnel/${row.id}`, async route => { await pending; await route.continue() }, { times: 1 })
  await dialog.getByRole('button', { name: '重新加载', exact: true }).click()
  try {
    await expect(dialog).toContainText('删除核对人员（DELETE-CHECK）')
    await expect(dialog.getByRole('status')).toHaveText('正在核对最新信息…')
    await expect(dialog.getByRole('button', { name: '删除', exact: true })).toBeDisabled()
  } finally { release() }
  await expect(dialog).toContainText('最新人员名称')
  await dialog.getByRole('button', { name: '删除', exact: true }).click()
  await expect(dialog).toBeHidden()
})

test('approved project deletion uses the listed version without fetching details', async ({ page }) => {
  await page.goto('/#/quality/personnel/certificates')
  await page.getByRole('tab', { name: '全部核准项目', exact: true }).click()
  await page.getByRole('table', { name: '核准项目列表', exact: true }).locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click()
  let reads = 0
  await page.route(/\/quality\/certificates\/projects\/[^/?]+$/, route => { reads++; return route.abort() })
  await page.getByRole('menuitem', { name: '删除', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '删除核准检测项目', exact: true })
  await expect(dialog).toContainText('确认删除核准检测项目')
  await expect(dialog.getByRole('button', { name: '确认删除', exact: true })).toBeEnabled()
  expect(reads).toBe(0)
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog).toBeHidden()
})

for (const source of ['internal', 'external']) test(`${source} report change deletion needs no detail request`, async ({ page }) => {
  await page.goto(`/#/reports/changes/${source}`)
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新增申请', exact: true })
  await form.getByRole('button', { name: '选择报告', exact: true }).click()
  const picker = page.getByRole('dialog', { name: '选择报告', exact: true })
  await picker.getByRole('checkbox', { name: '选择 SP2026090092', exact: true }).check()
  await picker.getByRole('button', { name: '移入', exact: true }).click()
  await picker.getByRole('button', { name: '确认', exact: true }).click()
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form).toBeHidden()
  const table = page.getByRole('table', { name: source === 'internal' ? '内部申请列表' : '外部申请列表', exact: true })
  await table.locator('tbody tr').first().getByRole('button', { name: /更多操作/ }).click()
  let reads = 0
  await page.route(new RegExp(`/reports/${source}-changes/[^/?]+$`), route => { if (route.request().method() === 'GET') reads++; return route.continue() })
  await page.getByRole('menuitem', { name: '删除', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '删除申请', exact: true })
  await expect(dialog).toContainText('确认删除这条申请')
  await expect(dialog.getByRole('button', { name: '确认删除', exact: true })).toBeEnabled()
  expect(reads).toBe(0)
  await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(dialog).toBeHidden()
})
