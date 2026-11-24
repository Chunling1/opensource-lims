import { test, expect } from '@playwright/test'

test('commission fields render once in commission and sample create, edit and readonly views', async ({ page }) => {
  for (const kind of ['commissions', 'samples']) {
    for (const mode of ['new', 'edit', 'view']) {
      const id = kind === 'commissions' ? 'demo-wt-1' : 'demo-yp-1'
      const path = mode === 'new' ? `new${kind === 'samples' ? '?commissionId=demo-wt-1' : ''}` : `${id}${mode === 'edit' ? '/edit' : ''}`
      await page.goto(`/#/commissions/registration/${kind}/${path}`)
      if (kind === 'samples' && mode !== 'view') await page.getByRole('tab', { name: '委托信息', exact: true }).click()
      await expect(page.getByRole('region', { name: '委托基本信息', exact: true })).toBeVisible()
      for (const key of ['code', 'contract', 'contractParty', 'payer', 'invoiceType', 'handlingDepartmentId']) {
        await expect(page.locator(`[id="commission-${key}"]`)).toHaveCount(1)
      }
      const duplicates = await page.locator('[id^="commission-"]').evaluateAll(elements => {
        const ids = elements.map(el => el.id)
        return ids.filter((id, index) => ids.indexOf(id) !== index)
      })
      expect(duplicates, `${kind}/${mode} duplicated field IDs`).toEqual([])
      await expect(page.locator('[id="commission-customer"]')).toHaveCount(1)
      if (mode === 'view') {
        await expect(page.locator('textarea[id^="commission-"]:not([readonly]), input[id^="commission-"]:not([readonly]), select[id^="commission-"]')).toHaveCount(0)
        await expect(page.getByRole('button', { name: '选择合同', exact: true })).toHaveCount(0)
      }
    }
  }
})

test('customer textarea preserves editable multiline text on save, selection and readonly display', async ({ page }, testInfo) => {
  await page.goto('/#/commissions/registration/commissions/new')
  const field = page.getByLabel('委托单位', { exact: true })
  await expect(field).toHaveJSProperty('tagName', 'TEXTAREA')
  await field.fill('华清环境检测中心\n手填单位甲')
  await field.press('End'); await field.press('Enter')
  await expect(field).toHaveValue('华清环境检测中心\n手填单位甲\n')
  await field.fill('华清环境检测中心\n手填单位甲\n手填单位乙')
  await page.getByRole('button', { name: '选择委托单位', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '选择委托单位' })
  await expect(dialog.getByRole('checkbox', { name: '选择 华清环境检测中心', exact: true })).toBeChecked()
  await dialog.getByRole('checkbox', { name: '选择 远景建设集团', exact: true }).check()
  await dialog.getByRole('button', { name: '确定', exact: true }).click()
  await expect(field).toHaveValue('华清环境检测中心；手填单位甲；手填单位乙；远景建设集团')
  const text = '自行编辑的单位\n第二行单位\n第三行补充说明'
  await field.fill(text)
  for (const [width, theme] of [[1440, 'light'], [390, 'dark']] as const) {
    await page.setViewportSize({ width, height: 900 })
    await page.evaluate(t => document.documentElement.setAttribute('data-bs-theme', t), theme)
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await field.screenshot({ path: testInfo.outputPath(`organization-textarea-${width}.png`) })
  }
  const request = page.waitForRequest(r => r.url().endsWith('/commissions') && r.method() === 'POST')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  expect((await request).postDataJSON().input.customer).toBe(text)
  await expect(page).toHaveURL(/commissions\/[^/]+\/edit/)
  const editUrl = page.url()
  await page.reload()
  await expect(field).toHaveValue(text)
  await page.goto(editUrl.replace('/edit?', '?').replace(/\/edit$/, ''))
  await expect(field).toHaveValue(text)
  await expect(field).not.toBeEditable()
  await expect(page.getByRole('button', { name: '选择委托单位', exact: true })).toHaveCount(0)
})
