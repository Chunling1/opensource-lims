// 页面验收（P-10/P-11）：真实浏览器点击，核对页面反馈。
// 用法：node p10.ui.mjs <url> <截图目录>；页面按 2026-11-18 15:47 版（列表 → 样品工作表 → 报告工作表）编写。（2026-11-18 晚：Tabler 重写后登录先落我的待办，退出在用户菜单内）
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { mkdirSync } from 'node:fs'
const require = createRequire(import.meta.url)
const { chromium } = require('playwright')

const [url = 'http://127.0.0.1:8899/', shots = fileURLToPath(new URL('./artifacts/p10', import.meta.url))] = process.argv.slice(2)
mkdirSync(shots, { recursive: true })
const PDF = Buffer.from('%PDF-1.4\n% acceptance\n%%EOF\n')
const today = new Date().toLocaleDateString('sv-SE')
const results = []
async function step(name, fn) {
  try { await fn(); results.push(['通过', name]) } catch (e) { results.push(['失败', name + '：' + String(e.message).split('\n')[0]]) }
}
function expect(cond, msg) { if (!cond) throw new Error(msg) }

const browser = await chromium.launch({ channel: 'msedge' })
async function session(account) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 } })
  const page = await ctx.newPage()
  page.setDefaultTimeout(6000)
  await page.goto(url)
  if (account) { await login(page, account); if (account !== 'zi') await toPool(page) }
  return page
}
async function login(page, account, pwd = 'LimsDemo2026') {
  await page.getByLabel('账号').fill(account)
  await page.getByLabel('密码').fill(pwd)
  await page.getByRole('button', { name: '登录' }).click()
}
async function toPool(p) {
  await p.getByRole('heading', { name: '我的待办' }).waitFor()
  await p.getByRole('link', { name: /检测样品/ }).click()
}
const alert = (p) => p.getByRole('alert').first()
const ok = (p) => p.getByRole('status')
async function open(p, name) {
  await p.getByRole('row', { name: new RegExp(name) }).getByRole('link', { name: '打开工作表' }).click()
  await p.getByRole('heading', { name: '样品工作表' }).waitFor()
}
const hint = (btn) => btn.locator('xpath=following-sibling::small').innerText()

