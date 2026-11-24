import { test, expect, type Page } from '@playwright/test'
async function settings(page: Page) {
  await page.getByRole('button', { name: '打开主题设置' }).click()
  await expect(page.locator('#theme-settings-offcanvas')).toHaveClass(/\bshow\b/)
}
async function choose(page: Page, key: string, value: string) {
  if (key === 'user') { await page.getByTestId('theme-user').setChecked(value === 'show'); return }
  if (key === 'sidebar' && value.startsWith('gradient') && !(await page.locator('#collapseBgGradient').isVisible())) await page.getByRole('button', { name: '渐变色', exact: true }).click()
  await page.getByTestId(`theme-label-${key}-${value}`).click()
}
async function close(page: Page) {
  await page.getByRole('button', { name: '关闭主题设置' }).click()
  await expect(page.locator('.offcanvas-backdrop')).toHaveCount(0)
  await expect(page.locator('#theme-settings-offcanvas')).toBeHidden()
}

test('all four layouts have usable desktop and mobile navigation', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 })
    for (const layout of ['vertical', 'horizontal', 'twocolumn', 'semibox']) {
      await page.goto('/#/dashboard')
      await settings(page); await choose(page, 'layout', layout); await close(page)
      if (width < 768) await page.getByRole('button', { name: '切换导航菜单' }).click()
      if (layout === 'twocolumn' && width > 768) await page.getByRole('link', { name: '样品管理', exact: true }).first().click()
      else await page.locator('a.menu-link').filter({ hasText: '样品管理' }).click()
      await page.locator('.navbar-menu').getByRole('link', { name: '样品入库', exact: true }).click()
      await expect(page.getByRole('heading', { name: '样品入库', exact: true, level: 4 })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    }
  }
})

test('settings options, dependencies, persistence and reset leave sample data intact', async ({ page }) => {
  await page.goto('/#/dashboard')
  const readSamples = () => page.evaluate(async () => { const path = '/src/services/storage/database.ts'; return (await (await import(path)).repository.read()).samples })
  const sampleData = await readSamples()
  await settings(page)
  const attributeNames: Record<string, string> = { mode: 'data-bs-theme', colors: 'data-theme-colors', width: 'data-layout-width', position: 'data-layout-position', topbar: 'data-topbar', size: 'data-sidebar-size', view: 'data-layout-style', sidebar: 'data-sidebar', image: 'data-sidebar-image' }
  for (const [key, values] of Object.entries({ mode: ['dark', 'light'], colors: ['green', 'purple', 'blue', 'default'], width: ['boxed', 'fluid'], position: ['scrollable', 'fixed'], topbar: ['dark', 'light'], size: ['md', 'sm', 'sm-hover', 'lg'], view: ['detached', 'default'], sidebar: ['light', 'gradient', 'gradient-2', 'gradient-3', 'gradient-4', 'dark'], image: ['img-1', 'img-2', 'img-3', 'img-4', 'none'], user: ['show', 'hide'] })) {
    for (const value of values) {
      await choose(page, key, value)
      await expect(page.getByTestId(key === 'user' ? 'theme-user' : `theme-${key}-${value}`)).toBeChecked({ checked: key !== 'user' || value === 'show' })
      if (key === 'user') expect(await page.locator('html').evaluate(el => el.hasAttribute('data-sidebar-user-show'))).toBe(value === 'show')
      else await expect(page.locator('html')).toHaveAttribute(attributeNames[key]!, value)
    }
  }
  await choose(page, 'theme', 'galaxy')
  for (const image of ['img-1', 'img-2', 'img-3', 'none']) { await choose(page, 'body', image); await expect(page.locator('html')).toHaveAttribute('data-body-image', image) }
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark')
  await choose(page, 'theme', 'default'); await choose(page, 'layout', 'semibox'); await choose(page, 'visibility', 'hidden')
  await expect(page.locator('.navbar-menu')).toBeHidden()
  await choose(page, 'visibility', 'show'); await choose(page, 'preloader', 'enable')
  await expect(page.locator('#theme-settings-offcanvas')).not.toHaveClass(/\bshow\b/)
  await expect(page.locator('.offcanvas-backdrop')).toHaveCount(0)
  await page.reload()
  await expect(page.locator('#preloader')).toHaveCount(0)
  await expect(page.locator('html')).toHaveAttribute('data-layout', 'semibox')
  await settings(page); await page.getByRole('button', { name: '恢复默认主题' }).click(); await close(page)
  expect(await readSamples()).toEqual(sampleData)
  await settings(page); await choose(page, 'size', 'sm'); await close(page)
  await page.getByRole('button', { name: '切换导航菜单' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'lg')
  await page.getByRole('button', { name: '切换导航菜单' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'sm')
})

test('all template themes and their light and dark choices remain interactive', async ({ page }) => {
  await page.goto('/#/dashboard')
  await settings(page)
  for (const theme of ['default', 'saas', 'corporate', 'galaxy', 'material', 'creative', 'minimal', 'modern', 'interactive', 'classic', 'vintage']) {
    await choose(page, 'theme', theme)
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    for (const mode of ['light', 'dark']) {
      await expect(page.getByTestId(`theme-mode-${mode}`)).toBeEnabled()
      await choose(page, 'mode', mode)
      await expect(page.locator('html')).toHaveAttribute('data-bs-theme', mode)
      const palette = await page.evaluate(() => {
        const style = getComputedStyle(document.documentElement)
        return [style.getPropertyValue('--vz-body-bg').trim(), style.getPropertyValue('--vz-body-color').trim(), style.getPropertyValue('--vz-primary').trim()]
      })
      expect(palette.every(Boolean)).toBe(true)
      expect(palette[0]).not.toBe(palette[1])
    }
    await expect(page.locator('#body-img')).toBeVisible({ visible: theme === 'galaxy' })
  }
})

test('Galaxy uses initial dark defaults but permits explicit changes and restores saved preferences', async ({ page }) => {
  await page.goto('/#/dashboard')
  await settings(page)
  await choose(page, 'sidebar', 'light')
  await choose(page, 'theme', 'galaxy')
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'dark')
  await choose(page, 'theme', 'default')
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'light')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'light')
  await choose(page, 'theme', 'galaxy')
  await choose(page, 'mode', 'light')
  await choose(page, 'sidebar', 'gradient-2')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'gradient-2')
  await close(page)
  await page.getByRole('button', { name: '切换明暗模式', exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'gradient-2')
  await settings(page)
  await choose(page, 'theme', 'default')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'gradient-2')
})

