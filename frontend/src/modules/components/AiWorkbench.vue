<template>
  <div >
    <button type="button" class="btn btn-light" aria-label="打开 AI 智能工作台" :aria-expanded="visible" @click="togglePanel">
      <span  />AI
    </button>

    <section v-show="visible" class="mb-3" :class="{ expanded }" aria-label="AI 智能工作台">
      <header class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <div>
          <strong>AI 搜索与分析工作台</strong>
          <small>内部数据 · 权限实时校验 · 全程只读</small>
        </div>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <el-button text circle :aria-label="expanded ? '退出全屏' : '展开工作台'" @click="expanded = !expanded">
            <el-icon><FullScreen /></el-icon>
          </el-button>
          <el-button text circle aria-label="关闭 AI 工作台" @click="visible = false">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </header>

      <nav  aria-label="AI 功能切换">
        <button class="btn btn-light" v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activeTab === tab.key }" @click="selectTab(tab.key)">
          {{ tab.label }}
        </button>
      </nav>

      <div >
        <span>范围：当前账号授权部门与项目</span>
        <span v-if="features.rerank">脱敏候选智能重排</span>
        <span>不保存完整对话</span>
      </div>
      <div  :class="statusType" role="status">{{ statusText }}</div>

      <main >
        <section v-show="activeTab === 'search'" class="mb-3">
          <div >
            <el-input
              ref="searchInputRef"
              v-model="searchQuery"
              clearable
              placeholder="报告号、委托号、样品号、标准、能力、设备或费用"
              @input="onSearchInput"
              @keyup.enter="runSearch()"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-button type="primary" :loading="searching" :disabled="!searchQuery.trim()" @click="runSearch()">搜索</el-button>
          </div>

          <div v-if="liveSuggestions.length && !searching"  aria-label="搜索建议">
            <button class="btn btn-light" v-for="item in liveSuggestions" :key="item" type="button" @click="runSearch(item)">
              <el-icon><Search /></el-icon><span>{{ item }}</span>
            </button>
          </div>
          <div v-if="correctionSuggestions.length" >
            你是否要找：
            <button class="btn btn-light" v-for="item in correctionSuggestions" :key="item" type="button" @click="runSearch(item)">{{ item }}</button>
          </div>

          <div >
            <button class="btn btn-light"
              v-for="option in entityOptions"
              :key="option.value"
              type="button"
              :class="{ 'bg-primary-subtle': searchFilters.entityTypes?.includes(option.value) }"
              @click="toggleEntity(option.value)"
            >{{ option.label }}</button>
            <button type="button" class="btn btn-light" @click="filtersOpen = !filtersOpen">{{ filtersOpen ? '收起筛选' : '更多筛选' }}</button>
          </div>
          <div v-show="filtersOpen" class="mb-3">
            <el-select v-model="searchFilters.statuses" multiple collapse-tags clearable placeholder="状态">
              <el-option v-for="item in searchFacets.statuses" :key="item.value" :label="`${item.label} (${item.count})`" :value="item.value" />
            </el-select>
            <el-input v-model="searchFilters.project" clearable placeholder="项目名称" />
            <el-input v-model="searchFilters.dateFrom" clearable placeholder="开始日期 YYYY-MM-DD" />
            <el-input v-model="searchFilters.dateTo" clearable placeholder="结束日期 YYYY-MM-DD" />
          </div>

          <div v-if="!searchCompleted && !searching" >
            <div v-if="recentSearches.length">
              <h4 class="h5 mb-3">本次会话最近搜索</h4>
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-light" v-for="item in recentSearches" :key="item" type="button" @click="runSearch(item)">{{ item }}</button>
              </div>
            </div>
            <div v-if="quickQuestions.length">
              <h4 class="h5 mb-3">推荐问题</h4>
              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-light" v-for="item in quickQuestions.slice(0, 6)" :key="item" type="button" @click="askSuggested(item)">{{ item }}</button>
              </div>
            </div>
          </div>

          <div v-if="searchResults.length" >
            <section v-for="group in groupedResults" :key="group.type" class="mb-3">
              <header><strong>{{ group.label }}</strong><span>{{ group.items.length }}</span></header>
              <button v-for="item in group.items" :key="item.id" type="button" class="btn btn-light" @click="openSource(item, searchQuery)">
                <div class="h6 mb-3">
                  <strong>
                    <template v-for="(part, index) in highlightParts(item.title, item.matchedTerms)" :key="index">
                      <mark v-if="part.highlight">{{ part.text }}</mark><template v-else>{{ part.text }}</template>
                    </template>
                  </strong>
                  <span v-if="item.exactMatch" >精确编号</span>
                </div>
                <span>{{ item.summary }}</span>
                <div class="text-muted small">
                  <small>{{ [item.status, item.department, formatTime(item.updatedAt)].filter(Boolean).join(' · ') }}</small>
                  <small>{{ item.rerankReason || item.matchReason || '业务关键词匹配' }}</small>
                </div>
              </button>
            </section>
            <el-button v-if="nextCursor" text :loading="searching" @click="loadMore">加载更多</el-button>
          </div>
          <el-empty v-else-if="searchCompleted && !searching" description="当前权限范围内没有匹配记录" :image-size="64" />
        </section>

        <section v-show="activeTab === 'analysis'" class="mb-3">
          <div v-if="!features.analysis" >业务分析功能当前处于灰度关闭状态，管理员启用后可使用。</div>
          <div class="row g-3">
            <button class="col-12 col-md-6 btn btn-light"
              v-for="item in analysisTemplates"
              :key="item.id"
              type="button"
              :disabled="!features.analysis || analysisLoading"
              :class="{ 'bg-primary-subtle': selectedTemplateId === item.id }"
              @click="runAnalysis(item)"
            >
              <strong>{{ item.title }}</strong><span>{{ item.description }}</span>
            </button>
          </div>
          <div >
            <el-input v-model="analysisQuestion" placeholder="可补充项目、状态或时间范围" @keyup.enter="runSelectedAnalysis" />
            <el-button type="primary" :loading="analysisLoading" :disabled="!features.analysis || !analysisTemplates.length" @click="runSelectedAnalysis">分析</el-button>
          </div>

          <article v-if="analysisResult" >
            <header class="h6 mb-3">
              <div><strong>{{ analysisResult.title }}</strong><small>{{ analysisResult.scopeLabel }} · {{ formatTime(analysisResult.generatedAt) }}</small></div>
              <span>只读统计</span>
            </header>
            <div class="row g-3">
              <div v-for="metric in analysisResult.metrics" :key="metric.label" class="col-12 col-md-6" :class="metric.tone">
                <span>{{ metric.label }}</span><strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong>
              </div>
            </div>
            <div v-if="analysisAnswer" >{{ analysisAnswer }}</div>
            <div v-for="section in analysisResult.sections" :key="section.title" class="mb-3">
              <h4 class="h5 mb-3">{{ section.title }}</h4>
              <div v-for="row in section.rows" :key="row.label" >
                <span>{{ row.label }}</span>
                <div><i  /></div>
                <strong>{{ row.value }}</strong>
              </div>
            </div>
            <div v-if="analysisResult.warnings.length" >
              <strong>需要关注</strong><p v-for="warning in analysisResult.warnings" :key="warning">{{ warning }}</p>
            </div>
            <div v-if="analysisResult.followUps.length" class="d-flex flex-wrap gap-2">
              <button class="btn btn-light" v-for="item in analysisResult.followUps" :key="item" type="button" @click="analysisQuestion = item; runSelectedAnalysis()">{{ item }}</button>
            </div>
          </article>
          <CitationList :items="analysisCitations" @open="openCitation" />
        </section>

        <section v-show="activeTab === 'chat'" class="mb-3">
          <div  v-if="chatHistory.length">
            <article v-for="(turn, index) in chatHistory" :key="index" :class="['p-3 mb-2 rounded', turn.role === 'user' ? 'bg-primary-subtle' : 'bg-light']">{{ turn.content }}</article>
          </div>
          <el-input
            v-model="question"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
            maxlength="1000"
            show-word-limit
            placeholder="基于当前账号可见记录提问，Ctrl+Enter 发送"
            @keydown.ctrl.enter="ask"
          />
          <el-button  type="primary" :loading="chatting" :disabled="!question.trim()" @click="ask">基于可见记录回答</el-button>
          <CitationList :items="chatCitations" @open="openCitation" />
          <div v-if="lastAnswerResultIds.length" >
            <span>这个回答有帮助吗？</span>
            <button class="btn btn-light" type="button" @click="feedback('helpful')">有帮助</button>
            <button class="btn btn-light" type="button" @click="feedback('unhelpful')">需改进</button>
          </div>
        </section>

        <section v-show="activeTab === 'voice'" class="mb-3">
          <p>录音完成后直接执行，不再要求二次确认；不会保存原音、业务表单或推进流程。</p>
          <div >
            <button class="btn btn-light" type="button" :class="{ 'bg-primary-subtle': voiceTarget === 'search' }" @click="voiceTarget = 'search'">语音搜索</button>
            <button class="btn btn-light" type="button" :class="{ 'bg-primary-subtle': voiceTarget === 'analysis' }" :disabled="!features.analysis" @click="voiceTarget = 'analysis'">语音分析</button>
          </div>
          <el-button  type="primary" :loading="transcribing" :disabled="!voiceAllowed || transcribing" @click="recording ? stopRecording() : startRecording()">
            <el-icon><Microphone /></el-icon>
            {{ recording ? `停止并立即执行 ${elapsedSeconds}s` : voiceAllowed ? '开始录音' : '当前账号未开通语音权限' }}
          </el-button>
          <el-input v-model="transcript" type="textarea" :rows="5" readonly placeholder="识别文本会显示在这里并立即执行" />
        </section>
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElMessage, type InputInstance } from 'element-plus'
import { Close, FullScreen, Microphone, Search } from '@element-plus/icons-vue'
import {
  aiSearch, getAiAnalysisTemplates, getAiSuggestions, sendAiFeedback, streamAiChat, transcribeAudio,
  type AiAnalysisResult, type AiAnalysisTemplate, type AiChatTurn, type AiFacetItem,
  type AiSearchFilters, type AiSearchItem,
} from '@/services/ai'
import { useSessionStore } from '@/stores/session'

