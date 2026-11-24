import { expect, test } from '@playwright/test'

for (const preloader of ['enable', 'disable']) test(`refresh uses one consistent startup presentation with preloader ${preloader}`, async ({ page }) => {
  await page.addInitScript(setting => {
    localStorage.setItem('lims.theme.v1', JSON.stringify({ version: 1, settings: { preloader: setting } }))
    const checks = { duplicateAnimation: false, loadingText: false }
    Object.assign(window, { startupChecks: checks })
    new MutationObserver(() => {
      if (document.querySelectorAll('#preloader').length > 1) checks.duplicateAnimation = true
      if ([...document.querySelectorAll('[role="status"]')].some(node => node.textContent?.trim() === '正在加载工作空间…' && node.getClientRects().length > 0)) checks.loadingText = true
    }).observe(document, { childList: true, subtree: true, attributes: true })
    document.addEventListener('DOMContentLoaded', () => {
      const image = document.createElement('img')
      image.hidden = true; image.src = '/startup-test.png'; document.body.append(image)
    })
  }, preloader)
  let releaseMain = () => {}, releaseView = () => {}, releaseImage = () => {}, imageStarted = () => {}
  const mainGate = new Promise<void>(resolve => { releaseMain = resolve })
  const viewGate = new Promise<void>(resolve => { releaseView = resolve })
  const imageGate = new Promise<void>(resolve => { releaseImage = resolve })
  const imageRequested = new Promise<void>(resolve => { imageStarted = resolve })
  await page.route('**/startup-test.png', async route => { imageStarted(); await imageGate; await route.fulfill({ status: 204, body: '' }) })
  await page.route('**/src/main.ts', async route => { await mainGate; await route.continue() })
  await page.route('**/src/views/samples/SampleInboundView.vue', async route => { await viewGate; await route.continue() })
  await page.goto('/#/samples/inbound', { waitUntil: 'commit' })
  await expect(page.locator('#boot-pending')).toHaveJSProperty('hidden', false)
  if (preloader === 'enable') {
    await expect(page.locator('#preloader')).toBeVisible()
  } else {
    await expect(page.locator('#preloader')).toBeHidden()
  }
  releaseMain()
  await imageRequested
  await expect(page.locator('#boot-pending')).toHaveCount(0)
  if (preloader === 'enable') {
    await expect(page.locator('#preloader')).toBeVisible()
    await expect(page.getByText('正在加载工作空间…', { exact: true })).toHaveCount(0)
  } else {
    await expect(page.locator('#preloader')).toHaveCount(0)
    await expect(page.getByText('正在加载工作空间…', { exact: true })).toHaveCount(0)
  }
  releaseImage()
  await page.waitForLoadState('load')
  await expect(page.locator('#preloader')).toHaveCount(0)
  await expect(page.locator('#layout-wrapper')).toHaveCount(0)
  releaseView()
  await expect(page.getByRole('heading', { name: '样品入库', level: 4, exact: true })).toBeVisible()
  await expect(page.locator('#preloader')).toHaveCount(0)
  expect(await page.evaluate(() => (window as unknown as { startupChecks: object }).startupChecks)).toEqual({ duplicateAnimation: false, loadingText: false })
})

test('enabled startup animation yields to static script failure feedback', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('lims.theme.v1', JSON.stringify({ version: 1, settings: { preloader: 'enable' } })))
  await page.route('**/src/main.ts', route => route.abort())
  await page.goto('/#/samples/inbound')
  await expect(page.getByRole('heading', { name: '应用资源加载失败', exact: true })).toBeVisible()
  await expect(page.locator('#preloader')).toBeHidden()
  await expect(page.getByRole('button', { name: '重新加载', exact: true })).toBeVisible()
})

test('enabling a preview during slow resource loading does not create a second startup animation', async ({ page }) => {
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const image = document.createElement('img')
      image.hidden = true; image.src = '/startup-test.png'; document.body.append(image)
    })
  })
  let release = () => {}
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/startup-test.png', async route => { await gate; await route.fulfill({ status: 204, body: '' }) })
  await page.goto('/#/dashboard', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: '打开主题设置', exact: true }).click()
  await page.getByTestId('theme-label-preloader-enable').click()
  await expect(page.locator('#preloader')).toHaveCount(1)
  await expect(page.locator('#preloader')).toBeVisible()
  await expect(page.locator('#theme-settings-offcanvas')).not.toHaveClass(/\bshow\b/)
  await expect(page.locator('#preloader')).toHaveCount(0)
  expect(await page.evaluate(() => document.readyState)).not.toBe('complete')
  release()
  await page.waitForLoadState('load')
  await expect(page.locator('#preloader')).toHaveCount(0)
})
