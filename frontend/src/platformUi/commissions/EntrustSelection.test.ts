import { afterEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import Picker from './EntrustSelection'

// Bootstrap completes transition timers after a modal unmounts.
afterEach(async () => { await new Promise(resolve => setTimeout(resolve, 400)) })

const options = Array.from({ length: 12 }, (_, i) => ({ entrustNo: `WT-${i}`, client: `客户${i}`, projectName: `工程${i}`, sampleCount: i }))
const make = (disabled = false) => mount(Picker, { props: { modelValue: 'WT-0', options, disabled }, global: { stubs: { teleport: true } } })
describe('Existing entrust selection presentation', () => {
  it('searches all available options and emits the original selection events only after confirmation', async () => {
    const w = make()
    await w.get('button').trigger('click')
    await w.get('input[placeholder="搜索委托编号、委托单位或工程名称"]').setValue('工程11')
    expect(w.findAll('tbody tr')).toHaveLength(1)
    await w.get('input[type="radio"]').setValue(true)
    expect(w.emitted('change')).toBeUndefined()
    await w.findAll('button').find(b => b.text() === '确认选择')!.trigger('click')
    expect(w.emitted('update:modelValue')).toEqual([['WT-11']])
    expect(w.emitted('change')).toEqual([['WT-11']])
    w.unmount()
  })
  it('cancels a pending selection without modifying the saved association', async () => {
    const w = make()
    await w.get('button').trigger('click')
    await w.findAll('input[type="radio"]')[1].setValue(true)
    await w.findAll('button').find(b => b.text() === '取消')!.trigger('click')
    expect(w.emitted('change')).toBeUndefined()
    expect((w.get('input[aria-label="已关联委托单"]').element as HTMLInputElement).value).toContain('WT-0')
    w.unmount()
  })
  it('keeps an existing report association locked', async () => {
    const w = make(true)
    expect(w.get('button').attributes('disabled')).toBeDefined()
    await w.get('button').trigger('click')
    expect(w.find('table').exists()).toBe(false)
    w.unmount()
  })
})