type TabName = 'search' | 'analysis' | 'chat' | 'voice'
type StatusType = '' | 'ok' | 'warn' | 'error'
interface CitationItem { number: number; item: AiSearchItem }

const CitationList = defineComponent({
  props: { items: { type: Array as () => CitationItem[], default: () => [] } },
  emits: ['open'],
  setup(props, { emit }) {
    return () => props.items.length ? h('div', { class: 'citation-list' }, [
      h('strong', '引用依据'),
      ...props.items.map((citation) => h(ElButton, {
        text: true,
        onClick: () => emit('open', citation),
      }, () => `[${citation.number}] ${citation.item.title}`)),
    ]) : null
  },
})

const router = useRouter()
const session = useSessionStore()
const visible = ref(false)
const expanded = ref(false)
const activeTab = ref<TabName>('search')
const statusText = ref('AI 只读检索和分析，不参与保存、审核、批准或流程流转。')
const statusType = ref<StatusType>('')
const tabs: Array<{ key: TabName; label: string }> = [
  { key: 'search', label: '全局搜索' }, { key: 'analysis', label: '业务分析' },
  { key: 'chat', label: '连续问答' }, { key: 'voice', label: '语音输入' },
]

const searchInputRef = ref<InputInstance>()
const searchQuery = ref('')
const searchResults = ref<AiSearchItem[]>([])
const searchFacets = ref<{ entityTypes: AiFacetItem[]; statuses: AiFacetItem[] }>({ entityTypes: [], statuses: [] })
const searchFilters = ref<AiSearchFilters>({ entityTypes: [], statuses: [], project: '', dateFrom: '', dateTo: '' })
const nextCursor = ref('')
const searching = ref(false)
const searchCompleted = ref(false)
const filtersOpen = ref(false)
const recentSearches = ref<string[]>([])
const quickQuestions = ref<string[]>([])
const dictionaryTerms = ref<string[]>([])
const correctionSuggestions = ref<string[]>([])
const features = ref({ searchV2: false, analysis: false, rerank: false })
const metaLoaded = ref(false)

