import { expect, test } from '@playwright/test'

test('shared selection handles mixed eligible rows, half selection and an entirely disabled page', async ({ page }) => {
  let allVoided = false
  await page.route('**/api/registration/samples/query', async route => {
    const response = await route.fetch(), data = await response.json()
    data.items.forEach((row: { status: string }, index: number) => { row.status = allVoided || index === 0 ? 'voided' : 'pending' })
    await route.fulfill({ response, json: data })
  })
  await page.goto('/#/commissions/registration?scope=all&sSort=code&sDirection=asc')
  const samples = page.getByRole('table', { name: '样品列表', exact: true })
  await expect(samples.locator('tbody tr')).toHaveCount(10)
  const rows = samples.locator('tbody tr'), all = samples.getByRole('checkbox', { name: '全选当前页样品' })
  await expect(rows.first().getByRole('checkbox')).toBeDisabled()
  await rows.nth(1).getByRole('checkbox').check()
  await expect(all).toHaveJSProperty('indeterminate', true)
  await all.check()
  await expect(all).toBeChecked()
  await expect(all).toHaveJSProperty('indeterminate', false)
  await expect(samples.locator('tbody input:checked')).toHaveCount(9)
  await all.uncheck()
  await expect(samples.locator('tbody input:checked')).toHaveCount(0)

  allVoided = true
  await page.getByRole('navigation', { name: '样品分页' }).getByRole('button', { name: '下一页', exact: true }).click()
  await expect(rows.first()).toContainText('SP2026090011')
  await expect(all).toBeDisabled()
  await expect(all).not.toBeChecked()
  await expect(all).toHaveJSProperty('indeterminate', false)
  await expect(samples.locator('tbody input:disabled')).toHaveCount(10)
  await rows.first().getByRole('button', { name: /更多操作/ }).click()
  await expect(page.getByRole('menu').getByRole('menuitem')).toHaveText(['查看', '附件管理'])
})


test('row menus highlight only hovered items on pointer opening and retain keyboard navigation', async ({ page }) => {
  for (const workspace of ['registration', 'review']) {
    await page.goto(`/#/commissions/${workspace}?scope=all&cSort=code&cDirection=asc&sSort=code&sDirection=asc`)
    for (const tableName of ['委托列表', '样品列表']) {
      const table = page.getByRole('table', { name: tableName, exact: true })
      const trigger = table.getByRole('button', { name: /更多操作/ }).first()
      await trigger.click()
      const menu = page.getByRole('menu')
      const view = menu.getByRole('menuitem', { name: '查看', exact: true })
      await expect(view).not.toBeFocused()
      const background = () => view.evaluate(el => getComputedStyle(el).backgroundColor)
      const normal = await background()
      await view.hover()
      await expect.poll(background).not.toBe(normal)
      await trigger.hover()
      await expect.poll(background).toBe(normal)
      await trigger.press('ArrowDown')
      await expect(view).toBeFocused()
      await view.press('End')
      await expect(menu.locator('[role="menuitem"]:not(:disabled)').last()).toBeFocused()
      await page.keyboard.press('Home')
      await expect(view).toBeFocused()
      await view.press('Escape')
      await expect(menu).toHaveCount(0)
      await expect(trigger).toBeFocused()
      await trigger.press('Enter')
      await expect(view).toBeFocused()
      await view.press('Escape')
    }
  }
})
