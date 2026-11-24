import { expect, test } from '@playwright/test'
import { openReportFiles } from './helpers/reportFiles'

test('queued report survives leaving and refresh; transient status failures recover without resubmission', async ({ page }, info) => {
  test.setTimeout(60000)
  let submissions = 0, failures = 0, loseProgress = false
  const ids = new Set<string>()
  await page.route('**/data-entry/combine', async route => {
    submissions++
    await route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), scenario: 'slow' }) })
  })
  await page.route('**/samples/demo-yp-76/data-entry', async route => {
    if (loseProgress && failures++ < 2) {
      await route.fulfill({ status: 503, json: { error: { code: 'UNAVAILABLE', message: '进度查询暂不可用' } } })
      return
    }
    const response = await route.fetch(), result = await response.json()
    if (result.job) ids.add(result.job.id)
    await route.fulfill({ response })
  })
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  await openReportFiles(page)
  await page.getByRole('button', { name: '预览报告', exact: true }).click()
  await expect(page.getByRole('heading', { name: '已加入报告生成队列' })).toBeVisible()
  await expect(page.getByRole('status', { name: '报告生成进度' })).toContainText('后台任务会继续')
  const generate = page.getByRole('button', { name: '生成预览', exact: true })
  await expect(generate).toBeDisabled()
  await expect(generate.locator('.spinner-border')).toBeVisible()
  await page.screenshot({ path: info.outputPath('report-queued.png'), fullPage: true, animations: 'disabled' })
  await page.getByRole('button', { name: '返回列表', exact: true }).click()
  await expect(page).toHaveURL(/#\/testing\/data-entry$/)
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  await expect(page.getByRole('status', { name: '报告生成进度' })).toBeVisible()
  await page.reload()
  await expect(generate).toBeDisabled()
  loseProgress = true
  await expect(page.getByRole('alert').filter({ hasText: '暂时无法获取最新进度' })).toBeVisible()
  await expect(generate).toBeDisabled()
  await expect(page.getByRole('button', { name: '刷新状态', exact: true })).toBeEnabled()
  await expect(page.getByRole('alert').filter({ hasText: '暂时无法获取最新进度' })).toHaveCount(0, { timeout: 15000 })
  expect(failures).toBeGreaterThanOrEqual(3)
  expect(submissions).toBe(1)
  expect(ids.size).toBe(1)
  await page.setViewportSize({ width: 390, height: 900 })
  await page.evaluate(() => document.documentElement.setAttribute('data-bs-theme', 'dark'))
  await page.screenshot({ path: info.outputPath('report-waiting-mobile-dark.png'), fullPage: true, animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await expect(page.getByRole('tab', { name: '报告模板', exact: true })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: '报告预览', exact: true }).click()
  await expect(generate).toBeDisabled()
  await expect(page.getByRole('tab', { name: '报告确认', exact: true })).toBeDisabled()
  await expect(page.getByRole('tab', { name: '报告确认', exact: true })).toHaveAccessibleDescription('报告预览就绪后可确认')
  expect(submissions).toBe(1)
})