const analysisTemplates = ref<AiAnalysisTemplate[]>([])
const selectedTemplateId = ref('')
const analysisQuestion = ref('')
const analysisResult = ref<AiAnalysisResult>()
const analysisAnswer = ref('')
const analysisCitations = ref<CitationItem[]>([])
const analysisLoading = ref(false)

const question = ref('')
const chatHistory = ref<AiChatTurn[]>([])
const chatCitations = ref<CitationItem[]>([])
const chatting = ref(false)
const lastAnswerResultIds = ref<string[]>([])

const transcript = ref('')
const recording = ref(false)
const transcribing = ref(false)
const elapsedSeconds = ref(0)
const voiceTarget = ref<'search' | 'analysis'>('search')
const voiceAllowed = computed(() => session.aiVoiceEnabled && session.canAction('ai.voice.use'))

const entityOptions = [
  { value: 'report', label: '报告' }, { value: 'entrust', label: '委托' }, { value: 'sample', label: '样品' },
  { value: 'standard', label: '标准' }, { value: 'capability', label: '能力' },
  { value: 'equipment', label: '设备' },
]
const groupedResults = computed(() => entityOptions.map((option) => ({
  type: option.value, label: option.label,
  items: searchResults.value.filter((item) => item.entityType === option.value),
})).filter((group) => group.items.length))
const liveSuggestions = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return []
  const identifiers = searchResults.value.map((item) => item.entityId)
  return [...new Set([...identifiers, ...recentSearches.value, ...dictionaryTerms.value])]
    .filter((item) => item.toLowerCase().includes(query) && item.toLowerCase() !== query)
    .slice(0, 7)
})

