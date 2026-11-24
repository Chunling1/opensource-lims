import { afterEach, describe, expect, it } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { reactive } from 'vue'
import StandardTitleChoices from './StandardTitleChoices.vue'
import ReportStandardDisplay from './testing/ReportStandardDisplay.vue'
import type { TitleStyle } from './testing/reportTextDisplay'

const wrappers: VueWrapper[] = []
afterEach(() => wrappers.splice(0).forEach(wrapper => wrapper.unmount()))
const codes = Array.from({length: 50}, (_,i) => `GB ${i + 1}-2024`)
const names = Object.fromEntries(codes.map((code,i) => [code, `标准名称${i + 1}`]))
function setup(readonly = false) {
  const wrapper = mount(StandardTitleChoices, {props: {
    id: 'test', codes, names, modelValue: {}, defaultStyle: 'none' as const, readonly,
    'onUpdate:modelValue': (value: Record<string,TitleStyle>) => wrapper.setProps({modelValue:value}),
  }})
  wrappers.push(wrapper)
  return wrapper
}
async function button(wrapper: VueWrapper, text: string) { await wrapper.findAll('button').find(item => item.text() === text)!.trigger('click') }

describe('bounded standard title choices', () => {
  it('shows five rows and retains independent selections across all ten pages', async () => {
    const wrapper = setup()
    for (let page = 1; page <= 10; page++) {
      expect(wrapper.findAll('select')).toHaveLength(5)
      expect(wrapper.get('select').attributes('aria-label')).toBe(`${codes[(page-1)*5]} 书名号`)
      await wrapper.get('select').setValue(page % 2 ? 'CN' : 'EN')
      if (page < 10) await button(wrapper,'下一页')
    }
    expect(wrapper.findAll('button').find(b => b.text()==='下一页')!.attributes('disabled')).toBeDefined()
    for (let page = 10; page >= 1; page--) {
      expect((wrapper.get('select').element as HTMLSelectElement).value).toBe(page % 2 ? 'CN' : 'EN')
      if (page > 1) await button(wrapper,'上一页')
    }
    expect(Object.keys(wrapper.props('modelValue'))).toHaveLength(10)
  })
  it('searches later standards and keeps batch scope clearly all selected standards', async () => {
    const wrapper = setup()
    await wrapper.get('input').setValue('GB 49-2024')
    expect(wrapper.findAll('select')).toHaveLength(1)
    await wrapper.get('select').setValue('EN')
    await button(wrapper,'中文《》')
    expect(Object.keys(wrapper.props('modelValue'))).toHaveLength(50)
    expect(Object.values(wrapper.props('modelValue')).every(v => v === 'CN')).toBe(true)
    await wrapper.get('select').setValue('none')
    await button(wrapper,'清除')
    expect(wrapper.props('modelValue')['GB 49-2024']).toBe('none')
    expect(wrapper.text()).toContain('第 1–5 条 / 共 50 条')
  })
  it('handles no matches and removal of the last page without hiding remaining standards', async () => {
    const wrapper = setup()
    await wrapper.get('input').setValue('不存在')
    expect(wrapper.text()).toContain('没有匹配的标准')
    await button(wrapper,'清除')
    await button(wrapper,'下一页')
    await wrapper.setProps({codes: codes.slice(0,3)})
    expect(wrapper.findAll('select')).toHaveLength(3)
    expect(wrapper.find('nav').exists()).toBe(false)
  })
  it('allows readonly navigation and search but cannot mutate a style', async () => {
    const wrapper = setup(true)
    expect(wrapper.findAll('select').every(s => s.attributes('disabled') !== undefined)).toBe(true)
    await button(wrapper,'下一页')
    expect(wrapper.text()).toContain('第 6–10 条')
    await wrapper.get('input').setValue('GB 49-2024')
    expect(wrapper.findAll('select')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
  it('previews all report standards even while only one page is visible', async () => {
    const wrapper = mount(ReportStandardDisplay,{props:{settings:reactive({standards:codes,standardNames:names,standardShowName:true,standardSeparatorText:'；\n'}),options:[],language:'CN',readonly:false}})
    wrappers.push(wrapper)
    expect(wrapper.findAll('[aria-label$=" 书名号"]')).toHaveLength(5)
    expect((wrapper.get('#report-standard-preview').element as HTMLTextAreaElement).value).toContain('GB 50-2024 《标准名称50》')
    await button(wrapper,'下一页')
    await wrapper.get('[aria-label="GB 6-2024 书名号"]').setValue('none')
    expect((wrapper.get('#report-standard-preview').element as HTMLTextAreaElement).value).toContain('GB 6-2024 标准名称6')
  })
})
