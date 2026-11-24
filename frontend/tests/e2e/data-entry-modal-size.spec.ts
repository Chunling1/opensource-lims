import { expect, test, type Locator } from '@playwright/test'
import { selectGeneralSamplePlan } from './helpers/sample-plan'

async function measure(dialog: Locator) {
  return dialog.evaluate(element => {
    const content = element.querySelector('.modal-content')!, rect = content.getBoundingClientRect()
    const body = element.querySelector('.modal-body')!, bodyRect = body.getBoundingClientRect()
    const title = getComputedStyle(element.querySelector('.modal-title')!)
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, bodyHeight: bodyRect.height, font: title.fontFamily, fontSize: title.fontSize, fontWeight: title.fontWeight }
  })
}

test('record dialogs match the actual test-basis picker at desktop, laptop and mobile sizes', async ({ page, context }, info) => {
  await page.goto('/#/commissions/registration/samples/new?commissionId=demo-wt-1')
  await selectGeneralSamplePlan(page)
  await page.getByRole('button', { name: '选择检测依据', exact: true }).click()
  const basis = page.getByRole('dialog', { name: '选择检测依据', exact: true })
  await expect(basis).toBeFocused()
  await expect(basis.getByRole('table')).toBeVisible()
  const entry = await context.newPage()
  await entry.goto('/#/testing/data-entry/demo-yp-76')
  const measurements = []
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport); await entry.setViewportSize(viewport)
    const reference = await measure(basis)
    for (const [button, title] of [['查看修改记录', '修改记录'], ['查看问题记录', '问题记录']] as const) {
      await entry.getByRole('button', { name: button, exact: true }).click()
      const dialog = entry.getByRole('dialog', { name: title, exact: true })
      await expect(dialog).toBeFocused()
      await expect(dialog.getByRole('table')).toBeVisible()
      const actual = await measure(dialog)
      measurements.push({ viewport, title, reference, actual })
      for (const key of ['x', 'y', 'width', 'height'] as const) expect(actual[key], `${viewport.width}px ${title} ${key}`).toBeCloseTo(reference[key], 0)
      for (const key of ['font', 'fontSize', 'fontWeight'] as const) expect(actual[key]).toBe(reference[key])
      if (viewport.width === 1440) await dialog.screenshot({ path: info.outputPath(`${title}.png`) })
      await dialog.getByRole('button', { name: '关闭弹窗', exact: true }).click()
      await expect(dialog).toBeHidden()
    }
    if (viewport.width === 1440) await basis.screenshot({ path: info.outputPath('检测依据.png') })
  }
  console.log(JSON.stringify(measurements))
  await info.attach('dialog-measurements', { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' })
})