const safeRoutePermissions: Record<string, string> = {
  '/inspection/entrust/query': 'entrust.query.view',
  '/inspection/sample/flow_query': 'sample.flow_query.view', '/inspection/report/query': 'report.query.view',
  '/inspection/report/review': 'report.review.view', '/inspection/report/approval': 'report.approval.view',
  '/inspection/report/print': 'report.print.view',
  '/inspection/report/archive': 'report.archive.view', '/inspection/testing/data_entry': 'testing.data_entry.view',
  '/inspection/entrust/contract_review': 'entrust.contract_review.view',
  '/inspection/system/custom_project': 'system.custom_project.view',
  '/inspection/quality/standard_library': 'quality.standard_library.view',
  '/inspection/quality/standard_library_department': 'quality.standard_library_department.view',
  '/inspection/quality/equipment_ledger': 'quality.equipment_ledger.view',
  '/inspection/quality/equipment_ledger_department': 'quality.equipment_ledger_department.view',
}
const explicitReportRoutes = [
  { route: '/inspection/testing/data_entry', phrases: ['检测数据录入', '数据录入', '录入数据'] },
  { route: '/inspection/entrust/contract_review', phrases: ['合同评审'] },
  { route: '/inspection/report/review', phrases: ['报告审核', '审核报告', '审核模块'] },
  { route: '/inspection/report/approval', phrases: ['报告批准', '批准报告', '批准模块'] },
  { route: '/inspection/report/print', phrases: ['报告签发', '签发报告', '报告打印', '打印报告'] },
  { route: '/inspection/report/archive', phrases: ['报告归档', '归档报告', '归档模块'] },
]
const navigationVerb = /(?:打开|进入|前往|去往|跳转(?:到|至)?|转到|办理|处理)/

let recorder: MediaRecorder | null = null
let mediaStream: MediaStream | null = null
let chunks: Blob[] = []
let startedAt = 0
let elapsedTimer = 0
let autoStopTimer = 0
let searchDebounceTimer = 0
let searchRequestId = 0

