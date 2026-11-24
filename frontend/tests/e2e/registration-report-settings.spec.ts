import { expect, test, type Page } from '@playwright/test'
import { selectGeneralSamplePlan } from './helpers/sample-plan'
import type { ReportSettingsConfig } from '../../src/types/commissions/reportSettings'

const newSample = '/#/commissions/registration/samples/new?commissionId=demo-wt-1'
const configUrl = '**/api/registration/samples/report-settings-config'
function controls(page: Page) {
  const card = page.getByRole('region', { name: '报告设置', exact: true })
  return { card, format: card.getByLabel('报告格式', { exact: true }), title: card.getByLabel('报告标题', { exact: true }), language: card.getByLabel('报告语言', { exact: true }), layout: card.getByLabel('首页版式', { exact: true }) }
}
async function required(page: Page) {
  await selectGeneralSamplePlan(page)
  await page.getByLabel('工程/产品名称', { exact: false }).fill('报告设置测试样品')
  await page.getByLabel('检测类别', { exact: false }).selectOption('委托')
}

test('report settings cascade, stay independent from category and persist across edit and view', async ({ page }, testInfo) => {
  await page.goto(newSample)
  const { card, format, title, language, layout } = controls(page)
  await expect(format).toHaveValue(''); await expect(title).toHaveValue('')
  await expect(language).toHaveValue('zh'); await expect(layout).toHaveCount(0)
  await expect(page.getByRole('button', { name: '选择报告标题', exact: true })).toHaveCount(0)
  await format.selectOption('product'); await title.selectOption('energy'); await language.selectOption('en')
  await page.getByLabel('检测类别', { exact: false }).selectOption('校准')
  await expect(format).toHaveValue('product')
  await format.selectOption('engineering')
  await expect(title).toHaveValue('energy'); await expect(language).toHaveValue('en')
  await expect(layout).toHaveCount(0)
  await format.selectOption('inspection')
  await expect(title).toHaveValue('default_lab'); await expect(title).toBeDisabled()
  await expect(title.locator('option[value="energy"]')).toBeDisabled()
  await expect(page.locator('.toast.show')).toContainText('报告标题：示例检测')
  await format.selectOption('product'); await title.selectOption('solar')
  await format.selectOption('calibration')
  await expect(title).toHaveValue('default_lab'); await expect(title).toBeDisabled()
  await expect(title.locator('option[value="solar"]')).toBeDisabled()
  await expect(page.locator('.toast.show')).toContainText('报告标题：示例检测')
  await expect(language).toHaveValue('zh'); await expect(language).toBeDisabled()
  await expect(language.locator('option[value="en"]')).toBeDisabled()
  await format.selectOption('sampling')
  await expect(title).toHaveValue('default_lab'); await expect(language).toBeEnabled()
  await language.selectOption('en'); await title.selectOption('solar')
  for (const [width, theme] of [[1440, 'light'], [390, 'dark']] as const) {
    await page.setViewportSize({ width, height: 950 })
    await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await card.screenshot({ path: testInfo.outputPath(`report-settings-${width}-${theme}.png`) })
  }
  await required(page)
  const response = page.waitForResponse(r => r.url().endsWith('/api/registration/samples') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  const saved = await (await response).json()
  expect(saved.details.reportSettings).toEqual({ formatId: 'sampling', titleId: 'solar', languageId: 'en', layoutId: 'standard' })
  expect(saved.details).not.toHaveProperty('reportFormat'); expect(saved.details).not.toHaveProperty('reportTitleCn')
  await expect(page).toHaveURL(/\/edit/)
  await page.reload()
  await expect(format).toHaveValue('sampling'); await expect(title).toHaveValue('solar'); await expect(language).toHaveValue('en'); await expect(layout).toHaveCount(0)
  await page.goto(`/#/commissions/registration/samples/${saved.id}`)
  await expect(title).toHaveValue('solar'); await expect(title).toBeDisabled(); await expect(format).toBeDisabled()
  await expect(layout).toHaveCount(0)
})

test('configuration failure retries without losing the form and backend data can enable calibration English', async ({ page }) => {
  let unavailable = true
  await page.route(configUrl, async route => {
    if (unavailable) { await route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '报告配置暂不可用' } } }); return }
    const response = await route.fetch(), config: ReportSettingsConfig = await response.json()
    config.combinations.push({ formatId: 'calibration', titleId: 'default_lab', languageId: 'en', layoutId: 'standard' })
    await route.fulfill({ response, json: config })
  })
  await page.goto(newSample)
  const { card, format, title, language } = controls(page)
  await expect(card.getByText('报告配置暂不可用')).toBeVisible()
  await expect(format).toBeDisabled(); await required(page)
  let submissions = 0
  page.on('request', r => { if (r.url().endsWith('/api/registration/samples') && r.method() === 'POST') submissions++ })
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator('.toast.show')).toContainText('请先加载报告设置配置')
  expect(submissions).toBe(0)
  unavailable = false
  await card.getByRole('button', { name: '重试', exact: true }).click()
  await expect(format).toBeEnabled(); await expect(language).toHaveValue('zh')
  await expect(page.getByLabel('工程/产品名称', { exact: false })).toHaveValue('报告设置测试样品')
  await format.selectOption('calibration'); await expect(title).toHaveValue('default_lab'); await expect(title).toBeDisabled()
  await expect(language).toBeEnabled(); await language.selectOption('en'); await expect(language).toHaveValue('en')
})

