import { test, expect } from '@playwright/test'
import { toolbarButton } from './helpers/toolbar'

test('draft attachment deletion confirms, preserves its parent, retries failures and blocks duplicate requests', async ({ page }) => {
  test.setTimeout(60000)
  await page.request.post('/api/registration/session')
  await page.goto('/#/quality/requests')
  await expect(page.getByRole('table', { name: '日常事务申请列表', exact: true })).toContainText('检测合同用印（示例）')
  await (await toolbarButton(page, '日常事务申请', '新增')).click()
  const parent = page.getByRole('dialog', { name: '新增申请', exact: true })
  await parent.getByLabel('办理事由', { exact: true }).fill('保留附件删除时的输入')
  await parent.locator('input[type=file]').setInputFiles({ name: '确认删除.txt', mimeType: 'text/plain', buffer: Buffer.from('evidence') })
  const remove = parent.getByRole('button', { name: '删除附件 确认删除.txt', exact: true })
  await expect(remove).toBeEnabled()
  await remove.click()
  const confirmation = page.getByRole('dialog', { name: '删除附件', exact: true })
  await expect(parent).toBeVisible()
  await confirmation.press('Escape')
  await expect(confirmation).toBeHidden()
  await expect(remove).toBeFocused()
  await expect(parent.getByLabel('办理事由', { exact: true })).toHaveValue('保留附件删除时的输入')
  let release!: () => void, requests = 0
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/attachment-drafts/*/remove', async route => {
    requests++
    if (requests > 1) return route.continue()
    await gate
    await route.fulfill({ status: 500, json: { error: { code: 'INTERNAL', message: '附件删除失败，请重试' } } })
  })
  await remove.click()
  try {
    await confirmation.getByRole('button', { name: '确认删除', exact: true }).click()
    await expect(confirmation.getByRole('button', { name: '正在删除…', exact: true })).toBeDisabled()
    await expect(confirmation.getByRole('button', { name: '取消', exact: true })).toBeDisabled()
    await confirmation.press('Escape')
    await expect(confirmation).toBeVisible()
    expect(requests).toBe(1)
  } finally { release() }
  await expect(confirmation.getByRole('alert')).toContainText('附件删除失败')
  await expect(parent.getByRole('button', { name: '确认删除.txt', exact: true })).toBeVisible()
  await confirmation.getByRole('button', { name: '确认删除', exact: true }).click()
  await expect(confirmation).toBeHidden()
  await expect(remove).toHaveCount(0)
  expect(requests).toBe(2)
  await parent.getByRole('button', { name: '取消', exact: true }).click()
  const leave = page.getByRole('dialog', { name: '放弃未保存内容', exact: true })
  await leave.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(parent.getByLabel('办理事由', { exact: true })).toHaveValue('保留附件删除时的输入')
  await parent.getByRole('button', { name: '取消', exact: true }).click()
  await leave.getByRole('button', { name: '放弃更改', exact: true }).click()
  await expect(parent).toBeHidden()
})