function setStatus(text: string, type: StatusType = '') { statusText.value = text; statusType.value = type }
function recentKey() { return `lims:ai-recent:${session.account || 'current'}` }
function loadRecent() {
  try { recentSearches.value = JSON.parse(sessionStorage.getItem(recentKey()) || '[]').slice(0, 8) } catch { recentSearches.value = [] }
}
function rememberSearch(value: string) {
  recentSearches.value = [value, ...recentSearches.value.filter((item) => item !== value)].slice(0, 8)
  sessionStorage.setItem(recentKey(), JSON.stringify(recentSearches.value))
}
async function ensureMeta() {
  if (metaLoaded.value) return
  try {
    const [suggestions, templates] = await Promise.all([getAiSuggestions(), getAiAnalysisTemplates()])
    quickQuestions.value = suggestions.quickQuestions
    dictionaryTerms.value = [...new Set(suggestions.dictionary.flatMap((item) => [item.canonical, ...item.aliases]))]
    features.value = suggestions.features
    analysisTemplates.value = templates.items
    if (!selectedTemplateId.value && templates.items.length) selectedTemplateId.value = templates.items[0].id
  } catch { /* search itself remains available */ }
  metaLoaded.value = true
}
async function togglePanel() { visible.value = !visible.value; if (visible.value) { loadRecent(); await ensureMeta() } }
async function selectTab(tab: TabName) { activeTab.value = tab; await ensureMeta(); if (tab === 'search') await nextTick(() => searchInputRef.value?.focus()) }
async function open(initial = '') {
  visible.value = true; activeTab.value = 'search'; loadRecent(); await ensureMeta()
  const query = initial.trim()
  if (query) { searchQuery.value = query; await runSearch(query); return }
  await nextTick(); searchInputRef.value?.focus()
}
function toggleEntity(value: string) {
  const selected = searchFilters.value.entityTypes || []
  searchFilters.value.entityTypes = selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]
}
async function runSearch(rawQuery = searchQuery.value, cursor = '') {
  const query = rawQuery.trim(); if (!query || (cursor && searching.value)) return
  const requestId = ++searchRequestId
  searchQuery.value = query; searching.value = true
  if (!cursor) { searchResults.value = []; searchCompleted.value = false; correctionSuggestions.value = [] }
  setStatus('正在检索并重新校验当前账号权限……')
  try {
    const response = await aiSearch(query, searchFilters.value, cursor)
    if (requestId !== searchRequestId) return
    searchResults.value = cursor ? [...searchResults.value, ...response.items] : response.items
    searchFacets.value = response.facets || { entityTypes: [], statuses: [] }
    nextCursor.value = response.nextCursor || ''
    correctionSuggestions.value = response.queryInterpretation?.correctionSuggestions || []
    searchCompleted.value = true; rememberSearch(query)
    const rerankText = response.rerank?.status === 'applied' ? '，已完成脱敏候选重排' : ''
    setStatus(`找到 ${response.totalApprox ?? searchResults.value.length} 条当前权限范围内记录${rerankText}。`, 'ok')
  } catch (error) { if (requestId === searchRequestId) setStatus(error instanceof Error ? error.message : 'AI 检索失败', 'error') }
  finally { if (requestId === searchRequestId) searching.value = false }
}
function onSearchInput(value: string) {
  window.clearTimeout(searchDebounceTimer)
  ++searchRequestId
  searching.value = false
  searchResults.value = []
  nextCursor.value = ''
  searchCompleted.value = false
  const query = value.trim()
  if (!query) return
  searchDebounceTimer = window.setTimeout(() => { void runSearch(query) }, 360)
}
async function loadMore() { if (nextCursor.value) await runSearch(searchQuery.value, nextCursor.value) }
function askSuggested(value: string) { activeTab.value = 'analysis'; analysisQuestion.value = value; void runSelectedAnalysis() }

