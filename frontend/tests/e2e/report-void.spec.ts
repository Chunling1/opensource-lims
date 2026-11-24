import { expect, test } from '@playwright/test'

for (const stage of [{ key: 'review', label: '审核', id: '85' }, { key: 'approval', label: '批准', id: '88' }]) {
  test(`report ${stage.key} submits a void application and restores its queue after rejection`, async ({ page }) => {
    await page.setViewportSize({ width: stage.key === 'approval' ? 390 : 1440, height: 1000 })
    const root = `/reports/${stage.key}`, code = `SP20260900${stage.id}`
    await page.goto(`/#${root}`)
    const row = page.getByRole('table', { name: `报告${stage.label}列表`, exact: true }).getByRole('row').filter({ hasText: code })
    const open = async () => {
      await row.getByRole('button', { name: `${code} 更多操作`, exact: true }).click()
      await page.getByRole('menuitem', { name: '作废', exact: true }).click()
    }
    await open()
    const dialog = page.getByRole('dialog', { name: '作废申请', exact: true })
    await expect(dialog).toContainText(code)
    await expect(dialog.getByLabel('申请作废原因', { exact: true })).toHaveAttribute('required', '')
    await dialog.getByRole('button', { name: '取消', exact: true }).click()
    await expect(row).toBeVisible()
    await open()
    await dialog.getByLabel('申请作废原因', { exact: true }).fill('客户要求撤销此报告')
    await dialog.getByRole('button', { name: '确认', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect(row).toHaveCount(0)
    await expect(page).toHaveURL(`/#${root}`)
    const headers = { 'X-Demo-Actor': 'admin' }, samplePath = `/api/registration/samples/demo-yp-${stage.id}`
    const sample = await (await page.request.get(samplePath, { headers })).json()
    expect(sample.status).toBe('void_pending')
    await page.goto('/#/commissions/cancellation-approval')
    await expect(page.getByRole('row').filter({ hasText: code })).toContainText('客户要求撤销此报告')
    const response = await page.request.post(`${samplePath}/cancellation-approval`, { headers, data: { version: sample.version, decision: 'rejected', reason: '继续出具报告' } })
    expect(response.ok()).toBe(true)
    await page.goto(`/#${root}`)
    await expect(row).toBeVisible()
  })
}
