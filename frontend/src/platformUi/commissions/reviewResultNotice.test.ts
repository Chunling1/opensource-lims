import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'
import { describe, expect, it, vi } from 'vitest'

// Execute the owning page function, with no production API or business writes.
const source = parse(readFileSync('src/modules/pages/ContractReviewPage.vue', 'utf8')).descriptor.scriptSetup!.content
const ast = ts.createSourceFile('review.ts', source, ts.ScriptTarget.Latest, true)
const declaration = ast.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === 'performSubmit')!
const loadStart = source.indexOf('let reviewLoad:')
const loadEnd = source.indexOf('const reviewLinkedParents=', loadStart)
const js = ts.transpileModule(source.slice(loadStart, loadEnd) + '\n' + declaration.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
function setup(result: unknown) {
  const ctx = {
    selectedReport: { value: { reportNo: 'R-1', status: '待合同评审' } },
    beginReviewLoad: () => () => true, commissionPage:{query:{},total:0},registrationSamplePage:{query:{},total:0},fetchListPage:vi.fn(async()=>({rows:[],total:0})),
    reviewListBusy: { value: false }, reviewListError: { value: '' }, reviewParents: { value: [] },
    reviewEpoch: 1, isCurrentReview: vi.fn(() => true),
    form: { items: {}, cma: false, cnas: false, opinion: '请更正' },
    submitContractReview: vi.fn(async () => result), ElMessage: { success: vi.fn(), error: vi.fn() },
    formOpen: { value: true }, allRows: { value: [] }, fetchReportRows: vi.fn(async () => []),
    reportWorkRows: [], session: { dataScope: {}, userName: 'tester' },
  }
  const run = new Function(...Object.keys(ctx), js + '; return performSubmit')(...Object.values(ctx))
  return { ctx, run }
}
describe('contract review success uses the persisted destination', () => {
  it.each([
    ['待样品入库', '样品入库中'],
    ['待样品领取', '样品出库领取中'],
    ['检测录入中', '检测数据录入中'],
    ['检测更改中', '检测更改中'],
    ['待审核', '报告审核中'],
  ])('shows %s returned by the server, including project step skips', async (status, dataStatus) => {
    const { ctx, run } = setup({ status, dataStatus })
    expect(await run('pass')).toBe(true)
    expect(ctx.ElMessage.success).toHaveBeenCalledExactlyOnceWith(`R-1 合同评审通过，已进入「${dataStatus}」`)
    expect(ctx.formOpen.value).toBe(false)
    expect(ctx.fetchListPage).toHaveBeenCalledWith('/api/reports/query',expect.objectContaining({view:'contract_review'}))
  })
  it('uses returned status if the display label is absent', async () => {
    const { ctx, run } = setup({ status: '待样品领取' }); await run('pass')
    expect(ctx.ElMessage.success).toHaveBeenCalledWith('R-1 合同评审通过，已进入「待样品领取」')
  })
  it('does not invent an inbound destination when the response has no state', async () => {
    const { ctx, run } = setup(undefined); await run('pass')
    expect(ctx.ElMessage.success).toHaveBeenCalledWith('R-1 合同评审通过')
  })
  it('retains the separate return confirmation', async () => {
    const { ctx, run } = setup({ status: '委托更改中' }); await run('return')
    expect(ctx.ElMessage.success).toHaveBeenCalledWith('R-1 已退回')
  })
  it('shows rejection without success or closing the form', async () => {
    const { ctx, run } = setup(null)
    ctx.submitContractReview.mockRejectedValueOnce(new Error('当前状态不可评审'))
    expect(await run('pass')).toBe(false)
    expect(ctx.ElMessage.error).toHaveBeenCalledWith('当前状态不可评审')
    expect(ctx.ElMessage.success).not.toHaveBeenCalled(); expect(ctx.formOpen.value).toBe(true)
  })
  it('ignores a response after the user has switched report', async () => {
    const { ctx, run } = setup({ status: '待样品领取', dataStatus: '样品出库领取中' })
    ctx.isCurrentReview.mockReturnValueOnce(true).mockReturnValue(false)
    expect(await run('pass')).toBe(false)
    expect(ctx.ElMessage.success).not.toHaveBeenCalled(); expect(ctx.fetchListPage).not.toHaveBeenCalled()
  })
})