async function runAnalysis(template: AiAnalysisTemplate) {
  selectedTemplateId.value = template.id
  analysisQuestion.value = template.prompt
  await runSelectedAnalysis()
}
async function runSelectedAnalysis() {
  if (!features.value.analysis || analysisLoading.value) return
  const template = analysisTemplates.value.find((item) => item.id === selectedTemplateId.value) || analysisTemplates.value[0]
  if (!template) return
  const currentQuestion = analysisQuestion.value.trim() || template.prompt
  analysisLoading.value = true; analysisResult.value = undefined; analysisAnswer.value = ''; analysisCitations.value = []
  setStatus('正在执行权限内只读统计并生成引用……')
  try {
    await streamAiChat(currentQuestion, (event) => {
      if (event.type === 'status' && event.text) setStatus(event.text)
      if (event.type === 'tool' && event.data) analysisResult.value = event.data
      if (event.type === 'citation' && event.item && event.number) analysisCitations.value.push({ number: event.number, item: event.item })
      if (event.type === 'delta') analysisAnswer.value += event.text || ''
    }, { mode: 'analysis', templateId: template.id, filters: searchFilters.value })
    setStatus('只读业务分析已完成，数字来自正式业务表。', 'ok')
  } catch (error) { setStatus(error instanceof Error ? error.message : '业务分析失败', 'error') }
  finally { analysisLoading.value = false }
}

async function ask() {
  const currentQuestion = question.value.trim(); if (!currentQuestion || chatting.value) return
  const historyForRequest = chatHistory.value.slice(-6)
  chatHistory.value.push({ role: 'user', content: currentQuestion }); question.value = ''; chatting.value = true
  chatCitations.value = []; lastAnswerResultIds.value = []; let responseText = ''
  setStatus('正在结合当前权限范围内的业务记录回答……')
  try {
    await streamAiChat(currentQuestion, (event) => {
      if (event.type === 'citation' && event.item && event.number) {
        chatCitations.value.push({ number: event.number, item: event.item }); lastAnswerResultIds.value.push(event.item.id)
      }
      if (event.type === 'delta') responseText += event.text || ''
    }, { mode: 'chat', filters: searchFilters.value, history: historyForRequest })
    chatHistory.value.push({ role: 'assistant', content: responseText || '当前授权数据中没有可用依据。' })
    chatHistory.value = chatHistory.value.slice(-12)
    setStatus('回答已生成，请通过引用记录核对。', 'ok')
  } catch (error) {
    chatHistory.value.push({ role: 'assistant', content: error instanceof Error ? error.message : 'AI 请求失败' })
    setStatus(error instanceof Error ? error.message : 'AI 请求失败', 'error')
  } finally { chatting.value = false }
}
async function feedback(rating: 'helpful' | 'unhelpful') {
  try { await sendAiFeedback(rating, lastAnswerResultIds.value); ElMessage.success('反馈已记录，不包含完整对话') }
  catch { ElMessage.warning('反馈暂未提交成功') }
}