let lin, zhou
await step('错误密码有提示，不进入工作台', async () => {
  lin = await session()
  await login(lin, 'lin', 'bad')
  await alert(lin).waitFor()
  expect(await lin.getByText('检测样品').count() === 0, '错误密码却进入了工作台')
})
await step('林澄登录后看到待领取池，有溪流水样', async () => {
  await login(lin, 'lin')
  await toPool(lin)
  await lin.getByRole('heading', { name: '检测样品' }).waitFor()
  await lin.getByRole('cell', { name: '溪流水样' }).waitFor()
  await lin.screenshot({ path: shots + '/01-pool.png' })
})
await step('两人同时打开同一样品：林澄领取成功，周禾再领看到提示', async () => {
  zhou = await session('zhou')
  await open(zhou, '溪流水样')
  await open(lin, '溪流水样')
  await lin.getByRole('button', { name: '领取样品' }).click()
  await ok(lin).waitFor()
  await zhou.getByRole('button', { name: '领取样品' }).click()
  await alert(zhou).waitFor()
  results.push(['记录', '周禾看到：' + (await alert(zhou).innerText())])
  await zhou.screenshot({ path: shots + '/02-claim-conflict.png' })
})
await step('领取后样品工作表负责人显示林澄', async () => {
  await lin.locator('.datagrid-item', { hasText: '负责人' }).getByText('林澄').waitFor()
})
await step('授权失效的陆川：待领取池为空（附表G：只列本人授权覆盖的）', async () => {
  const lu = await session('lu')
  await lu.getByText('没有符合条件的样品。').waitFor()
  await lu.context().close()
})
await step('陆川直接打开样品链接：领取按钮不可点并写明原因', async () => {
  const lu = await session('lu')
  await lu.getByRole('heading', { name: '检测样品' }).waitFor()
  await lu.goto(url + '#/samples/2')
  await lu.getByRole('heading', { name: '样品工作表' }).waitFor()
  const btn = lu.getByRole('button', { name: '领取样品' })
  expect(await btn.isDisabled(), '领取按钮仍可点击')
  const why = await hint(btn)
  expect(why.includes('授权'), '没有写原因：' + why)
  results.push(['记录', '陆川看到：' + why])
  await lu.screenshot({ path: shots + '/03-lu-disabled.png' })
  await lu.context().close()
})
await step('创建报告后进入报告工作表，显示 BG 编号', async () => {
  await lin.getByRole('button', { name: '创建报告' }).click()
  await lin.getByRole('heading', { name: '检测报告工作表' }).waitFor()
  await lin.getByText(/BG-\d{5}/).first().waitFor()
})
async function upload(kind, name, buffer) {
  await lin.getByLabel('资料类型').selectOption({ label: kind })
  await lin.getByLabel('PDF 文件').setInputFiles({ name, mimeType: 'application/pdf', buffer })
  await lin.getByRole('button', { name: '保存 PDF' }).click()
}
await step('改名的非 PDF 文件被拒并提示', async () => {
  const ed = lin.locator('details', { hasText: '编制操作' })
  if ((await ed.count()) && (await ed.getAttribute('open')) === null) await ed.locator('summary').click()
  await upload('原始记录', 'fake.pdf', Buffer.from('not pdf'))
  await alert(lin).waitFor()
  results.push(['记录', '非 PDF 提示：' + (await alert(lin).innerText())])
})
await step('上传原始记录和待签报告，文件可下载链接', async () => {
  await upload('原始记录', 'source.pdf', PDF)
  await lin.getByRole('link', { name: 'source.pdf' }).waitFor()
  await upload('待签报告', 'draft.pdf', PDF)
  await lin.getByRole('link', { name: 'draft.pdf' }).waitFor()
})
await step('审核人列表不含本人，选择沈宁后提交审核', async () => {
  const names = await lin.getByLabel('下一办理人').locator('option').allInnerTexts()
  expect(!names.some((n) => n.includes('林澄')), '审核人列表含本人')
  await lin.getByLabel('检测开始日期').fill(today)
  await lin.getByLabel('检测结束日期').fill(today)
  await lin.getByLabel('下一办理人').selectOption({ label: '沈宁' })
  await lin.getByRole('button', { name: '提交审核' }).click()
  await ok(lin).waitFor()
  await lin.screenshot({ path: shots + '/04-submitted.png', fullPage: true })
})
await step('提交后不再显示上传（送审包冻结）', async () => {
  expect(await lin.getByRole('button', { name: '保存 PDF' }).count() === 0, '提交后仍显示上传')
})
await step('回到样品工作表：已上传资料，“退回待领取池”不可点（D-72）', async () => {
  await lin.goto(url + '#/samples/1')
  const btn = lin.getByRole('button', { name: '退回待领取池' })
  if (await btn.count()) {
    expect(await btn.isDisabled(), '上传后仍可退回')
    results.push(['记录', '退回提示：' + (await hint(btn))])
  }
})
await step('资料管理员顾桐落在我的待办，看不到检测样品', async () => {
  const zi = await session('zi')
  await zi.getByRole('heading', { name: '我的待办' }).waitFor()
  expect(await zi.getByRole('heading', { name: '检测样品' }).count() === 0, '资料管理员看到了检测样品')
  expect(await zi.getByRole('link', { name: '检测样品' }).count() === 0, '资料管理员看到了检测样品导航')
  await zi.context().close()
})
await step('退出后回到登录页', async () => {
  await lin.getByRole('button', { name: '用户菜单' }).click()
  await lin.getByRole('button', { name: '退出' }).click()
  await lin.getByLabel('账号').waitFor()
})
await browser.close()
for (const [s, n] of results) console.log(`[${s}] ${n}`)
const failed = results.filter((r) => r[0] === '失败').length
console.log(`页面验收：${results.filter((r) => r[0] === '通过').length} 通过，${failed} 失败`)
process.exit(failed ? 1 : 0)
