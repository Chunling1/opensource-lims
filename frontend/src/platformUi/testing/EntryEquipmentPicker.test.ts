import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive, nextTick } from 'vue'
import EntryEquipmentPicker from './EntryEquipmentPicker.vue'
import { emptyTrialForm, type EntryDetail, type EntryEquipment } from '../../types/testing/dataEntryDetail'

vi.mock('vue-router', () => ({ onBeforeRouteLeave: vi.fn(), onBeforeRouteUpdate: vi.fn() }))
vi.mock('../../components/common/useUnsavedChanges', () => ({ useUnsavedChanges: vi.fn() }))
const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => { wrappers.splice(0).forEach(wrapper => wrapper.unmount()) })
const equipment = (id: string, extra: Partial<EntryEquipment> = {}): EntryEquipment => ({ id, code: `M-${id}`, name: `仪器${id}`, manufacturer: '', serial: '', model: '', status: '可用', selectable: true, lastCalibrationDate: '2026-01-01', validUntil: '2027-01-01', validityNote: '覆盖全部试验区间', ...extra })
function setup(value: string[] = []) {
  const detail = reactive({ sample: { id: 'R1' }, capabilities: { canEdit: true }, equipmentConfig: { version: 0, associatedIds: ['1', '2', '3'], defaultIds: [] }, form: { ...emptyTrialForm(), testDates: [{ kind: 'range', from: '2026-10-01', to: '2026-10-31' }] }, options: { equipment: [equipment('1'), equipment('2', { expiredNow: true, status: '已过期', validUntil: '2026-10-31' }), equipment('3', { selectable: false, status: '停用', validityNote: '不可选：停用' })] } } as unknown as EntryDetail)
  const wrapper = mount(EntryEquipmentPicker, { props: { detail, value }, global: {
    provide: { 'platform-entry-services': {} },
    stubs: {
      BootstrapModal: { template: '<section><slot name="toolbar" /><slot /><slot name="pagination" /><slot name="footer" /></section>' },
      ConfirmationModal: { props: ['title'], template: '<div role="dialog" :aria-label="title"><slot /><slot name="footer" /></div>' },
      EquipmentSchemeBar: true,
      TemplateToast: true,
      RouterLink: true,
    },
  } })
  wrappers.push(wrapper)
  const button = (text: string) => wrapper.findAll('button').find(row => row.text() === text)!
  const checkbox = (id: string, side = '关联设备') => wrapper.get(`table[aria-label="${side}列表"] input[aria-label="选择 M-${id} 仪器${id}"]`)
  return { wrapper, detail, button, checkbox }
}
describe('actual entry equipment picker', () => {
  it('merges the resolved subset without duplicates and retains existing selections', async () => {
    const { wrapper, button } = setup(['1'])
    wrapper.findComponent({ name: 'EquipmentSchemeBar' }).vm.$emit('applied', {
      schemeId: 1, version: 2,
      rows: [1, 2].map(id => ({ id, archiveNo: `M-${id}`, name: `仪器${id}`, actualCalDate: '2026-01-01', validUntil: '2026-10-31', eligibility: { selectable: true, level: 'notice', message: '历史有效期覆盖' } })),
      skipped: [{ id: '3', code: 'M-3', name: '仪器3', reason: '停用' }],
    })
    await nextTick(); await nextTick()
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[['1', '2']]])
  })

  it('filters authorized departments without losing already selected equipment from another department', async () => {
    const { wrapper, detail, button } = setup(['1'])
    detail.options.equipment[0].departmentName = '本部门'
    detail.options.equipment[1].departmentName = '获授权部门'
    detail.options.equipment[2].departmentName = '本部门'
    await nextTick()
    expect(wrapper.get('#equipment-group').text()).toContain('获授权部门')
    await wrapper.get('#equipment-group').setValue('获授权部门')
    await wrapper.get('form[aria-label="关联设备查询"]').trigger('submit')
    const table = wrapper.get('table[aria-label="关联设备列表"]')
    expect(table.text()).toContain('仪器2')
    expect(table.text()).not.toContain('仪器1')
    expect(wrapper.get('table[aria-label="已选设备列表"]').text()).toContain('仪器1')
    await wrapper.get('#equipment-group').setValue('')
    await wrapper.get('form[aria-label="关联设备查询"]').trigger('submit')
    expect(table.findAll('tbody tr')).toHaveLength(3)
  })
  it('displays all statuses and calibration dates, while selection of stopped equipment opens a blocking notice', async () => {
    const { wrapper, checkbox } = setup()
    const table = wrapper.get('table[aria-label="关联设备列表"]')
    expect(table.findAll('tbody tr')).toHaveLength(3)
    for (const text of ['当前状态', '最近校准日期', '可用', '已过期', '停用', '2026-01-01', '不可选：停用']) expect(table.text()).toContain(text)
    await checkbox('3').setValue(true)
    expect(wrapper.get('[role="dialog"]').text()).toContain('不可选：停用')
    expect((checkbox('3').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.get('button[aria-label="移入"]').attributes('disabled')).toBeDefined()
    expect(checkbox('2').attributes('disabled')).toBeUndefined()
  })
  it('shows a blocking notice for expired equipment outside the test window and never offers continue', async () => {
    const { wrapper, detail, checkbox } = setup()
    detail.options.equipment[1].selectable = false
    detail.options.equipment[1].validityNote = '不可选：有效期 2026-01-01 至 2026-10-31'
    detail.form.testDates[0].to = '2026-11-04'
    await nextTick()
    await checkbox('2').setValue(true)
    expect(wrapper.get('[role="dialog"]').text()).toContain('该仪器不能加入已选列表')
    expect(wrapper.get('[role="dialog"]').text()).toContain('2026-11-04')
    expect(wrapper.get('[role="dialog"]').text()).not.toContain('继续选择')
    expect((checkbox('2').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.emitted('select')).toBeUndefined()
  })
  it('keeps equipment with missing calibration dates visible and explains why it cannot be selected', async () => {
    const { wrapper, detail, checkbox } = setup()
    Object.assign(detail.options.equipment[0], {
      selectable: false, lastCalibrationDate: '', validUntil: '',
      validityNote: '不可选：校准有效期未登记完整',
    })
    await nextTick()
    expect(wrapper.get('table[aria-label="关联设备列表"]').text()).toContain('校准有效期未登记完整')
    await checkbox('1').setValue(true)
    expect(wrapper.get('[role="dialog"]').text()).toContain('校准有效期未登记完整')
    expect((checkbox('1').element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.emitted('select')).toBeUndefined()
  })
  it('cancel leaves expired equipment out; confirmation adds it once without a duplicate prompt on save', async () => {
    const { wrapper, checkbox, button } = setup()
    await checkbox('2').setValue(true)
    await wrapper.get('button[aria-label="移入"]').trigger('click')
    expect(wrapper.get('[role="dialog"]').text()).toContain('目前已过期')
    expect(wrapper.get('[role="dialog"]').text()).toContain('2026-10-31')
    await wrapper.get('[role="dialog"] .btn-light').trigger('click')
    expect(wrapper.get('table[aria-label="已选设备列表"]').text()).not.toContain('仪器2')
    await wrapper.get('button[aria-label="移入"]').trigger('click')
    await button('继续选择').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[['2']]])
  })
  it('bulk selection excludes stopped equipment and confirms expired equipment as a batch', async () => {
    const { wrapper, button } = setup()
    await wrapper.get('input[aria-label="全选当前页关联设备"]').setValue(true)
    await wrapper.get('button[aria-label="移入"]').trigger('click')
    await button('继续选择').trigger('click')
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[['1', '2']]])
  })
  it('adds normal equipment without an expiry prompt', async () => {
    const { wrapper, checkbox, button } = setup()
    await checkbox('1').setValue(true)
    await wrapper.get('button[aria-label="移入"]').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[['1']]])
  })
  it('requires confirmation for a preselected expired item', async () => {
    const { wrapper, button } = setup(['2'])
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toBeUndefined()
    await button('继续选择').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[['2']]])
  })
  it('invalidates a pending confirmation when the test dates or instrument status change', async () => {
    const { wrapper, detail, checkbox, button } = setup()
    await checkbox('2').setValue(true)
    await wrapper.get('button[aria-label="移入"]').trigger('click')
    detail.form.testDates[0].to = '2026-11-04'
    detail.options.equipment[1].selectable = false
    await nextTick()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.get('button[aria-label="移入"]').attributes('disabled')).toBeDefined()
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[[]]])
  })
  it('allows removing an invalid existing selection and prevents confirming it', async () => {
    const { wrapper, checkbox, button } = setup(['3'])
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toBeUndefined()
    expect(checkbox('3', '已选设备').attributes('disabled')).toBeUndefined()
    await checkbox('3', '已选设备').setValue(true)
    await wrapper.get('button[aria-label="移出"]').trigger('click')
    await button('确定').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[[]]])
  })
})