test('configuration conflicts refresh only the configuration and preserve values for user review', async ({ page }) => {
  let updated = false, configRequests = 0, submissions = 0
  await page.route(configUrl, async route => {
    configRequests++
    const response = await route.fetch(), config: ReportSettingsConfig = await response.json()
    if (updated) {
      config.version = '2'
      config.combinations = config.combinations.filter(row => row.formatId !== 'product' || ['default_lab', 'energy'].includes(row.titleId))
    }
    await route.fulfill({ response, json: config })
  })
  await page.route('**/api/registration/samples', async route => {
    if (route.request().method() !== 'POST') return route.continue()
    submissions++; updated = true
    await route.fulfill({ status: 409, json: { error: { code: 'VERSION_CONFLICT', message: '报告设置配置已更新，请检查最新选项后重新保存。', fieldErrors: { reportSettings: '配置已更新。' } } } })
  })
  await page.goto(newSample); await required(page)
  const { format, title, language } = controls(page)
  await format.selectOption('product'); await title.selectOption('solar'); await language.selectOption('en')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(title).toHaveAttribute('aria-invalid', 'true')
  await expect(title).toHaveValue('solar')
  await expect(page.getByLabel('工程/产品名称', { exact: false })).toHaveValue('报告设置测试样品')
  expect(configRequests).toBe(2); expect(submissions).toBe(1)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator('.toast.show')).toContainText('请检查报告设置中标记的选项')
  expect(submissions).toBe(1)
  await format.selectOption('engineering')
  await title.selectOption('solar')
  await format.selectOption('product')
  await expect(title).toHaveValue('')
  await expect(page.locator('.toast.show').filter({ hasText: '报告标题：请重新选择' })).toBeVisible()
})

test('editing retains a saved selection that a new configuration no longer permits', async ({ page }) => {
  await page.goto(newSample); await required(page)
  const { format, title } = controls(page)
  await format.selectOption('product'); await title.selectOption('solar')
  await page.getByRole('button', { name: '保存', exact: true }).click(); await expect(page).toHaveURL(/\/edit/)
  await page.route(configUrl, async route => {
    const response = await route.fetch(), config: ReportSettingsConfig = await response.json()
    config.combinations = config.combinations.filter(row => row.titleId !== 'solar')
    await route.fulfill({ response, json: config })
  })
  await page.reload()
  await expect(title).toHaveValue('solar'); await expect(title).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByLabel('工程/产品名称', { exact: false })).toHaveValue('报告设置测试样品')
  await title.selectOption('default_lab'); await expect(title).toHaveAttribute('aria-invalid', 'false')
})
