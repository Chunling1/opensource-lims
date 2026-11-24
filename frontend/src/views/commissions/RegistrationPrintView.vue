<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CommissionPdfPages from '@/components/CommissionPdfPages.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import LoadState from '../../components/common/LoadState.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import { registrationDemo as api } from '../../services/commissions/registrationApi'
import { registrationReturn, registrationContext } from '../../services/commissions/registrationService'
import { currentActor, sessionLocked } from '../../stores/session'
import { normalizeError, safeReturn } from '../../services/common/errors'
import { copyNames, printDescription, printStatus, type PrintOptions, type PrintTask, type PrintContext } from '../../types/commissions/commissionPrint'

const route = useRoute(), router = useRouter()
const archivePrint = computed(() => route.path.startsWith('/reports/archive/'))
const id = computed(() => String(route.params.id)), returnTo = computed(() => {
  if (!archivePrint.value) return registrationReturn(route.query.returnTo, registrationContext(route.path).root)
  const value = safeReturn(route.query.returnTo, '/reports/archive')
  return value === '/reports/archive' || value.startsWith('/reports/archive?') ? value : '/reports/archive'
})
const kind = computed(() => archivePrint.value || route.params.kind === 'samples' ? 'samples' : 'commissions')
const context = ref<PrintContext>(), task = ref<PrintTask>(), history = ref<PrintTask[]>([])
const options = reactive<{ type: PrintOptions['type'] | ''; layout: PrintOptions['layout']; copies: number[] }>({ type: '', layout: 'normal', copies: [1, 2, 3] })
const tab = ref('preview'), page = ref(1), size = ref(5), total = ref(0)
const loading = ref(false), submitting = ref(false), historyLoading = ref(false), pdfLoading = ref(false)
const loadError = ref(''), error = ref(''), historyError = ref(''), progressError = ref(''), pdfError = ref(''), pdfUrl = ref('')
const clock = ref(Date.now()), frame = ref<HTMLIFrameElement>()
let generation = 0, selection = 0, historyRequest = 0, pdfRequest = 0, polling = false, failures = 0, timer: ReturnType<typeof setTimeout> | undefined
const key = (value: { type: string; layout: string; copies: number[] }) => `${value.type}/${value.layout}/${[...value.copies].sort().join()}`
const matches = computed(() => !!task.value && key(task.value) === key(options))
const expired = computed(() => !!task.value && task.value.expiresAt <= clock.value)
const active = computed(() => task.value?.status === 'queued' || task.value?.status === 'running')
const ready = computed(() => matches.value && task.value?.status === 'ready' && !expired.value)
const elapsed = computed(() => task.value ? Math.max(0, Math.floor((clock.value - task.value.createdAt) / 1000)) : 0)
const valid = computed(() => !!options.type && options.copies.length > 0 && !!context.value?.canPrint)
const labels = (row: PrintTask) => row.expiresAt <= clock.value && row.status === 'ready' ? '文件已过期' : printStatus[row.status]
function clearPdf() { ++pdfRequest; if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value); pdfUrl.value = ''; pdfError.value = ''; pdfLoading.value = false }
async function fetchPdf() {
  if (!ready.value || !task.value || pdfLoading.value || pdfUrl.value) return
  const token = ++pdfRequest, current = task.value.id, epoch = generation
  pdfLoading.value = true; pdfError.value = ''
  try { const blob = await api.printPdf(kind.value, id.value, current); if (token === pdfRequest && epoch === generation && current === task.value?.id && ready.value) pdfUrl.value = URL.createObjectURL(blob) }
  catch (e) { if (token === pdfRequest && epoch === generation) pdfError.value = normalizeError(e).message }
  finally { if (token === pdfRequest) pdfLoading.value = false }
}
function selectType() { options.copies = options.type === 'product' ? [1, 2, 3, 4] : [1, 2, 3] }
watch(() => key(options), () => { clearPdf(); if (ready.value) void fetchPdf() })
watch(ready, value => { if (value) void fetchPdf(); else clearPdf() })
async function loadHistory() {
  const token = ++historyRequest, epoch = generation
  historyLoading.value = true; historyError.value = ''
  try { const result = await api.printHistory(kind.value, id.value, page.value, size.value); if (token === historyRequest && epoch === generation) { history.value = result.items; total.value = result.total } }
  catch (e) { if (token === historyRequest && epoch === generation) historyError.value = normalizeError(e).message }
  finally { if (token === historyRequest && epoch === generation) historyLoading.value = false }
}
async function selectTask(row: PrintTask) {
  ++selection; clearPdf(); task.value = row; progressError.value = ''; error.value = ''; failures = 0
  options.type = row.type; options.layout = row.layout; options.copies = [...row.copies]; tab.value = 'preview'
  await router.replace({ query: { ...route.query, task: row.id } })
  if (ready.value) void fetchPdf()
  schedule()
}
async function load() {
  const epoch = ++generation; ++selection; ++historyRequest; clearTimeout(timer); clearPdf()
  context.value = undefined; task.value = undefined; history.value = []; total.value = 0; page.value = 1
  Object.assign(options, { type: '', layout: 'normal', copies: [1, 2, 3] }); error.value = ''; progressError.value = ''; loadError.value = ''; loading.value = true; submitting.value = false
  try {
    const record = await api.printContext(kind.value, id.value)
    const result = await api.printHistory(kind.value, id.value)
    const recent = typeof route.query.task === 'string' ? await api.printTask(kind.value, id.value, route.query.task) : result.items[0]
    if (epoch !== generation) return
    context.value = record; history.value = result.items; total.value = result.total
    if (recent) await selectTask(recent)
  } catch (e) { if (epoch === generation) loadError.value = normalizeError(e).message }
  finally { if (epoch === generation) { loading.value = false; schedule() } }
}
async function submit() {
  if (!valid.value || !context.value || submitting.value) return
  const epoch = generation, selected = ++selection, optionKey = key(options)
  submitting.value = true; error.value = ''
  try {
    const result = await api.printSubmit(kind.value, id.value, { documentType: kind.value === 'samples' ? 'sample' : 'commission', documentCode: context.value.code, type: options.type as PrintOptions['type'], layout: options.layout, copies: [...options.copies] })
    if (epoch !== generation) return
    if (selected === selection && optionKey === key(options)) await selectTask(result)
    page.value = 1; await loadHistory()
  } catch (e) { if (epoch === generation) error.value = normalizeError(e).message }
  finally { if (epoch === generation) submitting.value = false }
}
function schedule() {
  clearTimeout(timer)
  if (document.hidden || sessionLocked.value || loadError.value || (!active.value && !progressError.value && tab.value !== 'history')) return
  const delay = failures ? Math.min(15000, 2000 * 2 ** failures) : elapsed.value < 30 ? 2000 : 5000
  timer = setTimeout(() => void poll(), delay)
}
async function poll() {
  if (document.hidden || sessionLocked.value) return
  if (polling) { schedule(); return }
  const epoch = generation, selected = selection, current = task.value
  polling = true; clock.value = Date.now()
  try {
    if (current && (active.value || progressError.value)) {
      const result = await api.printTask(kind.value, id.value, current.id)
      if (epoch === generation && selected === selection) { task.value = result; progressError.value = ''; failures = 0 }
    }
    if (epoch === generation && tab.value === 'history') await loadHistory()
  } catch { if (epoch === generation && selected === selection) { progressError.value = '暂时无法获取进度，后台任务可能仍在运行。'; failures++ } }
  finally { polling = false; if (epoch === generation) schedule() }
}
function visibility() { if (document.hidden) clearTimeout(timer); else { clock.value = Date.now(); void poll() } }
function print() { try { frame.value?.contentWindow?.focus(); frame.value?.contentWindow?.print() } catch { pdfError.value = '请在新标签页打开 PDF，使用文档工具栏打印。' } }
watch([kind, () => route.params.id, () => currentActor.value.id, sessionLocked], () => void load(), { immediate: true })
watch([page, size], () => { if (context.value) void loadHistory() })
watch(tab, value => { if (value === 'history') void loadHistory(); schedule() })
document.addEventListener('visibilitychange', visibility)
onBeforeUnmount(() => { ++generation; ++selection; clearTimeout(timer); clearPdf(); document.removeEventListener('visibilitychange', visibility) })
</script>

