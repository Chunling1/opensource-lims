import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import GenericTable from './TemplateDataTable'
import { ElTable, ElTableColumn } from './controls'
import { platformError, reportPreviewError } from './apiErrors'
import { PlatformError } from '../services/platform/http'
import LoadState from '../components/common/LoadState.vue'
import { createMemoryHistory, createRouter } from 'vue-router'

const full = '检测项目'.repeat(9) + '😀尾部'
const Table = GenericTable as any
const props = { label: '审核', rows: [{ id: '1', name: full }], columns: [{ key: 'name', label: '项目' }], rowKey: (r: any) => r.id, rowLabel: (r: any) => r.name }
describe('template table presentation', () => {
  it('caps default cells at the template limit and retains hover text and source data', () => {
    const wrapper = mount(Table, { props })
    const span = wrapper.get('tbody td span[title]')
    expect(span.text()).toBe(Array.from(full).slice(0, 20).join('') + '…')
    expect(span.attributes('title')).toBe(full)
    expect(props.rows[0].name).toBe(full)
  })
  it('applies the same presentation to text slots and leaves actions operational', async () => {
    const wrapper = mount(Table, { props, slots: { 'cell-name': () => h('strong', full) } })
    expect(wrapper.get('tbody span[title]').attributes('title')).toBe(full)
    let clicked = 0
    const action = mount(Table, { props, slots: { 'cell-name': () => h('button', { onClick: () => clicked++ }, full) } })
    await action.get('tbody button').trigger('click')
    expect(clicked).toBe(1)
    expect(action.get('tbody button').text()).toBe(full)
  })
  it('honours an explicit column limit without splitting Unicode characters', () => {
    const wrapper = mount(Table, { props: { ...props, rows: [{ id: '1', name: '😀😀😀😀' }], columns: [{ key: 'name', label: '项目', truncate: 2 }] } })
    expect(wrapper.get('tbody span[title]').text()).toBe('😀😀…')
  })
  it('also limits platform formatter output without losing the full tooltip', () => {
    const wrapper = mount(ElTable, { props: { data: props.rows, rowKey: 'id' }, slots: { default: () => h(ElTableColumn, { prop: 'name', label: '项目', formatter: () => full }) } })
    expect(wrapper.get('tbody span[title]').attributes('title')).toBe(full)
    expect(wrapper.get('tbody span[title]').text()).toBe(Array.from(full).slice(0, 20).join('') + '…')
  })
})
describe('template error presentation', () => {
  it('connects platform transport failures to system pages, prioritising HTTP status', () => {
    expect(new PlatformError(-1, 'private traceback', null, 500).code).toBe('INTERNAL')
    expect(new PlatformError(-1, 'private traceback', null, 500).message).not.toContain('private')
    expect(new PlatformError(422, 'upstream failure', null, 503).code).toBe('UNAVAILABLE')
    expect(new PlatformError(403, '无权查看', null, 200).status).toBe(403)
    expect(new PlatformError(-1, '请补充数据', null, 200).code).toBe('BUSINESS_RULE')
  })
  it.each([[400,'BAD_REQUEST'],[401,'UNAUTHORIZED'],[403,'FORBIDDEN'],[404,'NOT_FOUND'],[409,'VERSION_CONFLICT'],[422,'BUSINESS_RULE'],[429,'RATE_LIMITED'],[500,'INTERNAL'],[503,'UNAVAILABLE']])('maps platform status %i', (status, code) => {
    expect(platformError(Object.assign(new Error('测试原因'), { status })).code).toBe(code)
  })
  it('does not expose internal server details', () => {
    expect(platformError({ status: 500, message: 'private traceback' }).message).not.toContain('private')
    expect(platformError(new TypeError('Failed to fetch')).code).toBe('NETWORK')
  })
  it('shows a missing controlled version as a prerequisite, not a failed refresh', () => {
    const error = reportPreviewError(new Error('尚无当前受控正式版本；请在报告制作流程中生成并确认，预览不会自动生成'))
    expect(error.code).toBe('BUSINESS_RULE')
    const wrapper = mount(LoadState, { props: { error, hasData: false }, global: { stubs: { RouterLink: true } } })
    expect(wrapper.text()).toContain('尚无当前受控正式版本')
    expect(wrapper.text()).not.toContain('更新失败')
    expect(wrapper.text()).not.toContain('诊断编号')
  })
  it.each([403,404,500,503])('renders the supplied error page for initial status %i', async status => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }] })
    await router.push('/'); await router.isReady()
    const wrapper = mount(LoadState, { props: { error: platformError({ status, message: '测试原因' }), hasData: false }, global: { plugins: [router] } })
    expect(wrapper.find('.card').exists()).toBe(true)
    if (status === 404) expect(wrapper.get('img').attributes('src')).toContain('error400-cover.png')
    else expect(wrapper.text()).toContain(String(status))
  })
})
