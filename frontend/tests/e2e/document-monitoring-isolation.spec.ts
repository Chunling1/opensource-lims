import { expect, test } from '@playwright/test'
import { randomUUID } from 'node:crypto'

test('monitoring isolates records and attachment drafts and refreshes when switching pages', async ({ page }) => {
  const headers = { 'X-Demo-Actor': 'admin' }, root = '/api/registration'
  const post = (path: string, data: unknown) => page.request.post(`${root}/${path}`, { headers, data })
  await page.request.post(`${root}/session`)
  const library = (await (await post('quality/documents/library/query', {})).json()).items[0]
  const monitoring = (await (await post('quality/documents/monitoring/query', {})).json()).items[0]
  expect((await post('quality/documents/library/detail', { id: monitoring.id })).ok()).toBe(false)
  expect((await post('quality/documents/monitoring/detail', { id: library.id })).ok()).toBe(false)
  const draftId = randomUUID(), file = { id: randomUUID(), name: 'plan.txt', type: 'text/plain', size: 4, dataUrl: 'data:text/plain;base64,cGxhbg==' }
  const upload = await post(`attachment-drafts/${draftId}/upload`, { scope: 'monitoring-document', recordId: monitoring.id, file })
  expect(upload.ok()).toBe(true)
  const reference = await upload.json()
  expect((await post('quality/documents/library/files', { id: library.id, version: library.version, files: [reference], attachmentDraftId: draftId })).ok()).toBe(false)
  expect((await post(`attachment-drafts/${draftId}/file`, { scope: 'document', recordId: monitoring.id, fileId: file.id })).ok()).toBe(false)
  expect((await post('quality/documents/monitoring/files', { id: monitoring.id, version: monitoring.version, files: [reference], attachmentDraftId: draftId })).ok()).toBe(true)
  const saved = await post(`attachment-drafts/${draftId}/file`, { scope: 'monitoring-document', recordId: monitoring.id, fileId: file.id })
  expect(saved.ok()).toBe(true); expect(await saved.text()).toBe('plan')
  const unchanged = await (await post('quality/documents/library/detail', { id: library.id })).json()
  expect(unchanged.version).toBe(library.version); expect(unchanged.files).toEqual([])
  await page.goto('/#/quality/documents/library')
  let table = page.getByRole('table', { name: '文件基础信息库列表', exact: true })
  await expect(table).toContainText('质量手册')
  await table.locator('tbody tr').first().getByRole('checkbox').check()
  await page.evaluate(() => { location.hash = '/quality/documents/monitoring' })
  table = page.getByRole('table', { name: '质量监控计划列表', exact: true })
  await expect(table).toContainText('年度质量监控计划'); await expect(table).not.toContainText('质量手册')
  await expect(table.locator('tbody input:checked')).toHaveCount(0)
  await page.evaluate(() => { location.hash = '/quality/documents/library' })
  table = page.getByRole('table', { name: '文件基础信息库列表', exact: true })
  await expect(table).toContainText('质量手册'); await expect(table).not.toContainText('年度质量监控计划')
  await expect(table.locator('tbody input:checked')).toHaveCount(0)
})
