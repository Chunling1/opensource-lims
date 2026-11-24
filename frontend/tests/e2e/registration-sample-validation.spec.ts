import { expect, test } from '@playwright/test'
import { selectGeneralSamplePlan } from './helpers/sample-plan'

for (const width of [1440, 390]) {
  test(`sample validation follows visible field order and shares inline feedback at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/commissions/registration/samples/new?commissionId=demo-wt-1')
    if (width === 390) await page.evaluate(() => document.documentElement.setAttribute('data-bs-theme', 'dark'))
    const form = page.getByRole('form', { name: '样品表单', exact: true })
    const save = form.getByRole('button', { name: '保存', exact: true })
    const saveReturn = form.getByRole('button', { name: '保存并返回', exact: true })
    let submissions = 0
    page.on('request', request => { if (request.url().endsWith('/api/registration/samples') && request.method() === 'POST') submissions++ })
    await form.locator('#sample-quantity').fill('')
    await save.click()
    await expect(form.locator('#sample-testPlan')).toBeFocused()
    await expect(form.locator('#sample-testPlan')).toBeInViewport()
    for (const id of ['sample-testPlan', 'sample-category', 'sample-name', 'sample-quantity']) {
      await expect(form.locator(`#${id}`)).toHaveClass(/is-invalid/)
      await expect(form.locator(`#${id}`)).toHaveAttribute('aria-describedby', `${id}-error`)
      await expect(form.locator(`#${id}-error`)).toHaveClass('invalid-feedback d-block')
      await expect(form.locator(`#${id}-error`)).toHaveAttribute('role', 'alert')
    }
    await expect(page.locator('.toast.show')).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath(`validation-${width}.png`) })
    await selectGeneralSamplePlan(page)
    await expect(form.locator('#sample-testPlan-error')).toHaveCount(0)
    await saveReturn.click()
    await expect(form.locator('#sample-category')).toBeFocused()
    await expect(form.locator('#sample-category-error')).toHaveText('请选择检测类别。')
    await form.locator('#sample-category').selectOption('委托')
    await expect(form.locator('#sample-category-error')).toHaveCount(0)
    await save.click()
    await expect(form.locator('#sample-name')).toBeFocused()
    await expect(form.locator('#sample-name-error')).toHaveText('请填写工程/产品名称。')
    await form.locator('#sample-name').fill('校验顺序测试')
    await save.click()
    await expect(form.locator('#sample-quantity')).toBeFocused()
    await form.locator('#sample-quantity').fill('1')
    for (const id of ['samplingQuantity', 'samplingBase', 'standardPrice']) await form.locator(`#sample-${id}`).fill('-1')
    for (const id of ['samplingQuantity', 'samplingBase', 'standardPrice']) {
      await save.click()
      await expect(form.locator(`#sample-${id}`)).toBeFocused()
      await expect(form.locator(`#sample-${id}`)).toBeInViewport()
      await expect(form.locator(`#sample-${id}-error`)).toBeVisible()
      await form.locator(`#sample-${id}`).fill('1')
      await expect(form.locator(`#sample-${id}-error`)).toHaveCount(0)
    }
    expect(submissions).toBe(0)
    await save.click()
    await expect(page).toHaveURL(/samples\/[^/]+\/edit/)
    expect(submissions).toBe(1)
  })
}

test('validation keeps the current tab for the plan then reveals the first invalid hidden sample field', async ({ page }) => {
  await page.goto('/#/commissions/registration/samples/new?commissionId=demo-wt-1')
  const form = page.getByRole('form', { name: '样品表单', exact: true })
  await form.getByRole('tab', { name: '委托信息', exact: true }).click()
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form.locator('#sample-testPlan')).toBeFocused()
  await expect(form.getByRole('tab', { name: '委托信息', exact: true })).toHaveAttribute('aria-selected', 'true')
  await selectGeneralSamplePlan(page)
  await form.getByRole('button', { name: '保存', exact: true }).click()
  await expect(form.getByRole('tab', { name: '样品信息', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(form.locator('#sample-category')).toBeFocused()
  await expect(form.locator('#sample-category-error')).toBeVisible()
})
