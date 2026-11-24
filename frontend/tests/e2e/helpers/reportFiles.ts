import { expect, type Page } from '@playwright/test'

/** Follow the user's supplement path; already adopted records can switch freely. */
export async function openReportFiles(page: Page) {
  await expect(page.getByRole('tab', { name: '上传文件', exact: true })).toBeVisible()
  const adopt = page.getByRole('button', { name: '上传文件', exact: true })
  if (await adopt.isVisible() && await adopt.isEnabled()) await adopt.click()
  else await page.getByRole('tab', { name: '上传文件', exact: true }).click()
  await expect(page.getByRole('tab', { name: '上传文件', exact: true })).toHaveAttribute('aria-selected', 'true')
}
