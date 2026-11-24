import { test, expect, type Page } from '@playwright/test'

async function open(page: Page, code: string) {
  await page.getByRole('button', { name: `${code} 更多操作`, exact: true }).click()
  const menu = page.getByRole('menu', { name: `${code} 更多操作`, exact: true })
  await expect(menu.getByRole('menuitem').last()).toHaveText('附件管理')
  await menu.getByRole('menuitem', { name: '附件管理', exact: true }).click()
  return page.getByRole('dialog', { name: '附件', exact: true })
}

for (const workspace of ['review', 'query']) {
  const root = `/commissions/${workspace}`
  const list = `/#${root}?scope=all&current=demo-wt-1&cSort=code&cDirection=asc&sSort=code&sDirection=asc`
  for (const width of [1440, 390]) test(`${workspace} list attachments support CRUD and preserve selection at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(list)
    const selection = page.getByRole('checkbox', { name: '选择样品 SP2026090002', exact: true })
    await selection.check()
    const url = page.url(), reloads: string[] = []
    for (const [kind, code] of [['commissions', 'WT202609001'], ['samples', 'SP2026090002']]) {
      const dialog = await open(page, code!)
      const track = (request: import('@playwright/test').Request) => {
        if (/\/api\/registration\/(commissions\/query|samples\/query|commissions\/[^/]+\/summary)$/.test(request.url())) reloads.push(request.url())
      }
      page.on('request', track)
      const file = { name: `${kind}.txt`, mimeType: 'text/plain', buffer: Buffer.from('attachment contents') }
      const upload = dialog.getByLabel('添加附件', { exact: false })
      await upload.setInputFiles(file)
      await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
      const download = page.waitForEvent('download')
      await dialog.getByRole('button', { name: file.name, exact: true }).click()
      expect((await download).suggestedFilename()).toBe(file.name)
      await dialog.getByRole('button', { name: `删除附件 ${file.name}`, exact: true }).click()
      await dialog.getByRole('button', { name: '确认删除', exact: true }).click()
      await expect(dialog.getByRole('button', { name: file.name, exact: true })).toHaveCount(0)
      await upload.setInputFiles(file)
      await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
      for (const theme of ['light', 'dark']) {
        await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
        await expect(upload).toBeInViewport()
        expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
        await page.screenshot({ path: testInfo.outputPath(`${workspace}-${kind}-${width}-${theme}.png`) })
      }
      await dialog.getByRole('button', { name: '关闭', exact: true }).click()
      await expect(dialog).toBeHidden()
      await open(page, code!)
      await expect(dialog.getByRole('button', { name: file.name, exact: true })).toBeVisible()
      await expect(dialog.getByRole('button', { name: kind === 'samples' ? 'commissions.txt' : 'samples.txt', exact: true })).toHaveCount(0)
      await dialog.getByRole('button', { name: '关闭', exact: true }).click()
      await expect(dialog).toBeHidden()
      page.off('request', track)
    }
    expect(page.url()).toBe(url)
    expect(reloads).toEqual([])
    await expect(selection).toBeChecked()
    await expect(page.getByRole('checkbox', { name: '选择委托 WT202609001', exact: true })).toBeChecked()
    for (const path of ['samples/demo-yp-2', 'samples/demo-yp-2/edit', 'commissions/demo-wt-1', ...(workspace === 'review' ? ['samples/demo-yp-2/assess'] : [])]) {
      await page.goto(`/#${root}/${path}`)
      await expect(page.locator(path.startsWith('samples') ? '#sample-name' : '#commission-name')).toBeVisible()
      await expect(page.getByRole('region', { name: /^(样品|委托)附件$/ })).toHaveCount(0)
      await expect(page.getByLabel('添加附件', { exact: false })).toHaveCount(0)
    }
  })

  test(`${workspace} attachment controls follow backend permissions`, async ({ page }) => {
    await page.goto(list)
    for (const [kind, id, code] of [['commissions', 'demo-wt-1', 'WT202609001'], ['samples', 'demo-yp-2', 'SP2026090002']]) {
      await page.route(`**/api/registration/${kind}/${id}/attachments`, async route => {
        const response = await route.fetch()
        await route.fulfill({ response, json: { ...await response.json(), canManageAttachments: false, attachments: [{ id: 'fixture', name: 'history.txt', type: 'text/plain', size: 1, dataUrl: 'data:text/plain;base64,YQ==' }] } })
      })
      const dialog = await open(page, code!)
      await expect(dialog.getByLabel('添加附件', { exact: false })).toHaveCount(0)
      await expect(dialog.getByRole('button', { name: /删除附件/ })).toHaveCount(0)
      const download = page.waitForEvent('download')
      await dialog.getByRole('button', { name: 'history.txt', exact: true }).click()
      expect((await download).suggestedFilename()).toBe('history.txt')
      await dialog.getByRole('button', { name: '关闭', exact: true }).click()
      await expect(dialog).toBeHidden()
    }
  })
}
