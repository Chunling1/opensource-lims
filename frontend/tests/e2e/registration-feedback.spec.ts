import { test, expect } from '@playwright/test'

test('pending saves keep form and button appearance stable and block duplicate submissions', async ({ page }) => {
  await page.goto('/#/commissions/registration/commissions/demo-wt-1/edit')
  const form = page.getByRole('form', { name: '委托表单' })
  const save = page.getByRole('button', { name: '保存', exact: true })
  const saveReturn = page.getByRole('button', { name: '保存并返回', exact: true })
  await save.scrollIntoViewIfNeeded()
  const saveWidth = (await save.boundingBox())!.width, returnWidth = (await saveReturn.boundingBox())!.width
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  let requests = 0
  await page.route('**/api/registration/commissions/demo-wt-1', async route => {
    if (route.request().method() !== 'PUT') return route.continue()
    requests++
    await gate
    await route.continue()
  })
  try {
    await save.click()
    await expect(save).toHaveAttribute('aria-busy', 'true')
    await expect(save).toHaveText('保存')
    await expect(saveReturn).toHaveText('保存并返回')
    await expect(save).toHaveCSS('opacity', '1')
    await expect(form.locator('fieldset').first()).toHaveAttribute('inert', '')
    expect((await save.boundingBox())!.width).toBe(saveWidth)
    expect((await saveReturn.boundingBox())!.width).toBe(returnWidth)
    await expect(page.getByRole('status', { name: '正在处理' })).toBeVisible()
    await form.evaluate(element => (element as HTMLFormElement).requestSubmit(element.querySelector('button[value="stay"]') as HTMLButtonElement))
    expect(requests).toBe(1)
  } finally { release() }
  await expect(page.locator('.toast.show')).toContainText('委托已保存。')
  await expect(save).toHaveAttribute('aria-busy', 'false')
  expect(requests).toBe(1)
  await expect(form.locator('fieldset').first()).not.toHaveAttribute('inert')
})

test('first commission save retains the form DOM without reloading or resetting scroll', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2001-01-01T12:00:00+08:00'))
  const defaultsResponse = page.waitForResponse(response => response.url().endsWith('/commissions/defaults'))
  await page.goto('/#/commissions/registration/commissions/new')
  const { commissionDate: today } = await (await defaultsResponse).json()
  expect(today).not.toBe('2001-01-01')
  await expect(page.getByLabel('委托日期', { exact: true })).toHaveValue(today)
  await expect(page.getByLabel('委托日期', { exact: true })).toHaveAttribute('readonly', '')
  await page.getByLabel('项目名称', { exact: true }).fill('首次保存保持页面')
  const form = await page.getByRole('form', { name: '委托表单' }).elementHandle()
  const field = await page.getByLabel('项目名称', { exact: true }).elementHandle()
  const save = page.getByRole('button', { name: '保存', exact: true })
  await save.scrollIntoViewIfNeeded()
  const scroll = await page.evaluate(() => scrollY)
  const reads: string[] = []
  page.on('request', request => { if (request.method() === 'GET' && /\/api\/registration\/commissions\/[^/]+$/.test(request.url())) reads.push(request.url()) })
  await save.click()
  await expect(page).toHaveURL(/\/commissions\/[^/?]+\/edit/)
  await expect(page.locator('.toast.show')).toContainText('委托已保存。')
  expect(await form!.evaluate(element => element.isConnected)).toBe(true)
  expect(await field!.evaluate(element => element.isConnected)).toBe(true)
  expect(await page.evaluate(() => scrollY)).toBe(scroll)
  expect(reads).toEqual([])
  await expect(page.getByLabel('项目名称', { exact: true })).toHaveValue('首次保存保持页面')
  await expect(page.getByLabel('委托编号', { exact: true })).toHaveValue(/^WT\d+$/)
  await expect(page.getByLabel('委托日期', { exact: true })).toHaveValue(today)
  await expect(page.getByLabel('委托日期', { exact: true })).toHaveAttribute('readonly', '')
  await expect(page.getByLabel('添加附件', { exact: false })).toHaveCount(0)
  await save.click()
  await expect(page.locator('.toast.show')).toContainText('委托已保存。')
  expect(await form!.evaluate(element => element.isConnected)).toBe(true)
  expect(reads).toEqual([])
})

test('new commissions retry server date failures without using the browser date', async ({ page }) => {
  let requests = 0
  await page.route('**/api/registration/commissions/defaults', route => {
    requests++
    return requests === 1
      ? route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '服务器日期暂不可用' } } })
      : route.fulfill({ json: { commissionDate: '2031-03-04' } })
  })
  await page.goto('/#/commissions/registration/commissions/new')
  await expect(page.getByRole('form', { name: '委托表单' })).toHaveCount(0)
  await expect(page.getByText('服务器日期暂不可用', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await expect(page.getByLabel('委托日期', { exact: true })).toHaveValue('2031-03-04')
  await expect(page.getByLabel('委托日期', { exact: true })).toHaveAttribute('readonly', '')
  expect(requests).toBe(2)
})

test('commission save toasts preserve button position and scrolling on desktop and mobile', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/#/commissions/registration/commissions/demo-wt-1/edit')
    const save = page.getByRole('button', { name: '保存', exact: true })
    await save.scrollIntoViewIfNeeded()
    const before = await save.boundingBox(), scroll = await page.evaluate(() => scrollY)
    await save.click()
    const toast = page.locator('.toast.show').filter({ hasText: '委托已保存。' })
    await expect(toast).toBeInViewport()
    expect((await save.boundingBox())!.y).toBeCloseTo(before!.y, 0)
    expect(await page.evaluate(() => scrollY)).toBe(scroll)
    await toast.getByRole('button', { name: '关闭系统提示' }).click()
    await expect(toast).toHaveCount(0)
    await save.click()
    await expect(toast).toBeInViewport()
    await expect(toast).toHaveCount(0, { timeout: 6000 })
    await page.route('**/api/registration/commissions/demo-wt-1', route => route.request().method() === 'PUT' ? route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '保存服务暂不可用' } } }) : route.continue())
    await save.click()
    const failure = page.locator('.toast.show').filter({ hasText: '保存服务暂不可用' })
    await expect(failure).toBeInViewport()
    expect((await save.boundingBox())!.y).toBeCloseTo(before!.y, 0)
    expect(await page.evaluate(() => scrollY)).toBe(scroll)
    await page.unroute('**/api/registration/commissions/demo-wt-1')
  }
})