test('layout transitions preserve hidden preferences and apply width and sidebar dependencies', async ({ page }) => {
  await page.goto('/#/dashboard')
  await settings(page)
  await choose(page, 'view', 'detached')
  await choose(page, 'image', 'img-2')
  await choose(page, 'layout', 'horizontal')
  await expect(page.locator('#sidebar-view')).toBeHidden()
  await expect(page.locator('#sidebar-img')).toBeHidden()
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-image', 'none')
  await choose(page, 'layout', 'vertical')
  await expect(page.getByTestId('theme-view-detached')).toBeChecked()
  for (const layout of ['twocolumn', 'semibox']) {
    await choose(page, 'width', 'boxed')
    await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'sm-hover')
    await choose(page, 'layout', layout)
    await expect(page.locator('html')).toHaveAttribute('data-layout-width', 'fluid')
    await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'lg')
    await expect(page.locator('#layout-width')).toBeHidden()
    await expect(page.locator('#sidebar-view')).toBeHidden()
    await expect(page.locator('#layout-position')).toBeVisible({ visible: layout !== 'twocolumn' })
    await choose(page, 'layout', 'vertical')
    await expect(page.getByTestId(layout === 'twocolumn' ? 'theme-view-detached' : 'theme-view-default')).toBeChecked()
  }
  await choose(page, 'sidebar', 'gradient-3')
  await choose(page, 'image', 'img-3')
  await choose(page, 'size', 'md')
  await choose(page, 'layout', 'semibox')
  await choose(page, 'visibility', 'hidden')
  for (const id of ['sidebar-size', 'sidebar-color', 'sidebar-img']) await expect(page.locator(`#${id}`)).toBeHidden()
  for (const attr of ['data-sidebar', 'data-sidebar-image', 'data-sidebar-size']) expect(await page.locator('html').getAttribute(attr)).toBeNull()
  await choose(page, 'visibility', 'show')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar', 'gradient-3')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-image', 'img-3')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'md')
  await close(page)
  await page.getByRole('button', { name: '切换导航菜单', exact: true }).click()
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'sm')
  await settings(page)
  await choose(page, 'topbar', 'dark')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'sm')
})

test('tablet and mobile layout changes restore desktop preferences', async ({ page }) => {
  await page.goto('/#/dashboard')
  await settings(page); await choose(page, 'size', 'md'); await close(page)
  await page.setViewportSize({ width: 900, height: 900 })
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'sm')
  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'md')
  await settings(page); await choose(page, 'layout', 'twocolumn'); await close(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('html')).toHaveAttribute('data-layout', 'vertical')
  await expect(page.locator('html')).toHaveAttribute('data-sidebar-size', 'lg')
  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.locator('html')).toHaveAttribute('data-layout', 'twocolumn')
})

test('visual review captures representative themes and viewports', async ({ page }, testInfo) => {
  const failures: string[] = []
  page.on('pageerror', error => failures.push(error.message))
  page.on('response', response => { if (response.url().includes('/template/') && response.status() >= 400) failures.push(response.url()) })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/#/dashboard')
  await page.screenshot({ path: testInfo.outputPath('dashboard-default.png'), fullPage: true })
  await settings(page)
  await page.screenshot({ path: testInfo.outputPath('theme-previews-desktop.png'), fullPage: true })
  await close(page)
  await settings(page); await choose(page, 'layout', 'twocolumn'); await choose(page, 'mode', 'dark'); await close(page)
  await page.screenshot({ path: testInfo.outputPath('dashboard-twocolumn-dark.png'), fullPage: true })
  await settings(page); await choose(page, 'theme', 'galaxy'); await choose(page, 'body', 'img-2'); await choose(page, 'layout', 'semibox'); await close(page)
  await page.screenshot({ path: testInfo.outputPath('dashboard-galaxy-semibox.png'), fullPage: true })
  await settings(page); await page.getByRole('button', { name: '恢复默认主题' }).click(); await close(page)
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto('/#/samples/inbound')
  await page.screenshot({ path: testInfo.outputPath('samples-mobile.png'), fullPage: true })
  await settings(page)
  await page.screenshot({ path: testInfo.outputPath('theme-previews-mobile.png'), fullPage: true })
  await close(page)
  expect(failures).toEqual([])
})