<template>
  <PageHeading :title="archivePrint ? '打印委托书' : '打印委托单'" :parent-to="returnTo" />
  <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
    <RouterLink :to="returnTo" class="btn btn-light"><i class="ti ti-arrow-left me-1" aria-hidden="true"></i>返回{{ archivePrint ? '报告归档' : registrationContext(route.path).title }}</RouterLink>
  </div>
  <LoadState :loading="loading" :error="loadError" :back-to="returnTo" @retry="load" />
  <div v-if="context && !loading && !loadError" class="card">
    <div class="card-header d-flex flex-column flex-xl-row align-items-xl-center justify-content-between gap-2">
      <div class="d-flex flex-wrap align-items-center gap-2 flex-grow-1"><h5 class="card-title mb-0">{{ context.code }}</h5><span class="text-muted text-break">{{ context.name || '未填写项目名称' }}</span></div>
      <div class="flex-shrink-0 ms-xl-2 pt-3 pt-xl-0 align-self-start align-self-xl-auto">
      <ul class="nav justify-content-end nav-tabs-custom rounded card-header-tabs border-bottom-0" role="tablist" aria-label="委托单打印">
        <li class="nav-item"><a id="print-preview-tab" href="#print-preview-panel" class="nav-link" :class="{ active: tab === 'preview', 'text-muted': tab !== 'preview' }" role="tab" aria-controls="print-preview-panel" :aria-selected="tab === 'preview'" @click.prevent="tab = 'preview'">打印设置与预览</a></li>
        <li class="nav-item"><a id="print-history-tab" href="#print-history-panel" class="nav-link" :class="{ active: tab === 'history', 'text-muted': tab !== 'history' }" role="tab" aria-controls="print-history-panel" :aria-selected="tab === 'history'" @click.prevent="tab = 'history'">生成记录</a></li>
      </ul>
      </div>
    </div>
    <div v-if="!context.canPrint" class="alert alert-warning m-3" role="alert">该委托下暂无样品，无法打印。</div>
    <div class="tab-content">
    <div id="print-preview-panel" class="tab-pane" :class="{ active: tab === 'preview' }" role="tabpanel" aria-labelledby="print-preview-tab">
      <form class="px-3 py-2 border-bottom" aria-label="打印选项" @submit.prevent="submit">
        <fieldset :disabled="submitting" class="d-flex flex-wrap align-items-center gap-3">
          <div class="d-flex align-items-center gap-2"><label for="print-type" class="form-label mb-0 text-nowrap">委托单类型</label><select id="print-type" v-model="options.type" class="form-select w-auto" @change="selectType"><option value="">请选择</option><option value="product">产品</option><option value="engineering">工程</option></select></div>
          <div class="d-flex align-items-center gap-2"><label for="print-layout" class="form-label mb-0">版式</label><select id="print-layout" v-model="options.layout" class="form-select w-auto"><option value="normal">标准版</option><option value="extended">扩展版</option></select></div>
          <div class="d-flex flex-wrap align-items-center gap-3" role="group" aria-label="联次"><span>联次</span><div v-for="(name, index) in copyNames" :key="name" class="form-check mb-0"><input :id="`print-copy-${index}`" v-model="options.copies" class="form-check-input" type="checkbox" :value="index + 1" :disabled="!options.type || (index === 3 && options.type !== 'product')" /><label :for="`print-copy-${index}`" class="form-check-label text-nowrap">{{ name }}</label></div></div>
          <button class="btn btn-primary ms-sm-auto" :disabled="!valid || submitting || (matches && active)"><span v-if="submitting" class="spinner-border spinner-border-sm me-1"></span>{{ submitting ? '正在提交' : '生成并预览' }}</button>
        </fieldset>
        <div v-if="error" class="alert alert-danger mt-3 mb-0" role="alert">{{ error }} <button type="button" class="btn btn-link p-0" @click="load">刷新打印资料</button></div>
      </form>
      <div class="p-3">
        <div v-if="progressError" class="alert alert-warning" role="alert">{{ progressError }} <button class="btn btn-link p-0" @click="poll">刷新状态</button></div>
        <div v-if="!task || !matches" class="text-center py-5"><i class="ti ti-file-type-pdf display-5 text-muted" aria-hidden="true"></i><h5 class="mt-3">{{ task ? '选项已更改' : '生成委托单' }}</h5><p class="text-muted mb-0">{{ task ? '点击“生成并预览”获取所选版本，已有文件保留在生成记录中。' : '选择类型和联次后，生成 PDF 预览。' }}</p></div>
        <div v-else-if="active" class="text-center py-5" role="status"><div class="spinner-border text-primary mb-3"></div><h5>{{ task.status === 'queued' ? '已加入生成队列' : '正在生成委托单' }}</h5><p class="text-muted">{{ printDescription(task) }}</p><p>{{ task.stage || '等待后台处理' }} · 已用 {{ elapsed }} 秒</p><p class="text-muted">{{ elapsed >= 30 ? '后台仍在处理，您可以先办理其他业务，稍后查看生成记录。' : '可以离开本页，稍后从同一记录的“打印 → 生成记录”查看。' }}</p><RouterLink class="btn btn-light" :to="returnTo">{{ archivePrint ? '返回报告归档' : '返回委托列表' }}</RouterLink></div>
        <div v-else-if="task.status === 'failed' || expired" class="text-center py-5" role="status"><i class="ti ti-alert-circle display-5 text-warning" aria-hidden="true"></i><h5 class="mt-3">{{ expired ? '文件已过期' : '生成失败' }}</h5><p class="text-muted">{{ expired ? '请重新生成委托单。' : task.error }}</p><button class="btn btn-primary" :disabled="submitting" @click="submit">重新生成</button></div>
        <template v-else-if="ready">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3"><div><span class="badge bg-success-subtle text-success me-2">已生成</span>{{ printDescription(task) }}</div><div class="d-flex flex-wrap gap-2"><a v-if="pdfUrl" class="btn btn-light" :href="pdfUrl" target="_blank" rel="noopener">在新标签页查看 PDF</a><button class="btn btn-primary" :disabled="!pdfUrl" @click="print"><i class="ti ti-printer me-1" aria-hidden="true"></i>打印</button></div></div>
          <CommissionPdfPages :url="pdfUrl" :filename="`${context.code}-委托单.pdf`" :disabled="pdfLoading || !ready" />
          <div v-if="pdfLoading" class="text-center py-5" role="status">正在加载 PDF…</div>
          <div v-if="pdfError" class="alert alert-warning" role="alert">{{ pdfError }} <button class="btn btn-link p-0" @click="fetchPdf">重新加载 PDF</button></div>
          <iframe v-if="pdfUrl" ref="frame" :src="pdfUrl" title="委托单 PDF 预览" class="w-100 border rounded" height="650"></iframe>
        </template>
      </div>
    </div>
    <div id="print-history-panel" class="tab-pane" :class="{ active: tab === 'history' }" role="tabpanel" aria-labelledby="print-history-tab">
      <div class="d-flex justify-content-end p-3"><button class="btn btn-light" :disabled="historyLoading" @click="loadHistory"><i class="ti ti-refresh me-1" aria-hidden="true"></i>刷新记录</button></div>
      <div v-if="historyError" class="alert alert-warning mx-3" role="alert">{{ historyError }}</div>
      <div class="table-responsive"><table class="table table-nowrap align-middle mb-0" aria-label="委托单生成记录"><thead class="table-light"><tr><th>提交时间</th><th>委托单</th><th>联次</th><th>状态</th><th>操作</th></tr></thead><tbody>
        <tr v-for="row in history" :key="row.id"><td>{{ new Date(row.createdAt).toLocaleString('zh-CN') }}</td><td>{{ row.type === 'product' ? '产品' : '工程' }} · {{ row.layout === 'normal' ? '标准版' : '扩展版' }}</td><td>{{ row.copies.map(n => copyNames[n - 1]).join('、') }}</td><td><span class="badge" :class="row.status === 'failed' ? 'bg-danger-subtle text-danger' : row.status === 'ready' && row.expiresAt > clock ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning'">{{ labels(row) }}</span></td><td><button class="btn btn-link p-0" @click="selectTask(row)">{{ row.status === 'queued' || row.status === 'running' ? '查看进度' : row.status === 'failed' || row.expiresAt <= clock ? '查看并重新生成' : '预览' }}</button></td></tr>
        <tr v-if="!history.length"><td colspan="5" class="text-center text-muted py-5">{{ historyLoading ? '正在加载…' : '暂无生成记录' }}</td></tr>
      </tbody></table></div>
      <TablePagination label="生成记录" :total="total" :page="page" :page-size="size" :sizes="[5, 10, 20]" @page="page = $event" @size="size = $event; page = 1" />
    </div>
    </div>
  </div>
</template>
