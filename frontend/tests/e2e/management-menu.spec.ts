import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'
import { modules } from '../../src/services/business/modules'

type MenuNode = { label: string; children?: MenuNode[] }
function expectedMenu(title: string): MenuNode[] {
  const lines = readFileSync('docs/菜单.txt', 'utf8').split(/\r?\n/)
  const nodes: MenuNode[] = [], stack: { indent: number; node: MenuNode }[] = []
  for (const line of lines.slice(lines.indexOf(title) + 1)) {
    if (line && !line.includes('- ')) break
    const match = /^( *)- (.+)$/.exec(line)
    if (!match) continue
    const indent = match[1]!.length, node: MenuNode = { label: match[2]! }
    while (stack.length && stack.at(-1)!.indent >= indent) stack.pop()
    if (stack.length) (stack.at(-1)!.node.children ??= []).push(node)
    else nodes.push(node)
    stack.push({ indent, node })
  }
  return nodes
}

for (const [id, title, entry] of [
  ['customers', '客户管理', '/customers/accounts'],
  ['finance', '财务管理', '/finance/pricing'],
  ['quality', '质量体系', '/quality/personnel/registration'],
  ['system', '系统管理', '/system/maintenance/initialization'],
  ['analytics', '查询统计', '/analytics/batches/comparison'],
]) {
  test(`${title} matches 菜单.txt and every page has only a heading and breadcrumbs`, async ({ page }) => {
    test.setTimeout(60000)
    await page.goto(`/#${entry}`)
    const menu = page.locator(`#menu-${id}`)
    await expect(menu).toBeAttached()
    const actual = await menu.evaluate(root => {
      function read(parent: Element): MenuNode[] {
        return Array.from(parent.querySelectorAll(':scope > ul > li')).map(li => {
          const node: MenuNode = { label: li.querySelector(':scope > a')!.textContent!.trim() }
          const children = li.querySelector(':scope > .menu-dropdown')
          if (children) node.children = read(children)
          return node
        })
      }
      return read(root)
    })
    expect(actual).toEqual(expectedMenu(title!))
    const leaves = await menu.locator('a:not([data-bs-toggle])').evaluateAll(links => links.map(link => {
      const labels = [link.textContent!.trim()]
      let branch = link.parentElement!.parentElement!.parentElement!
      while (branch.id.startsWith('submenu-')) {
        labels.unshift(branch.parentElement!.querySelector(':scope > a')!.textContent!.trim())
        branch = branch.parentElement!.parentElement!.parentElement!
      }
      return { href: link.getAttribute('href')!, labels }
    }))
    for (const leaf of leaves) {
      await page.goto(`/${leaf.href}`)
      await expect(page.getByRole('heading', { name: leaf.labels.at(-1), exact: true, level: 4 })).toBeVisible()
      await expect(page.getByRole('navigation', { name: '面包屑', exact: true }).locator('li')).toHaveText([title!, ...leaf.labels])
      await expect(page.locator('main .page-content table, main .page-content form, main .page-content input, main .page-content .card')).toHaveCount(0)
      await expect(page.locator(`#menu-${id} a.active:not([data-bs-toggle])`)).toHaveText(leaf.labels.at(-1)!)
    }
    await page.reload()
    await expect(page.getByRole('heading', { name: leaves.at(-1)!.labels.at(-1), exact: true, level: 4 })).toBeVisible()
  })
}

test('retired management URLs are removed and show 404 without redirects', async ({ page }) => {
  test.setTimeout(60000)
  const oldModules = modules.filter(module => ['finance', 'quality', 'system'].includes(module.group) || ['customers', 'contracts'].includes(module.id))
  for (const path of [...oldModules.flatMap(module => [`/workspace/${module.id}`, `/workspace/${module.id}/old-record`]), '/statistics', '/maintenance', '/audit', '/authorization', '/components']) {
    await page.goto(`/#${path}`)
    await expect(page.getByRole('heading', { name: '页面不存在', exact: true })).toBeVisible()
    expect(new URL(page.url()).hash).toBe(`#${path}`)
  }
  await page.goto('/#/identity')
  await expect(page.getByRole('heading', { name: '演示身份', exact: true, level: 4 })).toBeVisible()
})

test('four-level menus work in all layouts on desktop and mobile', async ({ page }) => {
  test.setTimeout(60000)
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 })
    for (const layout of ['vertical', 'horizontal', 'twocolumn', 'semibox']) {
      await page.goto('/#/dashboard')
      await page.getByRole('button', { name: '打开主题设置' }).click()
      await page.getByTestId(`theme-label-layout-${layout}`).click()
      await page.getByRole('button', { name: '关闭主题设置' }).click()
      await expect(page.locator('.offcanvas-backdrop')).toHaveCount(0)
      if (width < 768) await page.getByRole('button', { name: '切换导航菜单' }).click()
      if (layout === 'twocolumn' && width > 768) await page.getByRole('link', { name: '系统管理', exact: true }).first().click()
      else if (layout === 'horizontal' && width > 1024) {
        await page.locator('a[href="#menu-more"]').click()
        await page.locator('a[href="#menu-system"]').click()
      } else await page.locator('a.menu-link').filter({ hasText: '系统管理' }).click()
      await page.locator('#menu-system').getByRole('button', { name: '检测项目', exact: true }).click()
      await page.locator('#submenu-system-projects').getByRole('button', { name: '检测项目分类设置', exact: true }).click()
      await page.locator('#submenu-system-projects-classification').getByRole('link', { name: '组号分配', exact: true }).click()
      await expect(page.getByRole('heading', { name: '组号分配', exact: true, level: 4 })).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
    }
  }
})

test('nested menus filter permissions and direct URLs use the same access check', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('lims.identity.v1', 'equipment'))
  await page.goto('/#/quality/equipment/ledger')
  await expect(page.getByRole('heading', { name: '设备台账', exact: true, level: 4 })).toBeVisible()
  await expect(page.locator('#menu-quality a').filter({ hasText: '人员登记' })).toHaveCount(0)
  await expect(page.locator('#menu-quality a').filter({ hasText: '标准物质登记' })).toHaveCount(0)
  await expect(page.locator('a[href="#menu-system"]')).toHaveCount(0)
  await page.goto('/#/system/users')
  await expect(page).toHaveURL(/#\/forbidden$/)
})
