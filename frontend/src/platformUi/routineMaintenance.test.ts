import { beforeEach, expect, it, vi } from 'vitest'
import { request } from '@/services/http'
import { fetchEquipmentDetail, fetchStdDetail, fetchPersonnelDetail, updateEquipment, updateStd, updateStandard, updatePersonnel } from '@/services/quality'
import { updateProjectMaster } from '@/services/projectConfig'
import { ElMessageBox } from 'element-plus'
vi.mock('@/services/http', () => ({ request: vi.fn(), authedFetch: vi.fn() }))
vi.mock('@/services/auth', () => ({ USE_BACKEND: true }))
vi.mock('../services/platform/auth', () => ({ profile: { value: { account: 'demo_admin', features: { businessDataCorrection: true } } } }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn() }, ElMessageBox: { prompt: vi.fn() } }))
beforeEach(() => { vi.clearAllMocks(); vi.mocked(request).mockResolvedValue({ id: 7 }) })
it.each([
  ['equipment', updateEquipment], ['std-library', updateStd], ['standards', updateStandard], ['personnel', updatePersonnel],
] as const)('saves %s through its normal endpoint without privileged proof or prompting', async (kind, save) => {
  const payload = { name: '日常维护' }
  await save(7, payload)
  expect(request).toHaveBeenCalledExactlyOnceWith(`/api/quality/${kind}/7`, { method: 'PUT', body: JSON.stringify(payload) })
  expect(ElMessageBox.prompt).not.toHaveBeenCalled()
})
it('saves project maintenance through the domain endpoint', async () => {
  const payload = { code: 'QA', name: '检测项目', departmentId: 1 } as any
  await updateProjectMaster(7, payload)
  expect(request).toHaveBeenCalledExactlyOnceWith('/api/admin/project-masters/7', { method: 'PUT', body: JSON.stringify(payload) })
  expect(ElMessageBox.prompt).not.toHaveBeenCalled()
})
it.each([['equipment', fetchEquipmentDetail], ['std-library', fetchStdDetail], ['personnel', fetchPersonnelDetail]] as const)('opens %s without a correction snapshot dependency', async (kind, fetch) => {
  await fetch(7)
  expect(request).toHaveBeenCalledTimes(1)
  expect(vi.mocked(request).mock.calls[0][0]).toContain(`/api/quality/${kind}/7`)
})
