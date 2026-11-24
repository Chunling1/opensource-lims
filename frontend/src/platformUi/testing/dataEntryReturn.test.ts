import { describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { createDataEntryReturn, type ReturnContext } from './dataEntryReturn'

function setup() {
  const context: ReturnContext = { account: 'tester', scope: 'D1', path: '/data_entry',
    formOpen: false, formReportNo: '', formReadOnly: false }
  let confirm!: (value: string | null) => void
  const deps = {
    busy: ref(false), saving: vi.fn(() => false), context: () => context,
    allowed: vi.fn(() => true),
    prompt: vi.fn(() => new Promise<string | null>(resolve => { confirm = resolve })),
    submit: vi.fn(async (_report: string, _note: string) => {}),
    completed: vi.fn(async (_report: string, _fromForm: boolean) => {}),
    warning: vi.fn(), error: vi.fn(),
  }
  return { context, deps, run: createDataEntryReturn(deps), confirm: (value: string | null) => confirm(value) }
}

describe('data-entry return workflow', () => {
  it('returns the clicked report without requiring table selection and refreshes on success', async () => {
    const t = setup(), pending = t.run('R2')
    t.confirm('  样品信息有误  '); await pending
    expect(t.deps.submit).toHaveBeenCalledExactlyOnceWith('R2', '样品信息有误')
    expect(t.deps.completed).toHaveBeenCalledWith('R2', false)
    expect(t.deps.busy.value).toBe(false)
  })
  it.each([null, '   '])('does not submit cancelled or empty reasons: %s', async note => {
    const t = setup(), pending = t.run('R1')
    t.confirm(note); await pending
    expect(t.deps.submit).not.toHaveBeenCalled()
    expect(t.deps.busy.value).toBe(false)
    if (note !== null) expect(t.deps.warning).toHaveBeenCalled()
  })
  it.each(['account', 'scope', 'path'] as const)('stops with a notice when %s changes during confirmation', async key => {
    const t = setup(), pending = t.run('R1')
    t.context[key] = 'changed'; t.confirm('原因'); await pending
    expect(t.deps.submit).not.toHaveBeenCalled()
    expect(t.deps.warning).toHaveBeenCalledWith(expect.stringContaining('未提交'))
  })
  it('rechecks status and permissions after confirmation', async () => {
    const t = setup(), pending = t.run('R1')
    t.deps.allowed.mockReturnValue(false); t.confirm('原因'); await pending
    expect(t.deps.submit).not.toHaveBeenCalled()
    expect(t.deps.warning).toHaveBeenCalled()
  })
  it('does not open a prompt for an unauthorized report', async () => {
    const t = setup(); t.deps.allowed.mockReturnValue(false); await t.run('R1')
    expect(t.deps.prompt).not.toHaveBeenCalled(); expect(t.deps.warning).toHaveBeenCalled()
  })
  it('does not submit while a data save is in progress', async () => {
    const t = setup(), pending = t.run('R1')
    t.deps.saving.mockReturnValue(true); t.confirm('原因'); await pending
    expect(t.deps.submit).not.toHaveBeenCalled(); expect(t.deps.warning).toHaveBeenCalled()
  })
  it('prevents duplicate returns while a prompt or request is pending', async () => {
    const t = setup(), pending = t.run('R1')
    await t.run('R2'); expect(t.deps.prompt).toHaveBeenCalledTimes(1)
    let finish!: () => void
    t.deps.submit.mockImplementation(() => new Promise<void>(resolve => { finish = resolve }))
    t.confirm('原因'); await Promise.resolve()
    await t.run('R1'); expect(t.deps.submit).toHaveBeenCalledTimes(1)
    finish(); await pending; expect(t.deps.busy.value).toBe(false)
  })
  it('displays backend errors without clearing the report and allows retry', async () => {
    const t = setup(); t.deps.submit.mockRejectedValueOnce(new Error('仅当前处理人可以退回'))
    const pending = t.run('R1'); t.confirm('原因'); await pending
    expect(t.deps.error).toHaveBeenCalledWith('仅当前处理人可以退回')
    expect(t.deps.completed).not.toHaveBeenCalled(); expect(t.deps.busy.value).toBe(false)
    const retry = t.run('R1'); t.confirm('原因'); await retry
    expect(t.deps.completed).toHaveBeenCalledOnce()
  })
  it('does not clear a different form when the original request finishes', async () => {
    const t = setup(); Object.assign(t.context, { formOpen: true, formReportNo: 'R1' })
    let finish!: () => void
    t.deps.submit.mockImplementation(() => new Promise<void>(resolve => { finish = resolve }))
    const pending = t.run('R1'); t.confirm('原因'); await Promise.resolve()
    t.context.formReportNo = 'R2'; finish(); await pending
    expect(t.deps.completed).not.toHaveBeenCalled()
  })
  it('keeps form-context protection before sending', async () => {
    const t = setup(); Object.assign(t.context, { formOpen: true, formReportNo: 'R1' })
    const pending = t.run('R1'); t.context.formReadOnly = true; t.confirm('原因'); await pending
    expect(t.deps.submit).not.toHaveBeenCalled(); expect(t.deps.warning).toHaveBeenCalled()
  })
})
