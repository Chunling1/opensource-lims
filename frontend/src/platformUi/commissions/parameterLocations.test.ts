import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { actualParameterAddresses } from '@/data/parameterLocations'
import { ElTag } from '../controls'
const rows = [{ itemName: '温度', address: '虚拟地址甲' }, { itemName: '湿度', address: '虚拟地址甲' }]
const base = { isOnsiteTesting: false, onsiteTestLocation: '', manualCapabilityItems: ['库外一', '库外二'], manualTestLocation: '' }
describe('parameter location aggregation', () => {
  it('unions inherited and individually selected locations in stable order', () => {
    expect(actualParameterAddresses(rows, { ...base, manualParameterLocations: {
      库外一: { mode: 'library', addresses: [] }, 库外二: { mode: 'selected', addresses: ['虚拟地址乙', '虚拟地址甲'] },
    } })).toEqual(['虚拟地址甲', '虚拟地址乙'])
  })
  it('preserves known addresses in preview but blocks incomplete manual addresses when validating', () => {
    expect(actualParameterAddresses(rows, base, false)).toEqual(['虚拟地址甲'])
    expect(() => actualParameterAddresses(rows, base)).toThrow('库外')
    const context = { ...base, manualParameterLocations: {} }
    expect(actualParameterAddresses(rows, context, false)).toEqual(['虚拟地址甲'])
    expect(() => actualParameterAddresses(rows, context)).toThrow('库外一')
  })
  it('supports manual-only database sites, historical addresses and onsite overrides', () => {
    expect(actualParameterAddresses([], { ...base, manualCapabilityItems: ['库外一'], manualParameterLocations: {
      库外一: { mode: 'selected', addresses: ['虚拟地址乙'] },
    } })).toEqual(['虚拟地址乙'])
    expect(actualParameterAddresses(rows, { ...base, manualTestLocation: '历史完整地址' })).toEqual(['虚拟地址甲', '历史完整地址'])
    expect(actualParameterAddresses(rows, { ...base, isOnsiteTesting: true, onsiteTestLocation: '现场甲' })).toEqual(['现场甲'])
  })
})
it('supports the bare closable attribute used by existing tag callers, without making static tags closable', () => {
  const tag = mount(ElTag, { props: { closable: '' as any }, slots: { default: '客户甲' } })
  expect(tag.find('button').exists()).toBe(true)
  tag.unmount()
  const staticTag = mount(ElTag, { slots: { default: '客户甲' } })
  expect(staticTag.find('button').exists()).toBe(false)
  staticTag.unmount()
})
