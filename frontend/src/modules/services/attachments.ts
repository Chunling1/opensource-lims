// 报告附件服务：后端模式存私有文件目录并由数据库记录元数据，mock 模式存 localStorage。
import { authedFetch, request } from './http'
import { isLegacySystemCover } from '../../platformUi/reportAttachments'
import { USE_BACKEND } from './auth'
import type { ReportDetailView } from './reports'

export interface Attachment {
  id?: number // 后端附件 id
  name: string
  type: string
  source: string
  status: string
  url?: string // mock 模式的 data URL
  contentType?: string
  sizeBytes?: number
  category?: 'completed_report' | 'report_page' | 'raw_record' | 'other'
  active?: boolean
  mergeEligible?: boolean
  selectedForOfficial?: boolean
  superseded?: boolean
}

export type AttachmentCategory = 'completed_report' | 'report_page' | 'raw_record' | 'other'

export async function deleteAttachment(id: number): Promise<void> {
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error('附件编号无效')
  if (!USE_BACKEND) throw new Error('演示模式不支持删除服务器附件')
  await request(`/api/attachments/${id}`, { method: 'DELETE' })
}

const FILES_KEY = 'hn_report_files'

function loadLocal(): Record<string, Attachment[]> {
  try {
    return JSON.parse(localStorage.getItem(FILES_KEY) || '{}')
  } catch {
    return {}
  }
}
function saveLocal(map: Record<string, Attachment[]>) {
  localStorage.setItem(FILES_KEY, JSON.stringify(map))
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(file)
  })
}

// 列出某报告已上传的附件（不含系统种子附件，那部分由前端展示）
export async function listUploadedAttachments(reportNo: string, view: ReportDetailView): Promise<Attachment[]> {
  if (USE_BACKEND) {
    const data = await request<{ rows: Attachment[] }>(`/api/reports/${encodeURIComponent(reportNo)}/attachments?view=${encodeURIComponent(view)}`)
    return data.rows.filter(file => !isLegacySystemCover(file))
  }
  return (loadLocal()[reportNo] ?? []).filter(file => !isLegacySystemCover(file))
}

export async function uploadAttachment(reportNo: string, file: File, category: AttachmentCategory = 'other'): Promise<void> {
  if (file.size > 500 * 1024 * 1024) throw new Error('单个文件不能超过 500MB')
  if (USE_BACKEND) {
    const form = new FormData()
    form.append('file', file, file.name)
    form.append('category', category)
    await request(`/api/reports/${reportNo}/attachments`, {
      method: 'POST',
      body: form,
    })
    return
  }
  // mock：存 localStorage
  const map = loadLocal()
  const att: Attachment = {
    name: file.name,
    type: /\.pdf$/i.test(file.name) ? 'PDF' : 'Word',
    source: category === 'completed_report' ? '完整报告正文' : category === 'report_page' ? '报告后续页' : category === 'raw_record' ? '原始记录' : '其他附件',
    status: '已上传',
    contentType: file.type,
    url: await fileToDataUrl(file),
  }
  map[reportNo] = [...(map[reportNo] ?? []), att]
  saveLocal(map)
}

export interface CompletePreviewState {
  notices?: string[]
  status: 'missing' | 'queued' | 'running' | 'ready' | 'failed' | 'stale'
  sourceHash?: string
  message: string
}

export async function completePreviewState(reportNo: string, view: ReportDetailView, prepare = false, retry = false): Promise<CompletePreviewState> {
  return request<CompletePreviewState>(
    `/api/reports/${encodeURIComponent(reportNo)}/complete-preview-state?view=${encodeURIComponent(view)}`,
    prepare ? { method: 'POST', body: JSON.stringify({ retry }) } : undefined,
    30_000,
  )
}

export async function completeReportObjectUrl(
  reportNo: string,
  view: ReportDetailView,
  download = false,
): Promise<{ url: string; name: string; receipt: string }> {
  const params = new URLSearchParams({ view })
  if (download) params.set('download', '1')
  const response = await authedFetch(
    `/api/reports/${encodeURIComponent(reportNo)}/complete-preview?${params}`,
  )
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    const body = await response.json()
    throw new Error(body?.message || '完整报告生成失败')
  }
  if (!response.ok || !contentType.includes('application/pdf')) {
    throw new Error(`完整报告生成失败（服务 ${response.status}）`)
  }
  return {
    url: URL.createObjectURL(await response.blob()),
    name: `${reportNo}-完整报告.pdf`,
    receipt: response.headers.get('X-Report-Preview-Receipt') || '',
  }
}

export async function confirmCompleteReportPreview(reportNo: string, receipt: string) {
  return request(`/api/reports/${encodeURIComponent(reportNo)}/complete-preview-confirm`, {
    method: 'POST', body: JSON.stringify({ receipt }),
  })
}

// 取附件内容的本地 blob URL（后端模式带鉴权拉取），用于预览/下载
export async function attachmentObjectUrl(
  att: Attachment,
  view: ReportDetailView,
  download = false,
): Promise<{ url: string; contentType: string }> {
  if (att.url) {
    // mock 的 data URL：推断 content-type
    const ct = att.contentType || (att.type === 'PDF' ? 'application/pdf' : 'application/octet-stream')
    return { url: att.url, contentType: ct }
  }
  if (USE_BACKEND && att.id != null) {
    const params = new URLSearchParams({ view })
    if (download) params.set('download', '1')
    const resp = await authedFetch(`/api/attachments/${att.id}?${params}`)
    const responseType = resp.headers.get('content-type') || ''
    if (responseType.includes('application/json')) {
      const body = await resp.json()
      throw new Error(body?.message || '附件读取失败')
    }
    if (!resp.ok) throw new Error(`附件读取失败（服务 ${resp.status}）`)
    const blob = await resp.blob()
    return { url: URL.createObjectURL(blob), contentType: blob.type || att.contentType || '' }
  }
  return { url: '', contentType: '' }
}

export function isPreviewable(contentType: string, name: string): boolean {
  const ct = (contentType || '').toLowerCase()
  if (ct === 'application/pdf' || ['image/png', 'image/jpeg', 'image/gif', 'image/webp'].includes(ct)) return true
  return /\.(pdf|png|jpe?g|gif|webp)$/i.test(name)
}
