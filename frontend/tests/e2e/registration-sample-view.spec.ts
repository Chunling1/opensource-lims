import { test, expect, type Locator } from '@playwright/test'
import { emptySampleSubproject } from '../../src/types/commissions/sampleForm'
const headers = { 'X-Demo-Actor': 'admin' }
async function fields(panel: Locator) {
  return panel.locator('input[id], textarea[id], select[id]').evaluateAll(nodes => nodes.map(node => {
    const input = node as HTMLInputElement
    return { id: input.id, tag: input.tagName, value: input.value, checked: input.type === 'checkbox' ? input.checked : undefined, rows: input.getAttribute('rows'), width: input.closest('[class*="col-"]')?.className }
  }))
}
for (const workspace of ['registration', 'review'] as const) {
  test(`${workspace} sample view reuses the complete form and preserves saved values read-only`, async ({ page }, testInfo) => {
    const root = `/commissions/${workspace}`, seedId = workspace === 'review' ? 'demo-yp-2' : 'demo-yp-1'
    await page.goto(`/#${root}`)
    await expect(page.getByRole('table', { name: '委托列表', exact: true })).toBeVisible()
    const record = await (await page.request.get(`/api/registration/samples/${seedId}`, { headers })).json()
    const defaults = await (await page.request.get('/api/registration/samples/defaults', { headers })).json()
    const input = { ...record, notes: '第一行备注\n第二行备注', details: { ...record.details,
      testPlanId: 'pressure-2', testBasisIds: ['pressure-2-basis-1', 'pressure-2-basis-2'], testBasisSeparators: ['\n'],
      useAssessmentStandard: true, assessmentStandardIds: ['pressure-2-basis-3'], assessmentStandardSeparators: [],
      manufacturer: '生产单位甲；生产单位乙', productionDate: '2026-09-01', requestedTestDate: '2026-09-25',
      internalNotes: '内部备注', samplingOrganization: '抽样单位甲', standardPrice: '125.50',
      reportSettings: { formatId: 'product', titleId: 'default_lab', languageId: 'en', layoutId: 'extended' },
      subprojects: [{ ...emptySampleSubproject(), ...defaults.subprojectOptions[0], id: 'view-subproject', amount: '125.50', notes: '子项目备注' }],
    } }
    const savedResponse = await page.request.post('/api/registration/samples', { headers, data: { input } })
    expect(savedResponse.ok(), await savedResponse.text()).toBe(true)
    const created = await savedResponse.json(), id = created.id
    if (workspace === 'review') {
      const completed = await page.request.post(`/api/registration/samples/${id}/actions`, { headers, data: { actionId: 'complete', version: created.version } })
      expect(completed.ok(), await completed.text()).toBe(true)
    }
    const saved = await (await page.request.get(`/api/registration/samples/${id}`, { headers })).json()
    await page.goto(`/#${root}/samples/${id}/edit`)
    const form = page.getByRole('form', { name: '样品表单', exact: true })
    await expect(form.locator('#sample-test-basis')).toHaveValue(saved.details.testBasis)
    await expect(form.locator('#sample-test-basis')).toHaveAttribute('rows', '1')
    await expect(form.getByLabel('首页版式', { exact: true })).toHaveCount(0)
    const samplePanel = form.getByRole('tabpanel', { name: '样品信息', exact: true })
    const before = await fields(samplePanel)
    const sections = await samplePanel.locator('.card-title').allTextContents()
    await form.getByRole('tab', { name: '委托信息', exact: true }).click()
    const orderValues = await form.getByRole('tabpanel', { name: '委托信息', exact: true }).locator('input[id],textarea[id],select[id]').evaluateAll(nodes => nodes.map(node => ({ id: node.id, value: (node as HTMLInputElement).value })))
    await page.route('**/api/registration/test-bases/query', route => route.abort())
    let writes = 0
    page.on('request', request => { if (request.method() === 'PUT' && request.url().includes('/samples/')) writes++ })
    await page.goto(`/#${root}/samples/${id}`)
    await expect(form.locator('#sample-name')).toHaveValue(saved.name)
    expect(await fields(samplePanel)).toEqual(before)
    expect(await samplePanel.locator('.card-title').allTextContents()).toEqual(sections)
    await expect(form.locator('#sample-test-basis')).toHaveValue(saved.details.testBasis)
    await expect(form.locator('#sample-assessment')).toHaveValue(saved.details.assessmentStandard)
    await expect(form.locator('#sample-test-basis')).not.toBeEditable()
    await expect(form.locator('#sample-test-basis')).toHaveAttribute('rows', '1')
    await expect(form.getByLabel('首页版式', { exact: true })).toHaveCount(0)
    await expect(form.locator('#sample-manufacturer')).not.toBeEditable()
    await expect(form.locator('#sample-category')).toBeDisabled()
    await expect(form.locator('#report-setting-formatId')).toBeDisabled()
    await expect(form.getByRole('button', { name: /保存|选择检测方案|选择检测依据|选择评定标准|选择生产单位/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '更多操作', exact: true })).toHaveCount(0)
    await form.getByRole('radio', { name: `选择子项目 ${defaults.subprojectOptions[0].name}` }).check()
    await form.getByRole('button', { name: '查看', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: '查看子项目', exact: true })
    await expect(dialog.getByLabel('子项金额', { exact: true })).toHaveValue('125.50')
    await expect(dialog.getByLabel('子项金额', { exact: true })).not.toBeEditable()
    await dialog.getByRole('button', { name: '返回', exact: true }).click()
    await form.getByRole('tab', { name: '委托信息', exact: true }).click()
    for (const field of orderValues.filter(field => field.id !== 'commission-handlingDepartmentId')) await expect(form.locator(`#${field.id}`)).toHaveValue(field.value)
    await expect(form.locator('#commission-customer')).not.toBeEditable()
    await expect(form.getByRole('tabpanel', { name: '委托信息', exact: true }).getByRole('button')).toHaveCount(0)
    await form.getByRole('tab', { name: '样品信息', exact: true }).click()
    for (const [width, theme] of [[1440, 'light'], [390, 'dark']] as const) {
      await page.setViewportSize({ width, height: 900 })
      await page.evaluate(value => document.documentElement.setAttribute('data-bs-theme', value), theme)
      await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`sample-view-${width}.png`), fullPage: true })
    }
    await form.dispatchEvent('submit')
    expect(writes).toBe(0)
    expect(await (await page.request.get(`/api/registration/samples/${id}`, { headers })).json()).toEqual(saved)
  })
}
