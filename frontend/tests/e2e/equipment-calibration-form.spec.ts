import { test, expect } from '@playwright/test'
import { toolbarButton } from './helpers/toolbar'

for (const width of [1440, 390]) test(`calibration form follows equipment context and responsive field layout at ${width}`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 1000 })
  await page.goto('/#/quality/equipment/ledger')
  await page.getByRole('button', { name: '新增', exact: true }).click()
  const equipment = page.getByRole('dialog', { name: '新增设备', exact: true })
  for (const [label, value] of [['档案号', 'CAL-001'], ['仪器设备名称', '电导率仪'], ['规格型号', 'ECTes11+'], ['仪器出厂号', '2919977'], ['生产厂家', 'EUTECH instruments']]) {
    await equipment.getByLabel(label!, { exact: true }).fill(value!)
  }
  await equipment.getByRole('tab', { name: '检定记录', exact: true }).click()
  await equipment.getByRole('button', { name: '新增', exact: true }).click()
  const form = page.getByRole('dialog', { name: '新增检定记录', exact: true })
  for (const [label, value] of [['设备编号', 'CAL-001'], ['设备名称', '电导率仪'], ['规格型号', 'ECTes11+'], ['出厂编号', '2919977'], ['生产厂家', 'EUTECH instruments']]) {
    await expect(form.getByLabel(label!, { exact: true })).toHaveValue(value!)
    await expect(form.getByLabel(label!, { exact: true })).toHaveAttribute('readonly', '')
  }
  const today = await page.evaluate(() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` })
  await expect(form.getByLabel('检定日期', { exact: true })).toHaveValue(today)
  await expect(form.getByLabel('下次检定日期', { exact: true })).toHaveValue(today)
  const codeBox = await form.getByLabel('设备编号', { exact: true }).boundingBox()
  const modelBox = await form.getByLabel('规格型号', { exact: true }).boundingBox()
  const nameBox = await form.getByLabel('设备名称', { exact: true }).boundingBox()
  const conclusionBox = await form.getByLabel('检定结论', { exact: true }).boundingBox()
  if (width > 768) {
    expect(Math.abs(codeBox!.y - modelBox!.y)).toBeLessThan(2)
    expect(nameBox!.width).toBeGreaterThan(codeBox!.width * 1.8)
    expect(Math.abs(nameBox!.width - conclusionBox!.width)).toBeLessThan(2)
  } else {
    expect(modelBox!.y).toBeGreaterThan(codeBox!.y)
    expect(await form.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
  }
  await form.getByLabel('检定单位', { exact: true }).fill('计量中心')
  await form.getByLabel('证书号', { exact: true }).fill('CERT-001')
  await form.getByLabel('检定结论', { exact: true }).fill('合格')
  await form.getByLabel('检定周期', { exact: true }).fill('12个月')
  await form.screenshot({ path: info.outputPath(`calibration-${width}.png`) })
  await form.getByRole('button', { name: '确认', exact: true }).click()
  await expect(equipment.getByRole('cell', { name: 'CERT-001', exact: true })).toBeVisible()
  await equipment.getByRole('button', { name: '新增', exact: true }).click()
  await form.getByLabel('证书号', { exact: true }).fill('CANCELLED')
  await form.getByRole('button', { name: '取消', exact: true }).click()
  await expect(equipment.getByRole('cell', { name: 'CANCELLED', exact: true })).toHaveCount(0)
  await equipment.getByRole('checkbox', { name: /选择检定记录 计量中心/ }).check()
  await (await toolbarButton(page, '检定记录', '查看')).click()
  const view = page.getByRole('dialog', { name: '查看检定记录', exact: true })
  await expect(view.getByLabel('设备编号', { exact: true })).toHaveValue('CAL-001')
  await expect(view.getByLabel('证书号', { exact: true })).toHaveValue('CERT-001')
  await expect(view.getByLabel('证书号', { exact: true })).toBeDisabled()
  await expect(view.getByLabel('检定日期', { exact: true })).toBeDisabled()
  await view.getByRole('button', { name: '返回', exact: true }).click()
})
