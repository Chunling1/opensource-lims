import { expect, test } from '@playwright/test'

const stages = [
  { stage: 'check', label: '校核', ids: ['82', '84'], receiver: '王复核（reviewer）' },
  { stage: 'review', label: '审核', ids: ['85', '87'], receiver: '王复核（reviewer）' },
  { stage: 'approval', label: '批准', ids: ['88', '90'], receiver: '陈批准（approver）' },
] as const
for (const item of stages) for (const width of [1440, 390]) test(`quick report ${item.stage} at ${width}`, async ({ page }, info) => {
  test.setTimeout(90000)
  await page.setViewportSize({ width, height: 1000 })
  const root = `/reports/${item.stage}`
  await page.goto(`/#${root}`)
  const quick = page.getByRole('button', { name: `快速${item.label}`, exact: true })
  await expect(quick).toBeDisabled()
  const table = page.getByRole('table', { name: `报告${item.label}列表`, exact: true })
  const select = async () => {
    for (const id of item.ids) await table.getByRole('row').filter({ hasText: `SP20260900${id}` }).getByRole('checkbox').check()
    await quick.click()
  }
  await select()
  const dialog = page.getByRole('dialog', { name: `快速${item.label}`, exact: true })
  const confirmed = dialog.getByRole('checkbox', { name: `我已阅读并确认全部样品的${item.label}结果`, exact: true })
  await expect(dialog).toContainText('已选择 2 个样品')
  await expect(dialog.getByRole('button', { name: '通过', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: '校验', exact: true }).click()
  for (const id of item.ids) await expect(dialog.getByRole('heading', { name: new RegExp(`SP20260900${id}`) })).toBeVisible()
  await confirmed.check()
  await page.screenshot({ path: info.outputPath(`quick-${item.stage}-${width}.png`), fullPage: true, animations: 'disabled' })
  await dialog.getByRole('button', { name: '通过', exact: true }).click()
  const next = page.getByRole('dialog', { name: '确认下一步', exact: true })
  await expect(next.getByRole('radio', { name: '下一步', exact: true })).toBeChecked()
  await next.getByRole('radio', { name: `转交${item.label}`, exact: true }).check()
  await expect(next.getByRole('button', { name: '确定', exact: true })).toBeDisabled()
  await next.getByRole('button', { name: '选择接收人', exact: true }).click()
  const picker = page.getByRole('dialog', { name: '选择接收人', exact: true })
  await picker.getByRole('radio', { name: `选择 ${item.receiver}`, exact: true }).check()
  await picker.getByRole('button', { name: '确定', exact: true }).click()
  await next.getByRole('button', { name: '确定', exact: true }).click()
  await expect(next).toBeHidden()
  await expect(quick).toBeDisabled()
  await select()
  await expect(confirmed).not.toBeChecked()
  await dialog.getByRole('button', { name: '校验', exact: true }).click()
  await confirmed.check()
  await dialog.getByRole('button', { name: '通过', exact: true }).click()
  await next.getByRole('button', { name: '确定', exact: true }).click()
  await expect(next).toBeHidden()
  for (const id of item.ids) await expect(table).not.toContainText(`SP20260900${id}`)
  await expect(page).toHaveURL(`/#${root}`)
})

test('quick report check handles incomplete results, unavailable states and shared rejection', async ({ page }) => {
  await page.goto('/#/reports/check')
  const table = page.getByRole('table', { name: '报告校核列表', exact: true })
  for (const id of ['82', '84']) await table.getByRole('row').filter({ hasText: `SP20260900${id}` }).getByRole('checkbox').check()
  await page.getByRole('button', { name: '快速校核', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '快速校核', exact: true })
  await page.route('**/samples/report-batch/check', async route => {
    const response = await route.fetch(), data = await response.json()
    data.items.pop()
    await route.fulfill({ response, json: data })
  }, { times: 1 })
  await dialog.getByRole('button', { name: '校验', exact: true }).click()
  await expect(dialog).toContainText('核验结果不完整')
  await expect(dialog.getByRole('button', { name: '通过', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: '校验', exact: true }).click()
  await dialog.getByRole('checkbox').check()
  const headers = { 'X-Demo-Actor': 'admin' }
  await page.route('**/samples/report-batch/submit', route => route.fulfill({ status: 422, json: { error: { code: 'BUSINESS_RULE', message: '样品当前状态不可操作，请刷新。' } } }), { times: 1 })
  await dialog.getByRole('button', { name: '通过', exact: true }).click()
  await page.getByRole('dialog', { name: '确认下一步', exact: true }).getByRole('button', { name: '确定', exact: true }).click()
  await expect(dialog).toContainText('样品信息或可用状态已变化')
  await dialog.getByRole('button', { name: '刷新样品', exact: true }).click()
  await expect(dialog.getByRole('button', { name: '通过', exact: true })).toBeDisabled()
  await dialog.getByRole('button', { name: '不通过', exact: true }).click()
  const issue = page.getByRole('dialog', { name: '问题处理', exact: true })
  await issue.getByRole('radio', { name: '其他问题', exact: true }).check()
  await issue.getByRole('button', { name: '确定', exact: true }).click()
  await expect(issue).toBeHidden()
  for (const id of ['82', '84']) {
    const saved = await (await page.request.get(`/api/registration/samples/demo-yp-${id}`, { headers })).json()
    expect(saved.dataStatus).toBe('委托更改中')
    expect(saved.reportCheckIssues.at(-1).reason).toBe('')
  }
})
