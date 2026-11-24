import { readFile } from 'node:fs/promises'
import { expect, test } from '@playwright/test'

for (const width of [1440, 390]) test(`complete report download and upload at ${width}px`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 1050 })
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  const button = page.getByRole('button', { name: '下载完整报告', exact: true })
  await expect(button).toBeEnabled()
  await expect(page.getByRole('button', { name: '下载模板', exact: true })).toBeEnabled()
  await page.screenshot({ path: testInfo.outputPath(`complete-download-${width}.png`), fullPage: true })
  const downloaded = page.waitForEvent('download')
  await button.click()
  const file = await downloaded
  expect(file.suggestedFilename()).toContain('完整报告.docx')
  const path = await file.path()
  expect((await readFile(path!)).toString()).toContain('自动生成完整报告')
  await expect(page.getByRole('tab', { name: '报告模板', exact: true })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('button', { name: '上传文件', exact: true }).click()
  await page.getByLabel('上传完整报告', { exact: false }).setInputFiles({ name: file.suggestedFilename(), mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: await readFile(path!) })
  await page.getByRole('alert', { name: '完整报告上传确认' }).getByRole('button', { name: '确认上传', exact: true }).click()
  await expect(page.getByRole('button', { name: file.suggestedFilename(), exact: true })).toBeVisible()
})

test('unsupported plans and layouts disable only the complete report download', async ({ page }, testInfo) => {
  await page.goto('/#/testing/data-changes/demo-yp-80/report')
  await expect(page.getByRole('button', { name: '下载完整报告', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '下载模板', exact: true })).toBeEnabled()
  await expect(page.getByText('暂不支持', { exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('complete-download-disabled.png'), fullPage: true })
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  await page.getByLabel('首页版式', { exact: true }).selectOption('extended')
  await expect(page.getByRole('button', { name: '下载完整报告', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '下载模板', exact: true })).toBeEnabled()
  await page.getByLabel('首页版式', { exact: true }).selectOption('standard')
  await expect(page.getByRole('button', { name: '下载完整报告', exact: true })).toBeEnabled()
})
