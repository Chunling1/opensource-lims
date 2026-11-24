<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import LoadState from '../../components/common/LoadState.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import { registrationDemo as api } from '../../services/commissions/registrationApi'
import { currentActor, sessionLocked } from '../../stores/session'
import { normalizeError, safeReturn } from '../../services/common/errors'
import { printStatus } from '../../types/commissions/commissionPrint'
import type { TaskPrintContext, TaskPrintJob } from '../../types/testing/taskPrint'

const route = useRoute(), router = useRouter()
const id = computed(() => String(route.params.id))
const returnTo = computed(() => {
  const root = route.path.startsWith('/reports/archive/') ? '/reports/archive' : route.path.startsWith('/testing/data-query/') ? '/testing/data-query' : route.path.startsWith('/testing/task-query/') ? '/testing/task-query' : '/testing/assignment'
  const value = safeReturn(route.query.returnTo, root)
  return ['/testing/assignment', '/testing/task-query', '/testing/data-query', '/reports/archive'].some(path => value === path || value.startsWith(path + '?')) ? value : root
})
const returnLabel = computed(() => returnTo.value.startsWith('/reports/archive') ? '返回报告归档' : returnTo.value.startsWith('/testing/data-query') ? '返回检测数据查询' : returnTo.value.startsWith('/testing/task-query') ? '返回检测任务查询' : '返回检测任务分配')
const context = ref<TaskPrintContext>(), task = ref<TaskPrintJob>(), history = ref<TaskPrintJob[]>([])
const tab = ref('preview'), page = ref(1), size = ref(5), total = ref(0)
const loading = ref(false), submitting = ref(false), historyLoading = ref(false), pdfLoading = ref(false), checking = ref(false)
const loadError = ref(''), error = ref(''), historyError = ref(''), progressError = ref(''), pdfError = ref(''), pdfUrl = ref('')
const clock = ref(Date.now()), frame = ref<HTMLIFrameElement>()
let epoch = 0, selection = 0, historyRequest = 0, pdfRequest = 0, pollRequest = 0, failures = 0
let timer: ReturnType<typeof setTimeout> | undefined, ticker: ReturnType<typeof setInterval> | undefined
const active = computed(() => task.value?.status === 'queued' || task.value?.status === 'running')
const expired = computed(() => !!task.value && task.value.expiresAt <= clock.value)
const historical = computed(() => !!task.value && task.value.sourceVersion !== context.value?.version)
const ready = computed(() => !!context.value && !loadError.value && task.value?.status === 'ready' && !expired.value)
const elapsed = computed(() => task.value ? Math.max(0, Math.floor((clock.value - task.value.createdAt) / 1000)) : 0)
const canGenerate = computed(() => context.value?.canPrint && !submitting.value && !error.value && !(active.value && !historical.value))
const label = (row: TaskPrintJob) => row.status === 'ready' && row.expiresAt <= clock.value ? '文件已过期' : printStatus[row.status]
function clearPdf() { ++pdfRequest; if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); pdfUrl.value = ''; pdfLoading.value = false; pdfError.value = '' }
function fatal(issue: unknown) {
  const problem = normalizeError(issue)
  if (['FORBIDDEN', 'UNAUTHORIZED', 'NOT_FOUND', 'BUSINESS_RULE', 'LOCKED'].includes(problem.code)) { clearPdf(); context.value = undefined; loadError.value = problem.message; return true }
  return false
}
async function fetchPdf() {
  if (!ready.value || !task.value || pdfLoading.value || pdfUrl.value) return
  const token = ++pdfRequest, generation = epoch, selected = task.value.id
  pdfLoading.value = true; pdfError.value = ''
  try {
    const blob = await api.taskPrintPdf(id.value, selected)
    if (token === pdfRequest && generation === epoch && selected === task.value?.id && ready.value) pdfUrl.value = URL.createObjectURL(blob)
  } catch (issue) { if (token === pdfRequest && generation === epoch && !fatal(issue)) pdfError.value = normalizeError(issue).message }
  finally { if (token === pdfRequest && generation === epoch) pdfLoading.value = false }
}
watch(ready, value => { if (value) void fetchPdf(); else clearPdf() })
async function loadHistory() {
  const token = ++historyRequest, generation = epoch
  historyLoading.value = true; historyError.value = ''
  try {
    const result = await api.taskPrintHistory(id.value, page.value, size.value)
    if (token === historyRequest && generation === epoch) { history.value = result.items; total.value = result.total }
  } catch (issue) { if (token === historyRequest && generation === epoch && !fatal(issue)) historyError.value = normalizeError(issue).message }
  finally { if (token === historyRequest && generation === epoch) historyLoading.value = false }
}
async function selectTask(row: TaskPrintJob) {
  ++selection; clearPdf(); task.value = row; tab.value = 'preview'; error.value = ''; progressError.value = ''; failures = 0
  const generation = epoch
  await router.replace({ query: { ...route.query, task: row.id } })
  if (generation !== epoch) return
  if (ready.value) void fetchPdf()
  schedule()
}
async function load() {
  const generation = ++epoch; ++selection; ++historyRequest; clearTimeout(timer); clearPdf()
  context.value = undefined; task.value = undefined; history.value = []; total.value = 0; page.value = 1; tab.value = 'preview'
  error.value = ''; loadError.value = ''; progressError.value = ''; historyError.value = ''; loading.value = true; submitting.value = false; checking.value = false
  if (sessionLocked.value) { loading.value = false; loadError.value = '工作空间已锁定。'; return }
  try {
    const record = await api.taskPrintContext(id.value)
    const result = await api.taskPrintHistory(id.value, 1, size.value)
    const recent = typeof route.query.task === 'string' ? await api.taskPrintJob(id.value, route.query.task) : result.items.find(row => row.sourceVersion === record.version)
    if (generation !== epoch) return
    context.value = record; history.value = result.items; total.value = result.total
    if (recent) await selectTask(recent)
  } catch (issue) { if (generation === epoch) loadError.value = normalizeError(issue).message }
  finally { if (generation === epoch) { loading.value = false; schedule() } }
}
async function submit() {
  if (!canGenerate.value || !context.value) return
  const generation = epoch, selected = ++selection
  submitting.value = true; error.value = ''
  try {
    const result = await api.taskPrintSubmit(id.value, context.value.version)
    if (generation !== epoch) return
    if (selected === selection) await selectTask(result)
    if (generation === epoch) { page.value = 1; await loadHistory() }
  } catch (issue) { if (generation === epoch) error.value = normalizeError(issue).message }
  finally { if (generation === epoch) submitting.value = false }
}
function schedule() {
  clearTimeout(timer)
  if (document.hidden || sessionLocked.value || loadError.value || (!active.value && !progressError.value && tab.value !== 'history')) return
  timer = setTimeout(() => void poll(), failures ? Math.min(15000, 2000 * 2 ** failures) : elapsed.value < 30 ? 2000 : 5000)
}
async function poll() {
  if (document.hidden || sessionLocked.value) return
  clearTimeout(timer)
  const generation = epoch, selected = selection, current = task.value, request = ++pollRequest
  clock.value = Date.now()
  try {
    const record = await api.taskPrintContext(id.value)
    if (generation !== epoch || request !== pollRequest) return
    context.value = record
    if (current) {
      const result = await api.taskPrintJob(id.value, current.id)
      if (generation === epoch && selected === selection && request === pollRequest) { task.value = result; progressError.value = ''; failures = 0 }
    }
    if (generation === epoch && request === pollRequest && tab.value === 'history') await loadHistory()
  } catch (issue) { if (generation === epoch && selected === selection && request === pollRequest && !fatal(issue)) { progressError.value = '暂时无法获取进度，后台任务可能仍在运行。'; failures++ } }
  finally { if (generation === epoch && request === pollRequest) schedule() }
}
async function usePdf(action: 'print' | 'download') {
  if (!ready.value || !pdfUrl.value || checking.value) return
  const generation = epoch, selected = selection
  checking.value = true
  try {
    const record = await api.taskPrintContext(id.value)
    if (generation !== epoch || selected !== selection) return
    context.value = record; clock.value = Date.now()
    if (!ready.value || !pdfUrl.value) return
    if (action === 'download') { const link = document.createElement('a'); link.href = pdfUrl.value; link.download = `${context.value.code}-任务单.pdf`; link.click() }
    else { try { frame.value?.contentWindow?.focus(); frame.value?.contentWindow?.print() } catch { pdfError.value = '请在新标签页打开 PDF，使用文档工具栏打印。' } }
  } catch (issue) { if (generation === epoch && selected === selection && !fatal(issue)) pdfError.value = normalizeError(issue).message }
  finally { if (generation === epoch) checking.value = false }
}
function visibility() { if (document.hidden) clearTimeout(timer); else if (context.value) void poll() }
watch([id, () => currentActor.value.id, sessionLocked], () => void load(), { immediate: true })
watch(() => route.query.task, value => { if (value !== task.value?.id) void load() })
watch([page, size], () => { if (context.value) void loadHistory() })
watch(tab, value => { if (value === 'history') void loadHistory(); schedule() })
onMounted(() => { document.addEventListener('visibilitychange', visibility); ticker = setInterval(() => { clock.value = Date.now() }, 1000) })
onBeforeUnmount(() => { ++epoch; ++selection; ++historyRequest; clearTimeout(timer); clearInterval(ticker); clearPdf(); document.removeEventListener('visibilitychange', visibility) })
</script>
<template>
  <PageHeading title="打印任务单" :parent-to="returnTo" />
  <RouterLink :to="returnTo" class="btn btn-light mb-2"><i class="ti ti-arrow-left me-1" aria-hidden="true"></i>{{ returnLabel }}</RouterLink>
  <LoadState :loading="loading" :error="loadError" :back-to="returnTo" @retry="load" />
  <div v-if="context && !loading && !loadError" class="card">
    <div class="card-header d-flex flex-column flex-xl-row align-items-xl-center justify-content-between gap-3">
      <div><h5 class="card-title mb-1">{{ context.code }} · {{ context.name }}</h5><span class="text-muted text-break">检测方案：{{ context.testPlan }}</span></div>
      <ul class="nav nav-tabs-custom card-header-tabs border-bottom-0 flex-shrink-0" role="tablist" aria-label="任务单打印">
        <li class="nav-item"><a id="task-preview-tab" href="#task-preview-panel" class="nav-link" :class="{ active: tab === 'preview' }" role="tab" aria-controls="task-preview-panel" :aria-selected="tab === 'preview'" @click.prevent="tab = 'preview'">预览与打印</a></li>
        <li class="nav-item"><a id="task-history-tab" href="#task-history-panel" class="nav-link" :class="{ active: tab === 'history' }" role="tab" aria-controls="task-history-panel" :aria-selected="tab === 'history'" @click.prevent="tab = 'history'">生成记录</a></li>
      </ul>
    </div>
    <div v-if="!context.canPrint" class="alert alert-warning m-3" role="alert">仅任务分配中及后续阶段的样品可以生成任务单。已有文件作为历史记录保留。</div>
    <div id="task-preview-panel" class="tab-pane" :class="{ 'd-none': tab !== 'preview' }" role="tabpanel" aria-labelledby="task-preview-tab">
      <div class="px-3 py-2 border-bottom d-flex flex-wrap align-items-center justify-content-between gap-2"><span class="text-muted">A4 · 演示模板</span><button type="button" class="btn btn-primary" :disabled="!canGenerate" @click="submit"><span v-if="submitting" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ submitting ? '正在提交' : task?.status === 'ready' && !historical ? '重新生成并预览' : '生成并预览' }}</button></div>
      <div class="p-3">
        <div v-if="error" class="alert alert-warning" role="alert">{{ error }} <button type="button" class="btn btn-link p-0" @click="load">刷新打印资料</button></div>
        <div v-if="progressError" class="alert alert-warning" role="alert">{{ progressError }} <button type="button" class="btn btn-link p-0" @click="poll">刷新状态</button></div>
        <div v-if="historical" class="alert alert-warning" role="status">历史版本：此文件对应生成时的分配信息，不代表当前分配结果。</div>
        <div v-if="!task" class="text-center py-5"><i class="ti ti-file-type-pdf display-5 text-muted" aria-hidden="true"></i><h5 class="mt-3">生成任务单</h5><p class="text-muted">点击“生成并预览”获取当前分配结果的 PDF。历史文件可在“生成记录”中查看。</p></div>
        <div v-else-if="active" class="text-center py-5" role="status"><div class="spinner-border text-primary mb-3" aria-hidden="true"></div><h5>{{ task.status === 'queued' ? '已加入生成队列' : '正在生成任务单' }}</h5><p>{{ task.stage || '等待后台处理' }} · 已用 {{ elapsed }} 秒</p><p class="text-muted">{{ elapsed >= 30 ? '后台仍在处理，您可以先办理其他业务，稍后查看生成记录。' : '可以离开本页，稍后从同一样品的“打印任务单 → 生成记录”查看。' }}</p><RouterLink :to="returnTo" class="btn btn-light">{{ returnLabel }}</RouterLink></div>
        <div v-else-if="task.status === 'failed' || expired" class="text-center py-5" role="status"><i class="ti ti-alert-circle display-5 text-warning" aria-hidden="true"></i><h5 class="mt-3">{{ expired ? '文件已过期' : '生成失败' }}</h5><p>{{ expired ? '请重新生成任务单。' : task.error }}</p><button type="button" class="btn btn-primary" :disabled="!canGenerate" @click="submit">重新生成</button></div>
        <template v-else-if="ready">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3"><span class="badge bg-success-subtle text-success">已生成</span><div class="d-flex flex-wrap gap-2"><a v-if="pdfUrl" :href="pdfUrl" target="_blank" rel="noopener" class="btn btn-light">在新标签页查看 PDF</a><button type="button" class="btn btn-light" :disabled="!pdfUrl || checking" @click="usePdf('download')">下载 PDF</button><button type="button" class="btn btn-primary" :disabled="!pdfUrl || checking" @click="usePdf('print')"><i class="ti ti-printer me-1" aria-hidden="true"></i>打印</button></div></div>
          <p v-if="pdfLoading" class="text-center py-5" role="status">正在加载 PDF…</p>
          <div v-if="pdfError" class="alert alert-warning" role="alert">{{ pdfError }} <button type="button" class="btn btn-link p-0" @click="fetchPdf">重新加载 PDF</button></div>
          <iframe v-if="pdfUrl" ref="frame" :src="pdfUrl" title="任务单 PDF 预览" class="w-100 border rounded" height="650"></iframe>
        </template>
      </div>
    </div>
    <div id="task-history-panel" class="tab-pane" :class="{ 'd-none': tab !== 'history' }" role="tabpanel" aria-labelledby="task-history-tab">
      <div class="d-flex justify-content-end p-3"><button type="button" class="btn btn-light" :disabled="historyLoading" @click="poll">刷新记录</button></div>
      <div v-if="historyError" class="alert alert-warning mx-3" role="alert">{{ historyError }}</div>
      <div class="table-responsive"><table class="table table-nowrap align-middle mb-0" aria-label="任务单生成记录"><thead class="table-light"><tr><th>提交时间</th><th>提交人</th><th>版本</th><th>状态</th><th>操作</th></tr></thead><tbody>
        <tr v-for="row in history" :key="row.id"><td>{{ new Date(row.createdAt).toLocaleString('zh-CN') }}</td><td>{{ row.submittedBy.name }}（{{ row.submittedBy.id }}）</td><td><span :class="row.sourceVersion !== context.version ? 'text-warning' : 'text-muted'">{{ row.sourceVersion !== context.version ? '历史版本' : '当前版本' }}</span></td><td><span class="badge" :class="row.status === 'failed' ? 'bg-danger-subtle text-danger' : row.status === 'ready' && row.expiresAt > clock ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning'">{{ label(row) }}</span></td><td><button type="button" class="btn btn-link p-0" @click="selectTask(row)">{{ ['queued', 'running'].includes(row.status) ? '查看进度' : row.status === 'failed' || row.expiresAt <= clock ? '查看并重新生成' : '预览' }}</button></td></tr>
        <tr v-if="!history.length"><td colspan="5" class="text-center text-muted py-5">{{ historyLoading ? '正在加载…' : '暂无生成记录' }}</td></tr>
      </tbody></table></div>
      <TablePagination label="任务单生成记录" :total="total" :page="page" :page-size="size" :sizes="[5, 10, 20]" @page="page = $event" @size="size = $event; page = 1" />
    </div>
  </div>
</template>

