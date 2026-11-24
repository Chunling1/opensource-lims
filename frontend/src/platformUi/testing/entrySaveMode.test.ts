import { beforeEach, describe, expect, it, vi } from 'vitest'
vi.mock('@/services/http', () => ({ request: vi.fn(), authedFetch: vi.fn() }))
vi.mock('@/services/auth', () => ({ USE_BACKEND: true }))
vi.mock('../../services/platform/auth', () => ({ profile: { value: { account: 'admin', features: { businessDataCorrection: true } } } }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn() }, ElMessageBox: { prompt: vi.fn() } }))
import { request } from '@/services/http'
import { updateTestInfo } from '@/services/pipeline'
import { rememberCorrection } from '@/services/businessCorrection'
import { profile } from '../../services/platform/auth'
import { ElMessageBox } from 'element-plus'
beforeEach(() => {
 vi.resetAllMocks()
 ;(profile as any).value = { account: 'admin', features: { businessDataCorrection: true } }
 vi.mocked(ElMessageBox.prompt).mockResolvedValue({ value: '核对原始记录', action: 'confirm' })
})
describe('testinfo save mode', () => {
 it('normal administrator saves do not prompt or send correction proof', async () => {
  await updateTestInfo('R1', { standard: '', result: 'draft' })
  expect(ElMessageBox.prompt).not.toHaveBeenCalled()
  expect(JSON.parse(String(vi.mocked(request).mock.calls[0][1]?.body))).toEqual({ standard: '', result: 'draft' })
 })
 it('explicit correction retains revision, reason and confirmation', async () => {
  vi.mocked(request).mockResolvedValueOnce({ revision: 'v1', warning: '管理员修订', fields: [], values: {} })
  await rememberCorrection('reports', 'R1')
  vi.mocked(request).mockResolvedValueOnce({ correctionRevision: 'v2', correctionValues: {} })
  await updateTestInfo('R1', { standard: '', result: 'corrected' }, true)
  expect(ElMessageBox.prompt).toHaveBeenCalledOnce()
  expect(JSON.parse(String(vi.mocked(request).mock.calls.at(-1)?.[1]?.body))).toEqual({
   standard: '', result: 'corrected', adminCorrection: { revision: 'v1', reason: '核对原始记录', confirmed: true },
  })
 })
 it('cancelling correction never writes', async () => {
  vi.mocked(request).mockResolvedValueOnce({ revision: 'v1', warning: '', fields: [], values: {} })
  await rememberCorrection('reports', 'R2')
  vi.mocked(ElMessageBox.prompt).mockRejectedValueOnce('cancel')
  await expect(updateTestInfo('R2', { standard: '' }, true)).rejects.toThrow('已取消保存')
  expect(vi.mocked(request).mock.calls.filter(([,o]) => o?.method === 'PUT')).toHaveLength(0)
 })
 it('a caller flag does not grant correction permission', async () => {
  ;(profile as any).value.features.businessDataCorrection = false
  await updateTestInfo('R3', { standard: '' }, true)
  expect(ElMessageBox.prompt).not.toHaveBeenCalled()
  expect(JSON.parse(String(vi.mocked(request).mock.calls[0][1]?.body))).toEqual({ standard: '' })
 })
})
