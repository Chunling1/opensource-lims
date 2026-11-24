import { expect, type Page } from '@playwright/test'

export async function toolbarButton(page: Page, label: string, name: string) {
  const toolbar = page.getByRole('group', { name: `${label}工具栏`, exact: true })
  const button = toolbar.getByRole('button', { name, exact: true })
  if (!await button.isVisible()) await toolbar.getByRole('button', { name: `${label}更多操作`, exact: true }).click()
  await expect(button).toBeVisible()
  return button
}

export async function openToolbarExport(page: Page, label: string) {
  const toolbar = page.getByRole('group', { name: `${label}工具栏`, exact: true })
  const button = toolbar.getByRole('button', { name: '导出', exact: true })
  if (await button.isVisible()) await button.click()
  else await toolbar.getByRole('button', { name: `${label}更多操作`, exact: true }).click()
}
