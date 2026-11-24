import { readFile } from 'node:fs/promises'
import { test, expect } from '@playwright/test'

test('customizer retains every original control and preview structure', async ({ page }, testInfo) => {
  const original = await readFile('docs/HTML/Master/src/partials/customizer.html', 'utf8')
  await page.goto('/#/dashboard')
  await page.getByRole('button', { name: '打开主题设置' }).click()
  await expect(page.locator('#theme-settings-offcanvas')).toHaveClass(/\bshow\b/)
  const differences = await page.evaluate(html => {
    const source = new DOMParser().parseFromString(html, 'text/html').querySelector('#theme-settings-offcanvas')!
    const target = document.querySelector('#theme-settings-offcanvas')!
    const differences: string[] = []
    for (const input of source.querySelectorAll('input')) {
      const copy = target.querySelector<HTMLInputElement>(`#${input.id}`)
      if (!copy || copy.type !== input.type || copy.name !== input.name || copy.value !== input.value || copy.className !== input.className) differences.push(`input ${input.id}`)
      const label = source.querySelector<HTMLLabelElement>(`label[for="${input.id}"]`)!
      const copyLabel = target.querySelector<HTMLLabelElement>(`label[for="${input.id}"]`)
      if (!copyLabel || copyLabel.className !== label.className) { differences.push(`label ${input.id}`); continue }
      const shape = (element: Element) => [...element.querySelectorAll('*')].map(child => `${child.tagName}:${child.className}`).join('|')
      if (shape(label) !== shape(copyLabel)) differences.push(`preview ${input.id}`)
    }
    const ids = [...target.querySelectorAll('[id]')].map(element => element.id)
    if (new Set(ids).size !== ids.length) differences.push('duplicate IDs')
    return differences
  }, original)
  expect(differences).toEqual([])

  await page.locator('#layout-position').scrollIntoViewIfNeeded()
  await page.screenshot({ path: testInfo.outputPath('customizer-middle.png') })
  await page.getByRole('button', { name: '渐变色', exact: true }).click()
  await expect(page.locator('#collapseBgGradient')).toBeVisible()
  await page.getByTestId('theme-label-sidebar-gradient-3').click()
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'gradient-3')
  await page.locator('#sidebar-img').scrollIntoViewIfNeeded()
  await expect.poll(() => page.locator('#sidebar-img img').evaluateAll(images => images.every(image => (image as HTMLImageElement).naturalWidth > 0))).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('customizer-bottom.png') })
  const swatches = await page.locator('#theme-primary-color label').evaluateAll(labels => labels.map(label => getComputedStyle(label).backgroundColor))
  expect(new Set(swatches).size).toBe(4)
  expect(swatches).not.toContain('rgba(0, 0, 0, 0)')
  await page.getByTestId('theme-label-colors-purple').focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('html')).toHaveAttribute('data-theme-colors', 'purple')
  await page.getByTestId('theme-label-theme-galaxy').click()
  await page.getByTestId('theme-label-body-img-2').click()
  await expect(page.locator('html')).toHaveAttribute('data-body-image', 'img-2')
  const backgrounds = await page.locator('#body-img label[data-body-image]:not([data-body-image="none"])').evaluateAll(labels => labels.map(label => getComputedStyle(label).backgroundImage))
  expect(backgrounds).not.toContain('none')
  await page.screenshot({ path: testInfo.outputPath('customizer-galaxy-backgrounds.png') })
})