function voiceSearchQuery(value: string) { return value.replace(/^\s*(?:请)?(?:帮我|帮忙)?\s*(?:查一下|查询|搜索|查找|检索)\s*/u, '').trim() }
async function startRecording() {
  if (!voiceAllowed.value) { ElMessage.warning('当前账号未开通语音权限'); return }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') { ElMessage.error('当前浏览器不支持安全语音录入'); return }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
    recorder = new MediaRecorder(mediaStream, mime ? { mimeType: mime } : undefined)
    chunks = []; elapsedSeconds.value = 0; startedAt = performance.now()
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
    recorder.onstop = () => { mediaStream?.getTracks().forEach((track) => track.stop()); mediaStream = null; void processRecording() }
    recorder.start(500); recording.value = true
    setStatus('正在录音，停止后将立即执行。')
    elapsedTimer = window.setInterval(() => { elapsedSeconds.value = Math.ceil((performance.now() - startedAt) / 1000) }, 500)
    autoStopTimer = window.setTimeout(stopRecording, 90_000)
  } catch { releaseRecorder(); ElMessage.error('未取得麦克风权限') }
}
function stopRecording() {
  if (!recording.value) return; recording.value = false
  window.clearInterval(elapsedTimer); window.clearTimeout(autoStopTimer)
  if (recorder?.state === 'recording') recorder.stop()
}
async function processRecording() {
  const duration = Math.max(0.1, Math.min(90, (performance.now() - startedAt) / 1000))
  let audio: Blob | null = new Blob(chunks, { type: recorder?.mimeType || 'audio/webm' })
  chunks = []; recorder = null
  if (audio.size > 8 * 1024 * 1024) { audio = null; setStatus('录音超过 8MB，请缩短后重试。', 'error'); return }
  transcribing.value = true; setStatus('正在转写，原始录音不会保存……')
  try {
    transcript.value = await transcribeAudio(audio, duration); audio = null
    const command = voiceSearchQuery(transcript.value)
    if (!command) throw new Error('没有识别到可执行内容，请重试。')
    if (voiceTarget.value === 'analysis' && features.value.analysis) {
      activeTab.value = 'analysis'; analysisQuestion.value = command; await runSelectedAnalysis()
    } else { activeTab.value = 'search'; searchQuery.value = command; await runSearch(command) }
  } catch (error) { setStatus(error instanceof Error ? error.message : '语音识别失败', 'error') }
  finally { audio = null; transcribing.value = false }
}
function releaseRecorder() {
  window.clearTimeout(searchDebounceTimer)
  window.clearInterval(elapsedTimer); window.clearTimeout(autoStopTimer)
  mediaStream?.getTracks().forEach((track) => track.stop()); mediaStream = null; recorder = null; recording.value = false; chunks = []
}

function explicitReportRoute(rawIntent: string) {
  if (!navigationVerb.test(rawIntent)) return ''
  return explicitReportRoutes.find((target) => target.phrases.some((phrase) => rawIntent.includes(phrase)))?.route || ''
}
function openSource(item: AiSearchItem, rawIntent: string) {
  let route = item.route; let permission = item.routePermission
  if (item.entityType === 'report' && route !== '/inspection/report/query') {
    const explicitRoute = explicitReportRoute(rawIntent)
    if (explicitRoute !== route) { route = session.can('report.query.view') ? '/inspection/report/query' : ''; permission = route ? 'report.query.view' : '' }
  }
  const expected = safeRoutePermissions[route]
  if (!route || !expected || expected !== permission || !session.can(expected)) { ElMessage.warning(item.routeDeniedReason || '当前账号没有进入该业务模块的权限'); return }
  if (item.routeDeniedReason) ElMessage.warning(item.routeDeniedReason)
  visible.value = false
  router.push({ path: route, query: { keyword: item.entityId, ...(route === '/inspection/report/query' ? { mode: 'view' } : {}) } })
}
function openCitation(citation: CitationItem) { openSource(citation.item, citation.item.entityType === 'report' ? '报告查询' : '') }
function highlightParts(value: string, rawTerms?: string[]) {
  const terms = (rawTerms || []).filter(Boolean).sort((a, b) => b.length - a.length)
  if (!terms.length) return [{ text: value, highlight: false }]
  const escaped = terms.map((item) => item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
  return value.split(pattern).filter(Boolean).map((text) => ({ text, highlight: terms.some((term) => term.toLowerCase() === text.toLowerCase()) }))
}
function formatTime(value?: string) { return value ? value.replace('T', ' ').replace(/Z$/, '').slice(0, 16) : '' }
function barWidth(rows: Array<{ value: string | number }>, value: string | number) {
  const numbers = rows.map((row) => Number(row.value) || 0); const maximum = Math.max(...numbers, 1)
  return Math.max(3, Math.round(((Number(value) || 0) / maximum) * 100))
}

onUnmounted(releaseRecorder)
watch(searchFilters, () => {
  if (visible.value && activeTab.value === 'search') onSearchInput(searchQuery.value)
}, { deep: true, flush: 'sync' })
watch([visible, activeTab], () => {
  if (!visible.value || activeTab.value !== 'search') {
    window.clearTimeout(searchDebounceTimer)
    ++searchRequestId
    searching.value = false
  }
})
defineExpose({ open })
</script>


