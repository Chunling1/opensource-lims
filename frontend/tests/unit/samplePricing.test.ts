import { describe, expect, it } from 'vitest'
import { blankSubproject, samplePricingErrors } from '../../src/modules/composables/sampleSubprojects'

const rows = (...amounts: string[]) => amounts.map(amount => ({
  ...blankSubproject(), projectName: '测试子项', dept: '测试部门', businessCategory: '测试分类', amount, receivedAmount: amount, paymentDescription: '按约定支付',
}))

describe('样品登记金额校验', () => {
  it('完成登记需要子项目，草稿允许为空或暂不平衡', () => {
    expect(samplePricingErrors([], '100').join()).toContain('至少一个子项目')
    expect(samplePricingErrors([], '', false)).toEqual([])
    expect(samplePricingErrors(rows('20'), '100', false)).toEqual([])
  })
  it.each(['projectName', 'dept', 'businessCategory'] as const)('每一行必须填写 %s', key => {
    const value = rows('40', '60')
    value[1]![key] = ' '
    expect(samplePricingErrors(value, '100').join()).toContain('第2行')
  })
  it.each([
    ['0.30', ['0.1', '0.2']], ['0', ['0']], ['90', ['100', '-10']],
    ['999999999999.99', ['999999999999.98', '0.01']],
  ])('以分精确核对 %s', (price, amounts) => {
    expect(samplePricingErrors(rows(...amounts), price)).toEqual([])
  })
  it('使用子项金额而非收款金额，并显示差额', () => {
    const value = rows('40', '59.99')
    value[0]!.receivedAmount = '100'
    expect(samplePricingErrors(value, '100').join()).toContain('差额 0.01 元')
  })
  it.each(['', 'NaN', '-1', '1e2', '100.001', '1000000000000'])('拒绝无效标准价格 %s', price => {
    expect(samplePricingErrors(rows('100'), price).join()).toContain('标准价格')
  })
  it.each(['', 'NaN', '1e2', '100.001', '1000000000000'])('拒绝无效子项金额 %s', amount => {
    expect(samplePricingErrors(rows(amount), '100').join()).toContain('子项金额')
  })
  it('草稿也拒绝负标准价格', () => {
    expect(samplePricingErrors([], '-10', false).join()).toContain('不能为负数')
  })
})


describe('内部合同无需子项目', () => {
  it('只有内部类型允许空子项目', () => {
    expect(samplePricingErrors([], '0.01', true, '不回传外部ERP合同')).toEqual([])
    for (const kind of ['标准合同', '框架', '虚拟框架', '']) {
      expect(samplePricingErrors([], '0.01', true, kind).join()).toContain('至少一个子项目')
    }
  })
  it('仍校验价格和已经填写的子项目', () => {
    expect(samplePricingErrors([], '-1', true, '不回传外部ERP合同').join()).toContain('标准价格')
    expect(samplePricingErrors(rows('99'), '100', true, '不回传外部ERP合同').join()).toContain('差额')
    expect(samplePricingErrors(rows('100'), '100', true, '不回传外部ERP合同')).toEqual([])
  })
})


describe('付款说明必填', () => {
  it.each([undefined, null, '', '  \n\t', '　'])('保存和完成登记均拒绝空说明 %s', description => {
    const value = rows('40', '60')
    Object.assign(value[1]!, { paymentDescription: description })
    for (const complete of [false, true]) {
      expect(samplePricingErrors(value, '100', complete)).toContain('请填写子项目第2行付款说明')
    }
    expect(samplePricingErrors(value, '', false)).toContain('请填写子项目第2行付款说明')
  })
  it('补充说明后可保存、完成，不代填内容', () => {
    const value = rows('100')
    value[0]!.paymentDescription = '签订合同后支付全款'
    expect(samplePricingErrors(value, '100', false)).toEqual([])
    expect(samplePricingErrors(value, '100', true)).toEqual([])
    expect(value[0]!.paymentDescription).toBe('签订合同后支付全款')
    expect(blankSubproject().paymentDescription).toBe('')
  })
})
