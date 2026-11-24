import { authedFetch, request } from '@/services/http'

export interface AiSearchItem {
  id: string
  entityType: string
  entityId: string
  title: string
  summary: string
  status: string
  department: string
  route: string
  routePermission: string
  routeDeniedReason: string
  navigationIntent: string
  score: number
  entityLabel?: string
  updatedAt?: string
  exactMatch?: boolean
  matchedFields?: string[]
  matchedTerms?: string[]
  matchReason?: string
  rerankScore?: number | null
  rerankReason?: string
}

export interface AiSearchFilters {
  entityTypes?: string[]
  statuses?: string[]
  project?: string
  dateFrom?: string
  dateTo?: string
}

export interface AiFacetItem { value: string; label: string; count: number }

export interface AiSearchResponse {
  items: AiSearchItem[]
  nextCursor?: string
  totalApprox?: number
  facets?: { entityTypes: AiFacetItem[]; statuses: AiFacetItem[] }
  queryInterpretation?: { normalized: string; expandedTerms: string[]; correctionSuggestions?: string[]; scope: string }
  rerank?: { enabled: boolean; status: string; candidates?: number }
}

export interface AiAnalysisTemplate {
  id: string
  title: string
  description: string
  prompt: string
}

export interface AiAnalysisMetric {
  label: string
  value: string | number
  unit: string
  tone: 'default' | 'primary' | 'success' | 'warn' | 'danger'
}

export interface AiAnalysisSection {
  title: string
  kind: 'bars' | 'table'
  rows: Array<{ label: string; value: string | number; secondary?: string }>
}

export interface AiAnalysisResult {
  templateId: string
  title: string
  summary: string
  generatedAt: string
  scopeLabel: string
  readOnly: boolean
  metrics: AiAnalysisMetric[]
  sections: AiAnalysisSection[]
  sources: AiSearchItem[]
  warnings: string[]
  followUps: string[]
}

export interface AiChatTurn { role: 'user' | 'assistant'; content: string }

export interface AiChatEvent {
  type: 'status' | 'tool' | 'sources' | 'citation' | 'delta' | 'done' | 'error'
  text?: string
  stage?: string
  name?: string
  data?: AiAnalysisResult
  items?: AiSearchItem[]
  number?: number
  item?: AiSearchItem
  elapsedMs?: number
}

export interface AiFormPatch {
  path: string
  value: string | string[]
  confidence: number
  evidence: string
  warning: string
}

export async function aiSearch(query: string, filters: AiSearchFilters = {}, cursor = ''): Promise<AiSearchResponse> {
  return request<AiSearchResponse>('/api/ai/search', {
    method: 'POST', body: JSON.stringify({ query, filters, pageSize: 20, cursor }),
  })
}

export async function streamAiChat(
  question: string,
  onEvent: (event: AiChatEvent) => void,
  options: { mode?: 'chat' | 'analysis'; templateId?: string; filters?: AiSearchFilters; history?: AiChatTurn[] } = {},
): Promise<void> {
  const response = await authedFetch('/api/ai/chat/stream', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, ...options }),
  })
  if (!response.ok || !response.body) {
    let message = `AI 请求失败（${response.status}）`
    try { message = (await response.json()).message || message } catch { /* empty */ }
    throw new Error(message)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const line = block.split('\n').find((entry) => entry.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)))
    }
    if (done) break
  }
}

export async function getAiAnalysisTemplates(): Promise<{ enabled: boolean; items: AiAnalysisTemplate[] }> {
  return request('/api/ai/analysis/templates')
}

export async function getAiSuggestions(): Promise<{
  quickQuestions: string[]
  dictionary: Array<{ canonical: string; aliases: string[]; entityTypes: string[] }>
  features: { searchV2: boolean; analysis: boolean; rerank: boolean }
}> {
  return request('/api/ai/suggestions')
}

export async function sendAiFeedback(
  rating: 'helpful' | 'unhelpful', resultIds: string[], tags: string[] = [],
): Promise<void> {
  await request('/api/ai/feedback', {
    method: 'POST', body: JSON.stringify({ rating, resultIds, tags }),
  })
}

export async function transcribeAudio(blob: Blob, durationSeconds: number): Promise<string> {
  const body = new FormData()
  body.append('audio', blob, `voice.${blob.type.includes('ogg') ? 'ogg' : 'webm'}`)
  body.append('durationSeconds', String(durationSeconds))
  const data = await request<{ text: string }>('/api/ai/transcriptions', { method: 'POST', body })
  return data.text
}

export async function createFormDraft(schemaId: string, transcript: string, currentValues: Record<string, unknown>): Promise<AiFormPatch[]> {
  const data = await request<{ patches: AiFormPatch[] }>('/api/ai/form-drafts', {
    method: 'POST', body: JSON.stringify({ schemaId, transcript, currentValues }),
  })
  return data.patches
}

export async function auditAppliedDraft(schemaId: string, patches: AiFormPatch[]): Promise<void> {
  await request('/api/ai/form-drafts/apply-audit', {
    method: 'POST', body: JSON.stringify({ schemaId, patches }),
  })
}
