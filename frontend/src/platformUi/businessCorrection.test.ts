import { beforeEach, describe, expect, it, vi } from 'vitest'
import { correctForm, formChanges, rememberCorrection } from '@/services/businessCorrection'
import { request } from '@/services/http'
import { profile } from '../services/platform/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
vi.mock('@/services/http', () => ({ request: vi.fn() }))
vi.mock('../services/platform/auth', () => ({ profile: { value: { account: 'demo_admin', features: { businessDataCorrection: true } } } }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn() }, ElMessageBox: { prompt: vi.fn() } }))
const record: any = { revision: 'v1', warning: '管理员修订', fields: ['client','detail','sample_no','report_no'].map(key => ({ key, type: key === 'detail' ? 'object' : 'text' })), values: { client: '原客户', detail: { workflowDates: { approved: '2026-01-01' }, rawSample: { sampleNo: 'S1' } }, sample_no: 'S1', report_no: 'LAB-S1' } }
beforeEach(() => { vi.resetAllMocks(); (profile as any).value = { account: 'demo_admin', features: { businessDataCorrection: true } }; vi.mocked(request).mockResolvedValue(structuredClone(record)); vi.mocked(ElMessageBox.prompt).mockResolvedValue({ value: '核对资料', action: 'confirm' }) })
describe('original form correction integration', () => {
 it('preserves workflow metadata and maps sample/report numbers from the existing sample form', () => {
  const patch = formChanges('reports', record, { fullDetail: { rawSample: { sampleNo: 'S2', reportNo: 'LAB-S2' } } })
  expect(patch.sample_no).toBe('S2'); expect(patch.report_no).toBe('LAB-S2')
  expect((patch.detail as any).workflowDates.approved).toBe('2026-01-01')
 })
 it('sends proof to the original domain endpoint, preserving its side effects', async () => {
  await rememberCorrection('reports', 'R1')
  vi.mocked(request).mockResolvedValueOnce({ correctionRevision: 'v2', correctionValues: record.values, message: '已保存' })
  await correctForm('reports', 'R1', { result: '新值' }, '/api/reports/R1/testinfo')
  expect(request).toHaveBeenLastCalledWith('/api/reports/R1/testinfo', expect.objectContaining({ method: 'PUT' }))
  const body = JSON.parse(String(vi.mocked(request).mock.calls.at(-1)?.[1]?.body))
  expect(body).toEqual({ result: '新值', adminCorrection: { revision: 'v1', reason: '核对资料', confirmed: true } })
 })
 it('cancelling the warning does not write or claim success', async () => {
  await rememberCorrection('reports', 'R2'); vi.mocked(ElMessageBox.prompt).mockRejectedValueOnce('cancel')
  await expect(correctForm('reports', 'R2', { client: '改名' })).rejects.toThrow('已取消保存')
  expect(vi.mocked(request).mock.calls.filter(([,o]) => o?.method === 'PUT')).toHaveLength(0)
  expect(ElMessage.success).not.toHaveBeenCalled()
 })
 it('rejects stale snapshots after switching accounts', async () => {
  await rememberCorrection('reports', 'R3'); (profile as any).value.account = 'admin'
  await expect(correctForm('reports', 'R3', { client: '改名' })).rejects.toThrow('校验信息未加载')
  expect(ElMessageBox.prompt).not.toHaveBeenCalled()
 })
 it('concurrent changes are not accepted as a new successful baseline', async () => {
  await rememberCorrection('reports', 'R4'); vi.mocked(request).mockRejectedValueOnce(Error('数据已被修改'))
  await expect(correctForm('reports', 'R4', { client: '改名' })).rejects.toThrow('数据已被修改')
  expect(ElMessage.success).not.toHaveBeenCalled()
 })
})
