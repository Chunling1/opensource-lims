import { expect, test } from '@playwright/test'
import { checkOnlyWithControl } from './helpers/table-selection'

for (const workspace of ['registration', 'review', 'query']) test(`${workspace}: repeated row clicks preserve selection, scope and child page`, async ({ page }) => {
  // Review lists only completed registrations; the second demo commission has eligible samples.
  const initialIndex = workspace === 'review' ? 1 : 0
  await page.goto(`/#/commissions/${workspace}?current=demo-wt-${initialIndex + 1}&cSort=code&cDirection=asc&sSort=code&sDirection=asc`)
  const commissions = page.getByRole('table', { name: '委托列表', exact: true })
  const samples = page.getByRole('table', { name: '样品列表', exact: true })
  const rows = commissions.locator('tbody tr')
  await expect(rows.first()).toContainText('WT202609001')
  await expect(samples.locator('tbody input:enabled').first()).toBeVisible()
  const blank = rows.nth(initialIndex).locator('td').nth(1)
  const sampleControl = samples.locator('tbody input:enabled').first()
  await checkOnlyWithControl(sampleControl.locator('xpath=ancestor::tr'), sampleControl)
  const singleUrl = page.url()
  await blank.click({ position: { x: 2, y: 2 } })
  await expect(page).toHaveURL(singleUrl)
  await expect(samples.locator('tbody input:checked')).toHaveCount(1)

  const loaded = page.waitForResponse(r => r.url().endsWith('/samples/query') && r.request().postDataJSON().commissionIds?.length === 2)
  await rows.nth(initialIndex + 1).getByRole('checkbox').check()
  await loaded
  await expect(samples.locator('tbody input:enabled').first()).toBeVisible()
  await samples.locator('tbody input:enabled').first().check()
  const multiUrl = page.url()
  await blank.click({ position: { x: 2, y: 2 } })
  await expect(page).toHaveURL(multiUrl)
  await expect(commissions.locator('tbody input:checked')).toHaveCount(2)
  await expect(samples.locator('tbody input:checked')).toHaveCount(1)

  const allLoaded = page.waitForResponse(r => r.url().endsWith('/samples/query') && !r.request().postDataJSON().commissionIds)
  await page.getByRole('tab', { name: '全部样品', exact: true }).click()
  await allLoaded
  // Review's eligible fixture set fits on one page; the other workspaces exercise page two.
  if (workspace !== 'review') {
    const nextPage = page.waitForResponse(r => r.url().endsWith('/samples/query') && r.request().postDataJSON().page === 2)
    await page.getByRole('navigation', { name: '样品分页' }).getByRole('button', { name: '下一页', exact: true }).click()
    await nextPage
  }
  await expect(page.getByRole('navigation', { name: '样品分页' }).getByRole('button', { name: `第 ${workspace === 'review' ? 1 : 2} 页`, exact: true })).toHaveAttribute('aria-current', 'page')
  await samples.locator('tbody input:enabled').first().check()
  const allUrl = page.url()
  await blank.click({ position: { x: 2, y: 2 } })
  await expect(page).toHaveURL(allUrl)
  await expect(page.getByRole('tab', { name: '全部样品', exact: true })).toHaveAttribute('aria-selected', 'true')
  await expect(commissions.locator('tbody input:checked')).toHaveCount(2)
  await expect(samples.locator('tbody input:checked')).toHaveCount(1)

  // An explicit checkbox still removes a selection; an unselected row still switches parent.
  await rows.nth(initialIndex + 1).getByRole('checkbox').uncheck()
  await expect(commissions.locator('tbody input:checked')).toHaveCount(1)
  await rows.nth(4).locator('td').nth(1).click({ position: { x: 2, y: 2 } })
  await expect(rows.nth(4).getByRole('checkbox')).toBeChecked()
  await expect(rows.nth(initialIndex).getByRole('checkbox')).not.toBeChecked()
  await expect(page.getByRole('tab', { name: '当前委托', exact: true })).toHaveAttribute('aria-selected', 'true')
})
