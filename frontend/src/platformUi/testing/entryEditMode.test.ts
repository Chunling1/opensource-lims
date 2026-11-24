import { describe, it, expect } from 'vitest'
import { effectScope, reactive } from 'vue'
import { useEntryEditMode } from './entryEditMode'
function setup(overrides = {}) {
 const c = reactive({ open: true, reportNo: 'R1', account: 'admin', route: '/data_entry',
  canCorrect: true, requestedReadOnly: false, status: '检测录入中', sampleStatus: '已领取', ...overrides })
 const scope = effectScope()
 const mode = scope.run(() => useEntryEditMode(() => c))!
 return { c, mode, stop: () => scope.stop() }
}
describe('explicit data entry correction mode', () => {
 it('admins start normal and need an explicit toggle', () => {
  const { mode, stop } = setup()
  expect(mode.adminEditing.value).toBe(false)
  expect(mode.formReadOnly.value).toBe(false)
  mode.toggleAdminEditing()
  expect(mode.adminEditing.value).toBe(true)
  mode.toggleAdminEditing()
  expect(mode.adminEditing.value).toBe(false)
  stop()
 })
 it.each(['待审核', '已批准', '样品登记中'])('keeps %s readonly until correction is enabled', status => {
  const { mode, stop } = setup({ status })
  expect(mode.formReadOnly.value).toBe(true)
  mode.toggleAdminEditing()
  expect(mode.formReadOnly.value).toBe(false)
  mode.toggleAdminEditing()
  expect(mode.formReadOnly.value).toBe(true)
  stop()
 })
 it('preserves pickup requirements and explicit view-only entry', () => {
  const { c, mode, stop } = setup({ sampleStatus: '待入库' })
  expect(mode.formReadOnly.value).toBe(true)
  c.status = '检测更改中'
  expect(mode.formReadOnly.value).toBe(false)
  c.requestedReadOnly = true
  expect(mode.formReadOnly.value).toBe(true)
  stop()
 })
 it('ordinary accounts cannot activate correction', () => {
  const { mode, stop } = setup({ canCorrect: false })
  mode.toggleAdminEditing()
  expect(mode.adminEditing.value).toBe(false)
  expect(mode.canAdminEdit.value).toBe(false)
  stop()
 })
 it.each(['open', 'reportNo', 'account', 'route', 'canCorrect'])('resets on %s changes', key => {
  const { c, mode, stop } = setup()
  mode.toggleAdminEditing()
  ;(c as any)[key] = typeof (c as any)[key] === 'boolean' ? false : 'changed'
  expect(mode.adminEditing.value).toBe(false)
  stop()
 })
 it('reopening the same report does not retain privileged mode', () => {
  const { c, mode, stop } = setup()
  mode.toggleAdminEditing()
  c.open = false
  c.open = true
  expect(mode.adminEditing.value).toBe(false)
  stop()
 })
})
