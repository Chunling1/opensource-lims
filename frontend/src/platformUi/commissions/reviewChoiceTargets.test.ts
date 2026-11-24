import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { computed, defineComponent, h, nextTick, reactive, useId } from 'vue'
import RegistrationReviewModal from '../../components/commissions/RegistrationReviewModal.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import { reviewFormSchema, type ReviewForm } from './reviewForm'

const items = [
  ['tech', '技术能力'], ['instrument', '仪器设备'], ['env', '环境'], ['method', '方法'],
  ['personnel', '人员'], ['sample', '样品'], ['basisAuth', '检验依据授权'],
].map(([key, name]) => ({ key: key!, name: name! }))
const wrappers: VueWrapper[] = []
const HiddenModal = defineComponent({
  setup(_, { slots }) { return () => h('div', { hidden: true }, [slots.default?.(), slots.footer?.()]) },
})

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
})
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('contract review label targets with the hidden quick-review form mounted', () => {
  it('clicks all four previously blocked labels into the visible model, keeping the hidden model unchanged', async () => {
    const form = reactive<ReviewForm>({
      items: Object.fromEntries(items.map(item => [item.key, !['personnel', 'sample'].includes(item.key)])),
      cma: false, cnas: false, opinion: '',
    })
    const saved = vi.fn()
    const ActiveForm = defineComponent({
      setup() {
        const idPrefix = `contract-review-${useId()}`
        const schema = computed(() => reviewFormSchema({
          idPrefix, crItems: items, checkedCount: items.filter(item => form.items[item.key]).length,
          requiredCma: true, requiredCnas: true, reviewDetailLoading: false,
        }))
        return () => h('form', {
          'data-active-review': '',
          onSubmit: (event: Event) => { event.preventDefault(); saved(JSON.parse(JSON.stringify(form))) },
        }, [h(SchemaForm<ReviewForm>, { model: form, schema: schema.value }), h('button', { type: 'submit' }, '保存测试表单')])
      },
    })
    const wrapper = mount(defineComponent({
      setup: () => () => [h(RegistrationReviewModal), h(ActiveForm)],
    }), { attachTo: document.body, global: { stubs: { BootstrapModal: HiddenModal, RouterLink: true } } })
    wrappers.push(wrapper)
    const hiddenInputs = wrapper.findComponent(RegistrationReviewModal).findAll<HTMLInputElement>('input[type="checkbox"]')
    const hiddenBefore = hiddenInputs.map(input => input.element.checked)
    const active = wrapper.get('[data-active-review]')
    expect(active.text()).toContain('5/7 已确认')
    for (const text of ['人员', '样品', '确认 CMA 要求及授权范围', '确认 CNAS 要求及授权范围']) {
      const label = active.findAll<HTMLLabelElement>('label').find(node => node.text() === text)!
      // Native label activation reproduces the browser bug; setValue bypasses the faulty association.
      label.element.click()
      await nextTick()
    }
    expect(form.items.personnel).toBe(true)
    expect(form.items.sample).toBe(true)
    expect(form.cma).toBe(true)
    expect(form.cnas).toBe(true)
    expect(active.text()).toContain('7/7 已确认')
    expect(hiddenInputs.map(input => input.element.checked)).toEqual(hiddenBefore)
    await active.trigger('submit')
    expect(saved).toHaveBeenCalledWith({ items: Object.fromEntries(items.map(item => [item.key, true])), cma: true, cnas: true, opinion: '' })
    const personnel = active.findAll<HTMLLabelElement>('label').find(node => node.text() === '人员')!
    personnel.element.click()
    await nextTick()
    expect(form.items.personnel).toBe(false)
    expect(active.text()).toContain('6/7 已确认')
    const ids = wrapper.findAll('[id]').map(node => node.attributes('id'))
    expect(new Set(ids).size).toBe(ids.length)
  })
})
