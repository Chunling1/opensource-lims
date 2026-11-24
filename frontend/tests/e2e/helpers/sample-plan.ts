import type { Page } from '@playwright/test'

export async function selectGeneralSamplePlan(page: Page) {
  await page.getByRole('button', { name: '选择检测方案', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '选择检测方案', exact: true })
  await dialog.getByRole('button', { name: '综合检测部', exact: true }).click()
  await dialog.getByRole('radio', { name: '选择 常规检测方案', exact: true }).check()
  await dialog.getByRole('button', { name: '确定', exact: true }).click()
}
