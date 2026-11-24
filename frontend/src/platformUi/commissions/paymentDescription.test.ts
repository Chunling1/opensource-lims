import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import Editor from './RegistrationSampleSubprojects.vue'

describe('登记页付款说明', () => {
  it('空白说明不能提交，补填后提交真实内容', async () => {
    const wrapper = shallowMount(Editor, {
      props: { modelValue: [], options: [{ name: '测试子项', accountingDepartment: '部门', businessCategory: '分类' }] },
      global: {
        provide: { 'platform-registration-subprojects': { isLocked: () => false } },
        stubs: {
          BootstrapModal: { template: '<div><slot/><slot name="footer"/></div>' },
          AdaptiveTableActions: { template: '<div><slot/></div>' },
        },
      },
    })
    await wrapper.find('button.btn-primary').trigger('click')
    await wrapper.find('#subproject-name').setValue('测试子项')
    const description = wrapper.find('#subproject-paymentDescription')
    expect(description.attributes('required')).toBeDefined()
    for (const value of ['', ' \n\t', '　']) {
      await description.setValue(value)
      await wrapper.find('form').trigger('submit')
      expect(wrapper.emitted('update:modelValue')).toBeUndefined()
      expect((description.element as HTMLInputElement).validationMessage).toBe('请填写付款说明')
    }
    await wrapper.find('button.btn-light').trigger('click')
    await wrapper.find('button.btn-primary').trigger('click')
    await wrapper.find('#subproject-name').setValue('测试子项')
    expect((description.element as HTMLInputElement).validity.customError).toBe(false)
    await wrapper.find('#subproject-amount').setValue('100')
    await description.setValue('签订合同后支付全款')
    await wrapper.find('form').trigger('submit')
    const emitted = wrapper.emitted('update:modelValue')!
    expect(emitted).toHaveLength(1)
    expect(emitted[0]![0]).toEqual([expect.objectContaining({ name: '测试子项', paymentDescription: '签订合同后支付全款' })])
    wrapper.unmount()
  })
})
