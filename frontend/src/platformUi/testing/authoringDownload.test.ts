import { afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('@/services/http', () => ({ authedFetch: vi.fn(), request: vi.fn() }))
import { authedFetch } from '@/services/http'
import { downloadReportAuthoringTemplate } from '@/services/pipeline'
import { templateCapacityMessage } from './templateCapacityWarnings'
import { ElMessage, feedback } from '../controls'

afterEach(() => { vi.restoreAllMocks(); ElMessage.closeAll() })
describe('Word authoring downloads', () => {
  it('returns the file and shows a warning without treating download as failure', async () => {
    const makeUrl = vi.fn(() => 'blob:authoring-file')
    vi.stubGlobal('URL', class extends URL { static createObjectURL = makeUrl })
    vi.mocked(authedFetch).mockResolvedValue(new Response('test-docx', { headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'X-Template-Capacity-Warnings': encodeURIComponent(JSON.stringify(['SAMPLENAME'])),
    } }))
    const result = await downloadReportAuthoringTemplate('LAB-TEST')
    expect(result.url).toBe('blob:authoring-file')
    expect(result.name).toBe('LAB-TEST-完整报告填写模板.docx')
    expect(makeUrl).toHaveBeenCalledOnce()
    ElMessage.warning(templateCapacityMessage(result.capacityWarnings))
    expect(feedback.tone).toBe('warning')
    expect(feedback.message).toContain('填写模板已下载')
    expect(feedback.message).toContain('SAMPLENAME')
    vi.unstubAllGlobals()
  })
  it('still rejects API validation and permission failures', async () => {
    vi.mocked(authedFetch).mockResolvedValue(new Response(JSON.stringify({code:403,message:'无报告正文编辑权限'}), {headers:{'Content-Type':'application/json'}}))
    await expect(downloadReportAuthoringTemplate('LAB-TEST')).rejects.toThrow('无报告正文编辑权限')
  })
})
