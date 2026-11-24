import { expect, type Locator, type Page } from '@playwright/test'
export async function pickRangeDay(page: Page, date: string) {
  const calendar = page.locator('.flatpickr-calendar.open')
  await expect(calendar).toBeVisible()
  const [year, month] = date.split('-')
  await calendar.locator('.cur-year').fill(year!)
  await calendar.locator('.cur-year').press('Enter')
  await calendar.locator('.flatpickr-monthDropdown-months').selectOption(String(Number(month) - 1))
  await calendar.locator(`.flatpickr-day[aria-label="${date}"]:not(.prevMonthDay):not(.nextMonthDay)`).click()
}
export async function pickDateRange(page: Page, input: Locator, from: string, to: string) {
  await input.click()
  await pickRangeDay(page, from)
  await pickRangeDay(page, to)
  await expect(page.locator('.flatpickr-calendar.open')).toHaveCount(0)
}
