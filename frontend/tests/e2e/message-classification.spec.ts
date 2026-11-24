import { expect, test } from '@playwright/test'

test('report recipient validation is an operation hint and keeps the delivery form', async ({ page }) => {
  await page.goto('/#/reports/distribution')
  const menus = page.getByRole('button', { name: /更多操作$/ })
  await expect(menus.first()).toBeVisible()
  let opened = false
  for (let i = 0; i < await menus.count(); i++) {
    await menus.nth(i).click()
    const action = page.getByRole('menuitem', { name: '发放', exact: true })
    if (await action.count() && await action.isEnabled()) { await action.click(); opened = true; break }
    await page.keyboard.press('Escape')
    await page.getByRole('heading', { name: '报告发放', exact: true }).first().click()
  }
  expect(opened).toBe(true)
  const dialog = page.getByRole('dialog', { name: '报告发放', exact: true })
  await dialog.getByLabel('领取人', { exact: true }).fill('   ')
  await dialog.getByLabel('备注', { exact: true }).fill('保留表单内容')
  await dialog.getByRole('button', { name: '确认', exact: true }).click()
  const hint = dialog.getByRole('alert', { name: '操作提示' })
  await expect(hint).toContainText('请检查领取人')
  await expect(hint).not.toContainText('诊断编号')
  await expect(hint.getByRole('button', { name: '重试', exact: true })).toHaveCount(0)
  await expect(dialog.getByLabel('备注', { exact: true })).toHaveValue('保留表单内容')
  await expect(dialog.locator('.alert-danger')).toHaveCount(0)
})

test('save hints reuse compact feedback while conflicts retain recovery and faults retain diagnostics', async ({ page }) => {
  await page.goto('/#/commissions/registration/commissions/demo-wt-1/edit')
  await page.getByLabel('项目名称', { exact: true }).fill('保留未保存的名称')
  for (const code of ['VALIDATION', 'BUSINESS_RULE', 'VERSION_CONFLICT', 'INTERNAL']) {
    await page.route('**/api/registration/commissions/demo-wt-1', route => route.request().method() === 'PUT'
      ? route.fulfill({ status: code === 'INTERNAL' ? 500 : code === 'VERSION_CONFLICT' ? 409 : 422, json: { error: { code, message: `${code} 检查提示` } } })
      : route.continue())
    await page.getByRole('button', { name: '保存', exact: true }).click()
    const toast = page.locator('.toast.show').filter({ hasText: `${code} 检查提示` })
    await expect(toast).toBeVisible()
    await expect(toast.locator('.alert')).toHaveCount(0)
    if (code === 'INTERNAL') await expect(toast).toContainText('诊断编号')
    else { await expect(toast).toContainText('操作提示'); await expect(toast).not.toContainText('诊断编号') }
    if (code === 'VERSION_CONFLICT') {
      await expect(toast.getByRole('link', { name: '查看最新记录' })).toHaveAttribute('target', '_blank')
      await toast.getByRole('button', { name: '重新加载', exact: true }).click()
      await expect(toast).toContainText('重新加载将替换当前未保存的输入')
      await toast.getByRole('button', { name: '保留输入', exact: true }).click()
    }
    await expect(page.getByLabel('项目名称', { exact: true })).toHaveValue('保留未保存的名称')
    await toast.getByRole('button', { name: /^关闭/ }).click()
    await expect(toast).toHaveCount(0)
    await page.unroute('**/api/registration/commissions/demo-wt-1')
  }
})

test('success feedback is a reusable floating toast and repeats without moving content', async ({ page }) => {
  await page.goto('/#/identity')
  const identity = page.locator('main .card-body button').first()
  await expect(identity).toBeVisible()
  for (let i = 0; i < 2; i++) {
    const before = await identity.boundingBox()
    await identity.click()
    const toast = page.locator('.toast.show').filter({ hasText: '演示身份已切换' })
    await expect(toast).toBeVisible()
    await expect(page.locator('main .alert-success')).toHaveCount(0)
    expect((await identity.boundingBox())!.y).toBeCloseTo(before!.y, 0)
    await toast.getByRole('button', { name: '关闭系统提示' }).click()
    await expect(toast).toHaveCount(0)
  }
})
