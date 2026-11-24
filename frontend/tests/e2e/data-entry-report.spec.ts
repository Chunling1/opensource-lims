import { openReportFiles } from './helpers/reportFiles'
import { readFile } from 'node:fs/promises'
import { expect, test } from '@playwright/test'

test('uncertain template download reconciles the existing task without duplicate generation', async ({ page }) => {
  let submitted = 0
  await page.route('**/data-entry/template-tasks', async route => { submitted++; await route.fetch(); await route.abort() })
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  await page.getByRole('button', { name: '刷新核对', exact: true }).click()
  const downloaded = page.waitForEvent('download')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  expect((await downloaded).suggestedFilename()).toContain('standard')
  expect(submitted).toBe(1)
  await expect(page.getByTitle('报告模板预览', { exact: true })).toHaveCount(0)
})

test('one click saves the selected layout and downloads Word without PDF conversion; cached downloads preserve final preview', async ({ page }) => {
  let submitted = 0, templatePdf = 0
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/template-tasks')) { submitted++; expect(request.postDataJSON().wordOnly).toBe(true) }
    if (/template-tasks\/[^/]+\/pdf$/.test(request.url())) templatePdf++
  })
  await page.goto('/#/testing/data-entry/demo-yp-76')
  await page.locator('#trial-conclusion').fill('模板资料快照测试')
  await page.getByRole('button', { name: '报告填写', exact: true }).click()
  await page.getByRole('button', { name: '继续填写', exact: true }).click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.getByText('试验信息已保存。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '报告填写', exact: true }).click()
  const layout = page.getByLabel('首页版式', { exact: true })
  await layout.selectOption('extended')
  expect(submitted).toBe(0)
  await page.route('**/data-entry/save', route => route.fulfill({ status: 422, json: { error: { code: 'VALIDATION', message: '保存失败，请重试。' } } }))
  await page.getByRole('button', { name: '上传文件', exact: true }).click()
  await expect(page.getByText('保存失败，请重试。', { exact: true })).toBeVisible()
  await expect(layout).toHaveValue('extended')
  expect(submitted).toBe(0)
  await page.unroute('**/data-entry/save')
  let downloaded = page.waitForEvent('download')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  const word = await readFile((await (await downloaded).path())!)
  expect(word.toString()).toContain('模板资料快照测试')
  expect(word.toString()).toContain('扩展首页')
  await expect(page.getByRole('button', { name: '生成并预览', exact: true })).toHaveCount(0)
  await expect(page.getByTitle('报告模板预览', { exact: true })).toHaveCount(0)
  await page.getByRole('tab', { name: '报告预览', exact: true }).click()
  await expect(page.getByTitle('完整报告预览', { exact: true })).toBeVisible()
  downloaded = page.waitForEvent('download')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  await downloaded
  await page.getByRole('tab', { name: '报告预览', exact: true }).click()
  await expect(page.getByTitle('完整报告预览', { exact: true })).toBeVisible()
  await page.reload()
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  downloaded = page.waitForEvent('download')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  await downloaded
  expect(submitted).toBe(1); expect(templatePdf).toBe(0)
})

test('failed Word generation can retry from the same download button and readonly users can download existing results', async ({ page }) => {
  let submitted = 0
  await page.route('**/data-entry/template-tasks', async route => {
    submitted++
    await route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), ...(submitted === 1 ? { scenario: 'word-failure' } : {}) }) })
  })
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  await expect(page.getByRole('button', { name: '下载模板', exact: true })).toBeDisabled()
  await expect(page.getByText('模拟 Word 生成失败，请重试下载模板。', { exact: true })).toBeVisible()
  let downloaded = page.waitForEvent('download')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  await downloaded
  expect(submitted).toBe(2)
  await page.goto('/#/testing/data-entry/demo-yp-76/report?mode=view')
  await expect(page.getByLabel('首页版式', { exact: true })).toBeDisabled()
  downloaded = page.waitForEvent('download')
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await page.getByRole('button', { name: '下载模板', exact: true }).click()
  await downloaded
  expect(submitted).toBe(2)
})

test('batch append preserves successes and Conclusion order; final failure retries and readonly reports use final output', async ({ page }, info) => {
  test.setTimeout(60000)
  await page.goto('/#/testing/data-entry/demo-yp-76/report')
  await openReportFiles(page)
  const pdf = Buffer.from('%PDF-1.4\n%%EOF'), word = Buffer.from('504b0304', 'hex')
  await page.getByLabel('添加附加文件', { exact: false }).setInputFiles([
    { name: '附加一.pdf', mimeType: 'application/pdf', buffer: pdf },
    { name: '错误文件.pdf', mimeType: 'application/pdf', buffer: Buffer.from('invalid') },
    { name: 'Conclusion.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: word },
  ])
  await expect(page.getByRole('button', { name: 'Conclusion.docx', exact: true })).toBeVisible()
  await expect(page.locator('[data-upload-retry]')).toHaveAccessibleName(/文件内容与格式不一致.*点击重试/)
  await expect(page.getByText('结论内容文件', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '上移 Conclusion.docx', exact: true }).click()
  await expect(page.getByRole('button', { name: '上移 Conclusion.docx', exact: true })).toBeDisabled()
  await page.getByLabel('上传完整报告', { exact: false }).setInputFiles({ name: '已有完整报告.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: word })
  await page.getByRole('button', { name: '确认上传', exact: true }).click()
  await expect(page.getByRole('button', { name: '已有完整报告.docx', exact: true })).toBeVisible()
  await page.getByLabel('替换完整报告', { exact: false }).setInputFiles({ name: '替换报告.docx', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', buffer: word })
  await page.getByRole('button', { name: '确认替换', exact: true }).click()
  await expect(page.getByRole('button', { name: '已有完整报告.docx', exact: true })).toHaveCount(0)
  await page.route('**/data-entry/combine', async route => { await route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), scenario: 'failure' }) }) })
  await page.getByRole('tab', { name: '报告预览', exact: true }).click()
  await expect(page.getByRole('button', { name: '生成预览', exact: true })).toBeVisible()
  await page.unroute('**/data-entry/combine')
  await page.getByRole('button', { name: '生成预览', exact: true }).click()
  await expect(page.getByTitle('完整报告预览', { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('report-final-expanded.png'), fullPage: true })
  await page.goto('/#/testing/data-entry/demo-yp-76/report?mode=view')
  await expect(page.getByTitle('完整报告预览', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await expect(page.getByLabel('首页版式', { exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: '生成并预览', exact: true })).toHaveCount(0)
  await expect(page.locator('input[type=file]')).toHaveCount(0)
  await openReportFiles(page)
  await expect(page.getByRole('button', { name: '替换报告.docx', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: '数据录入', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '报告填写', exact: true })).toHaveCount(0)
  await page.goto('/#/testing/data-entry/demo-yp-76?mode=view')
  await expect(page.locator('#trial-conclusion')).toHaveAttribute('readonly', '')
  await expect(page).toHaveURL(/mode=view/)
  await expect(page.getByRole('button', { name: '报告填写', exact: true })).toHaveCount(0)
  await page.goto('/#/testing/data-entry/demo-yp-76/report?mode=view')
  await expect(page.getByTitle('完整报告预览', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: '报告模板', exact: true }).click()
  await expect(page.getByLabel('首页版式', { exact: true })).toBeDisabled()
})
