import { test, expect, type Page } from '@playwright/test'

async function fillSample(page: Page, name: string) {
  await page.goto('/#/commissions/registration/samples/new?commissionId=demo-wt-1')
  await page.getByLabel('工程/产品名称', { exact: false }).fill(name)
}
async function themePanel(page: Page) { await page.getByRole('button', { name: '打开主题设置' }).click(); await expect(page.locator('#theme-settings-offcanvas')).toBeVisible() }
async function closeTheme(page: Page) { await page.getByRole('button', { name: '关闭主题设置' }).click(); await expect(page.locator('.offcanvas-backdrop')).toHaveCount(0) }

test('theme and layout switches preserve draft; preferences survive refresh', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message))
  await page.route('https://cdn.example.invalid/**', route => route.abort())
  await fillSample(page, '保留中的登记内容')
  await themePanel(page)
  const previews = page.locator('#theme-settings-offcanvas img[data-theme-preview]')
  await expect(previews).toHaveCount(11)
  await expect.poll(() => previews.evaluateAll(images => images.every(image => image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0 && new URL(image.src).origin === location.origin))).toBe(true)
  for (const layout of ['horizontal', 'twocolumn', 'semibox', 'vertical']) {
    await page.locator(`[data-testid="theme-label-layout-${layout}"]`).click()
    await expect(page.locator('html')).toHaveAttribute('data-layout', layout)
    await expect(page.getByLabel('工程/产品名称', { exact: false })).toHaveValue('保留中的登记内容')
  }
  for (const theme of ['saas', 'corporate', 'galaxy', 'material', 'creative', 'minimal', 'modern', 'interactive', 'classic', 'vintage', 'default']) {
    await page.locator(`[data-testid="theme-label-theme-${theme}"]`).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await expect(page.getByLabel('工程/产品名称', { exact: false })).toHaveValue('保留中的登记内容')
  }
  await page.locator('[data-testid="theme-label-mode-dark"]').click()
  await closeTheme(page)
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark')
  await themePanel(page)
  await page.getByRole('button', { name: '恢复默认主题' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'light')
  await closeTheme(page)
  expect(errors).toEqual([])
})

test('invalid theme storage safely falls back to defaults', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('lims.theme.v1', '{broken'))
  await page.goto('/#/dashboard')
  await expect(page.locator('html')).toHaveAttribute('data-layout', 'vertical')
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'light')
  await expect(page.getByRole('heading', { name: '工作台', exact: true })).toBeVisible()
})
