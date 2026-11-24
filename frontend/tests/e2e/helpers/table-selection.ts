import { expect, type Locator } from '@playwright/test'

/** Independent/leaf rows must never change selection through their text or padding. */
export async function checkOnlyWithControl(row: Locator, control: Locator) {
  await expect(control).not.toBeChecked()
  const cell = row.locator('td:not(:has(a, button, input, select, textarea, label))').first()
  await cell.click({ position: { x: 2, y: 2 } })
  await cell.click()
  await expect(control).not.toBeChecked()
  await control.check()
  await expect(control).toBeChecked()
  await cell.click({ position: { x: 2, y: 2 } })
  await cell.click()
  await expect(control).toBeChecked()
}
