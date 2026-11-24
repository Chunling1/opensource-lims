<script setup lang="ts">
import ConfirmationModal from '../common/ConfirmationModal.vue'
import FeedbackNotice from '../common/FeedbackNotice.vue'
import type { UploadProgress } from '../common/fileUploadProgress'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRouter, type RouteLocationNormalized } from 'vue-router'
import FileUploadStatus from '../common/FileUploadStatus.vue'
import { useFileUpload } from '../common/useFileUpload'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateToast from '../common/TemplateToast.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import DataTable from '../common/table/DataTable.vue'
import TablePagination from '../common/table/TablePagination.vue'
import TemplateDate from '../common/TemplateDate.vue'
import TemplateDateRange from '../common/TemplateDateRange.vue'
import TemplateEditableSelect from '../common/TemplateEditableSelect.vue'
import RegistrationAttachments from '../commissions/RegistrationAttachments.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientToday, clientYearRange } from '../../services/common/date'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import type { AssignmentRow } from '../../types/testing/assignment'
import type { DemoAttachment } from '../../types/commissions/registration'
import { taskProcessingColumns, type TaskProcessingInput, type TaskProcessingPage, type TaskProcessingQuery, type TaskProcessingRow, type TaskProcessingDetail, type TaskProcessingAttachments } from '../../types/testing/taskProcessing'

const props = defineProps<{ row?: Pick<AssignmentRow, 'id' | 'code' | 'name' | 'projectName'> }>(), emit = defineEmits<{ close: [] }>(), router = useRouter()
const mode = ref<'list' | 'new' | 'detail' | 'attachments'>('list'), busy = ref(false), loading = ref(false), error = ref<ErrorValue>(''), notice = ref('')
const uploadStatus = useFileUpload()
const deletingBusy = ref(false)
const noticeToast = ref<InstanceType<typeof TemplateToast>>()
watch(notice, value => { if (value) noticeToast.value?.show(); else noticeToast.value?.hide() }, { flush: 'post' })
const page = ref<TaskProcessingPage>(), selected = ref<TaskProcessingDetail>(), files = ref<TaskProcessingAttachments>(), deleting = ref<DemoAttachment>()
const filter = reactive({ handler: '', ...clientYearRange() }), query = ref<TaskProcessingQuery>({ ...filter, page: 1, pageSize: 10 })
const blank = (): TaskProcessingInput => ({ requestId: crypto.randomUUID(), account: currentActor.value.id, name: currentActor.value.name, date: clientToday(), contactMethod: '', contactTarget: '', content: '', notes: '' })
const draft = ref(blank()), original = ref(''), stale = ref(false), uncertain = ref(false)
const dirty = computed(() => mode.value === 'new' && JSON.stringify(draft.value) !== original.value)
const discard = ref<'close' | 'list' | 'navigate'>(), destination = ref(''), form = ref<HTMLFormElement>(), range = ref<InstanceType<typeof TemplateDateRange>>()

const title = computed(() => ({ list: '任务处理记录', new: '新增记录', detail: '查看记录', attachments: '处理记录附件' })[mode.value])
const rows = computed(() => (page.value?.items || []).map((row, index) => ({ ...row, sequence: ((page.value?.page || 1) - 1) * (page.value?.pageSize || 10) + index + 1 })))
const sample = computed(() => page.value?.sample || (props.row && { code: props.row.code, name: props.row.name, testPlan: props.row.projectName }))
const fieldErrors = computed(() => error.value ? error.value.fieldErrors || {} : {})
const canAttach = computed(() => !!files.value?.canManageAttachments && !stale.value)
let epoch = 0, controller: AbortController | undefined, reader: FileReader | undefined
function invalidate() { deletingBusy.value = false; epoch++; controller?.abort(); reader?.abort(); uploadStatus.finish() }
function clearMessages() { error.value = ''; notice.value = ''; stale.value = false; uncertain.value = false; deleting.value = undefined }
async function loadList() {
  if (!props.row || busy.value) return
  invalidate(); const token = epoch, id = props.row.id; controller = new AbortController(); loading.value = true; error.value = ''
  try { const result = await registrationDemo.taskProcessingRecords(id, query.value, controller.signal); if (token === epoch) { page.value = result; query.value.page = result.page } }
  catch (issue) { if (token === epoch && !controller.signal.aborted) error.value = normalizeError(issue) }
  finally { if (token === epoch) loading.value = false }
}
watch(() => props.row?.id, () => {
  invalidate(); mode.value = 'list'; page.value = undefined; files.value = undefined; selected.value = undefined; busy.value = false; discard.value = undefined; clearMessages()
  Object.assign(filter, { handler: '', ...clientYearRange() }); query.value = { ...filter, page: 1, pageSize: 10 }
  if (props.row) void loadList()
}, { immediate: true })
watch(currentActor, () => { invalidate(); emit('close') }, { flush: 'sync' })
function beforeUnload(event: BeforeUnloadEvent) { if (props.row && (dirty.value || busy.value)) { event.preventDefault(); event.returnValue = '' } }
window.addEventListener('beforeunload', beforeUnload)
onBeforeUnmount(() => { invalidate(); window.removeEventListener('beforeunload', beforeUnload) })
function guardNavigation(to: RouteLocationNormalized) {
  if (!props.row) return
  if (busy.value) return false
  if (dirty.value) { destination.value = to.fullPath; discard.value = 'navigate'; return false }
}
onBeforeRouteLeave(guardNavigation)
onBeforeRouteUpdate(guardNavigation)
function finish(target: 'close' | 'list' | 'navigate') {
  discard.value = undefined; original.value = JSON.stringify(draft.value)
  if (target === 'close') { invalidate(); emit('close') }
  else if (target === 'navigate') void router.push(destination.value)
  else { invalidate(); mode.value = 'list'; loading.value = false; clearMessages() }
}
function leave(target: 'close' | 'list') { if (busy.value) return; if (dirty.value) discard.value = target; else finish(target) }
function search() { if (range.value && !range.value.validate()) return; query.value = { ...filter, page: 1, pageSize: query.value.pageSize }; notice.value = ''; void loadList() }
function paginate(values: Partial<TaskProcessingQuery>) { query.value = { ...query.value, ...values }; void loadList() }
async function startNew() {
  if (!page.value?.canCreate || busy.value || loading.value) return
  clearMessages(); draft.value = blank(); original.value = JSON.stringify(draft.value); mode.value = 'new'
  await nextTick(); form.value?.querySelector<HTMLInputElement>('input:not([readonly])')?.focus()
}
function fail(issue: unknown, write = false) {
  error.value = normalizeError(issue)
  stale.value = ['BUSINESS_RULE', 'FORBIDDEN', 'NOT_FOUND', 'NETWORK', 'UNAVAILABLE', 'INTERNAL'].includes(error.value.code)
  uncertain.value = write && ['NETWORK', 'UNAVAILABLE', 'INTERNAL'].includes(error.value.code)
}
async function save() {
  if (!props.row || busy.value || stale.value || !form.value?.reportValidity()) return
  const token = epoch, id = props.row.id; busy.value = true; error.value = ''
  try {
    const record = await registrationDemo.createTaskProcessingRecord(id, { ...draft.value })
    if (token !== epoch) return
    original.value = JSON.stringify(draft.value); mode.value = 'list'; busy.value = false; query.value.page = 1
    const listEpoch = epoch + 1
    await loadList()
    if (epoch !== listEpoch || props.row?.id !== id) return
    const { handler, from, to } = query.value, term = handler?.toLocaleLowerCase()
    const matches = (!term || record.name.toLocaleLowerCase().includes(term) || record.account.toLocaleLowerCase().includes(term)) && (!from || record.date >= from) && (!to || record.date <= to)
    notice.value = matches ? '处理记录已保存。' : '处理记录已保存，但不在当前筛选范围内。'
  } catch (issue) { if (token === epoch) fail(issue, true) }
  finally { if (token === epoch) busy.value = false }
}
async function openRecord(row: TaskProcessingRow, target: 'detail' | 'attachments') {
  if (!props.row || busy.value) return
  invalidate(); const token = epoch; controller = new AbortController(); mode.value = target; loading.value = true; selected.value = row as TaskProcessingDetail; files.value = undefined; clearMessages()
  try {
    if (target === 'detail') { const result = await registrationDemo.taskProcessingRecord(props.row.id, row.id, controller.signal); if (token === epoch) selected.value = result }
    else { const result = await registrationDemo.taskProcessingAttachments(props.row.id, row.id, controller.signal); if (token === epoch) { files.value = result; selected.value = result } }
  } catch (issue) { if (token === epoch && !controller.signal.aborted) fail(issue) }
  finally { if (token === epoch) loading.value = false }
}
function sync(updated: TaskProcessingAttachments) {
  files.value = updated; selected.value = updated
  const row = page.value?.items.find(row => row.id === updated.id)
  if (row) { row.version = updated.version; row.attachmentCount = updated.attachmentCount }
}
async function upload(file: File, progress: UploadProgress) {
  const record = files.value
  if (!record || !props.row || !canAttach.value || busy.value) throw new Error('当前不可上传附件')
  const id = props.row.id, token = epoch; busy.value = true; uploadStatus.start(file.name); error.value = ''; notice.value = ''; deleting.value = undefined
  try {
    if (file.size > 20 * 1024 * 1024) throw new AppError('VALIDATION', '附件不能超过 20 MB。')
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reading = reader = new FileReader(); reading.onload = () => resolve(String(reading.result)); reading.onerror = () => reject(reading.error)
      reading.onabort = () => reject(new AppError('NETWORK', '读取附件已取消。')); reading.onprogress = event => progress('reading', event.loaded, event.lengthComputable ? event.total : undefined); reading.readAsDataURL(file)
    })
    if (token !== epoch) return
    uploadStatus.processing(); progress('uploading')
    const result = await registrationDemo.attachTaskProcessingFile(id, record.id, record.version, { name: file.name, type: file.type, size: file.size, dataUrl }, (loaded, total) => progress(loaded === total ? 'saving' : 'uploading', loaded === total ? undefined : loaded, loaded === total ? undefined : total))
    if (token === epoch) { sync(result); notice.value = '附件已上传。' }
  } catch (issue) { if (token === epoch) fail(issue, true); throw issue }
  finally { if (token === epoch) { busy.value = false; uploadStatus.finish(); reader = undefined } }
}
async function remove() {
  if (!props.row || !files.value || !deleting.value || busy.value || !canAttach.value) return
  const token = epoch; busy.value = true; deletingBusy.value = true; error.value = ''; notice.value = ''
  try {
    const result = await registrationDemo.deleteTaskProcessingFile(props.row.id, files.value.id, files.value.version, deleting.value.id)
    if (token === epoch) { sync(result); deleting.value = undefined; notice.value = '附件已删除。' }
  } catch (issue) { if (token === epoch) fail(issue, true) }
  finally { if (token === epoch) { busy.value = false; deletingBusy.value = false } }
}
async function download(file: DemoAttachment) {
  if (!props.row || !files.value || busy.value) return
  const token = epoch; busy.value = true; error.value = ''
  try {
    const result = await registrationDemo.taskProcessingAttachments(props.row.id, files.value.id)
    if (token !== epoch) return
    sync(result); const latest = result.attachments.find(item => item.id === file.id)
    if (!latest) throw new AppError('NOT_FOUND', '附件不存在或已不可访问。')
    const bytes = atob(latest.dataUrl.slice(latest.dataUrl.indexOf(',') + 1))
    downloadBlob(new Blob([Uint8Array.from(bytes, char => char.charCodeAt(0))], { type: latest.type }), latest.name)
  } catch (issue) { if (token === epoch) fail(issue) }
  finally { if (token === epoch) busy.value = false }
}
async function checkLatest() {
  if (!props.row || busy.value) return
  if (mode.value !== 'new') { if (selected.value) await openRecord(selected.value, mode.value === 'attachments' ? 'attachments' : 'detail'); return }
  const token = epoch; loading.value = true
  try {
    // The same idempotency key is retained after checking the latest status.
    const result = await registrationDemo.taskProcessingRecords(props.row.id, query.value)
    if (token === epoch) { page.value = result; if (result.canCreate) { clearMessages(); notice.value = '已核对最新状态，可再次提交；同一请求不会重复创建记录。' } else error.value = new AppError('BUSINESS_RULE', '样品当前状态仅支持查看记录，请关闭新增表单。') }
  } catch (issue) { if (token === epoch) fail(issue) }
  finally { if (token === epoch) loading.value = false }
}
const fields = [
  { key: 'account', label: '处理人工号', max: 100, required: true }, { key: 'name', label: '处理人姓名', max: 100, required: true },
] as const
const detailFields = [
  { key: 'account', label: '处理人工号' }, { key: 'name', label: '处理人姓名' },
  { key: 'date', label: '处理时间' }, { key: 'contactMethod', label: '联系方式' },
  { key: 'contactTarget', label: '沟通对象' },
] as const
</script>

<template>
  <BootstrapModal :loading="loading" :open="!!row" :title="title" :size="mode === 'detail' ? 'lg' : 'xl'" scrollable :compact-height="mode === 'attachments'" :fullscreen-mobile="['list', 'new'].includes(mode)" :busy="busy" :guard-close="dirty" :body-class="mode === 'detail' ? 'pt-0 pb-2' : ['list', 'new', 'attachments'].includes(mode) ? 'pt-2 pb-2' : undefined" @close="leave('close')">
    <template #toolbar><div v-if="sample && mode !== 'detail'" class="text-break" :class="['list', 'new', 'attachments'].includes(mode) ? 'py-0' : 'py-2'"><strong>{{ sample.code }}</strong><span class="ms-2">{{ sample.name }}</span><span class="text-muted ms-2">检测方案：{{ sample.testPlan || '—' }}</span></div><TemplateToast ref="noticeToast" :message="notice" tone="success" within-modal />
      <form v-if="mode === 'list'" class="row gx-3 gy-2 align-items-start mb-3" aria-label="处理记录查询" @submit.prevent="search">
        <div class="col-12 col-md-4"><div class="row gx-2 align-items-center"><label class="col-auto col-form-label text-nowrap" for="processing-handler">处理人</label><div class="col"><input id="processing-handler" v-model="filter.handler" class="form-control" maxlength="100" placeholder="姓名或工号" /></div></div></div>
        <div class="col-12 col-md-8 col-lg-5"><div class="row gx-2 align-items-start"><label class="col-auto col-form-label text-nowrap" for="processing-range">处理时间</label><div class="col"><TemplateDateRange id="processing-range" ref="range" :from="filter.from" :to="filter.to" within-modal @change="Object.assign(filter, $event)" /></div></div></div>
        <div class="col-12 col-lg-3 d-flex flex-wrap gap-2"><button class="btn btn-primary" type="submit" :disabled="loading">查询</button><button class="btn btn-primary" type="button" :disabled="!page?.canCreate || loading" @click="startNew"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增记录</button></div>
      </form>
    </template>
    <ErrorNotice v-if="!deleting" :error="error" :retry="mode === 'list'" :busy="loading" @retry="loadList" />
    <FeedbackNotice v-if="stale" :message="uncertain ? '操作结果尚未确认，请先刷新核对，勿重复提交。' : '请刷新核对最新状态后再操作。'">{{ uncertain ? '操作结果尚未确认，请先刷新核对，勿重复提交。' : '请刷新核对最新状态后再操作。' }}<button class="btn btn-light btn-sm ms-2" :disabled="busy || loading" @click="checkLatest">{{ mode === 'attachments' ? '刷新附件' : '核对最新状态' }}</button></FeedbackNotice>
    <div v-if="mode === 'list'">

      <DataTable label="处理记录" :rows="rows" :columns="taskProcessingColumns" :row-key="record => record.id" :row-label="record => `第${record.sequence}条记录`" :loading="loading" :error="''">
        <template #cell-name="{ row: record }"><span :title="record.account">{{ record.name }}</span></template>
        <template #cell-attachmentCount="{ row: record }">{{ record.attachmentCount > 0 ? '有' : '' }}</template>
        <template #actions="{ row: record }"><button class="dropdown-item" role="menuitem" @click="openRecord(record, 'detail')">查看记录</button><button class="dropdown-item" role="menuitem" @click="openRecord(record, 'attachments')">附件管理</button></template>
      </DataTable>
    </div>
    <div v-else :inert="busy">
      <div v-if="loading" class="text-center py-3" role="status"><span class="spinner-border spinner-border-sm me-2"></span>正在加载…</div>
      <form v-if="mode === 'new'" id="task-processing-form" ref="form" aria-label="新增处理记录" @submit.prevent="save">
        <div class="row g-3">
          <div class="col-12 col-md-4"><label class="form-label" for="processing-plan">检测方案</label><input id="processing-plan" class="form-control" :value="sample?.testPlan" readonly /></div>
          <div class="col-12 col-md-8"><label class="form-label" for="processing-sample">样品/工程名称</label><input id="processing-sample" class="form-control" :value="sample?.name" readonly /></div>
          <div v-for="field in fields" :key="field.key" class="col-12 col-md-6 col-lg-4"><label class="form-label" :for="`processing-${field.key}`">{{ field.label }} <span class="text-danger">*</span></label><input :id="`processing-${field.key}`" v-model="draft[field.key]" class="form-control" :class="{ 'is-invalid': fieldErrors[field.key] }" :aria-invalid="!!fieldErrors[field.key]" :maxlength="field.max" required /><div class="invalid-feedback">{{ fieldErrors[field.key] }}</div></div>
          <div class="col-12 col-lg-4"><label class="form-label" for="processing-date">处理时间 <span class="text-danger">*</span></label><TemplateDate id="processing-date" v-model="draft.date" required within-modal :class="{ 'is-invalid': fieldErrors.date }" /><div class="invalid-feedback">{{ fieldErrors.date }}</div></div>
          <div class="col-12 col-md-6 col-lg-4"><label class="form-label" for="processing-method">联系方式</label><TemplateEditableSelect id="processing-method" v-model="draft.contactMethod" label="联系方式" :options="['电话', '微信', '邮件', '现场']" :maxlength="100" /><div v-if="fieldErrors.contactMethod" class="text-danger small">{{ fieldErrors.contactMethod }}</div></div>
          <div class="col-12 col-md-6 col-lg-4"><label class="form-label" for="processing-target">沟通对象</label><input id="processing-target" v-model="draft.contactTarget" class="form-control" :class="{ 'is-invalid': fieldErrors.contactTarget }" maxlength="100" /><div class="invalid-feedback">{{ fieldErrors.contactTarget }}</div></div>
          <div class="col-12"><label class="form-label" for="processing-content">处理内容 <span class="text-danger">*</span></label><textarea id="processing-content" v-model="draft.content" class="form-control" :class="{ 'is-invalid': fieldErrors.content }" rows="4" maxlength="500" required></textarea><div class="invalid-feedback">{{ fieldErrors.content }}</div></div>
          <div class="col-12"><label class="form-label" for="processing-notes">备注</label><textarea id="processing-notes" v-model="draft.notes" class="form-control" :class="{ 'is-invalid': fieldErrors.notes }" rows="3" maxlength="500"></textarea><div class="invalid-feedback">{{ fieldErrors.notes }}</div></div>
        </div>
      </form>
      <section v-if="mode === 'detail' && selected && !loading && !error" aria-label="处理记录详情" class="text-break">
        <div class="border-bottom pb-3 mb-3">
          <div class="d-flex flex-wrap align-items-center gap-2 mb-1"><strong>{{ selected.sampleCode }}</strong><span>{{ selected.sampleName || '—' }}</span></div>
          <p class="mb-0"><span class="text-muted">检测方案：</span>{{ selected.testPlan || '—' }}</p>
        </div>
        <div class="row g-3">
          <div v-for="field in detailFields" :key="field.key" class="col-12 col-md-6">
            <dl class="d-flex gap-3 mb-0"><dt class="text-muted fw-normal text-nowrap flex-shrink-0">{{ field.label }}</dt><dd class="mb-0 text-break">{{ selected[field.key] || '—' }}</dd></dl>
          </div>
        </div>
        <section v-for="field in [{ key: 'content', label: '处理内容' }, { key: 'notes', label: '备注' }] as const" :key="field.key" class="mt-3" :aria-label="field.label">
          <h6 class="fw-semibold mb-2">{{ field.label }}</h6>
          <p class="mb-0 text-break" :class="{ 'text-muted': !selected[field.key] }"><template v-for="(line, index) in (selected[field.key] || '—').split('\n')" :key="index"><br v-if="index" />{{ line }}</template></p>
        </section>
      </section>
      <template v-if="mode === 'attachments' && files && !loading">
        <p class="text-break mb-2">{{ files.date }} · {{ files.name }}（{{ files.account }}）· {{ files.content }}</p>
        <p v-if="!files.canManageAttachments" class="text-muted mb-2">当前仅支持查看和下载处理记录附件。</p>
        <RegistrationAttachments fill-empty label="处理记录附件" :files="files.attachments" :can-attach="canAttach" :busy="busy" :upload="upload" @download="download" @remove="deleting = $event; notice = ''; error = ''" />
      </template>
    </div>
    <template #pagination><div v-if="mode === 'list' && page" :inert="loading"><TablePagination label="处理记录" :total="page.total" :page="page.page" :page-size="page.pageSize" :sizes="[10, 20, 50]" @page="paginate({ page: $event })" @size="paginate({ page: 1, pageSize: $event })" /></div></template>
    <template #footer><FileUploadStatus class="me-auto" :state="uploadStatus.state.value" :leave-attempted="uploadStatus.leaveAttempted.value" /><span v-if="busy && !uploadStatus.active.value" class="me-auto text-muted" role="status"><span class="spinner-border spinner-border-sm me-2"></span>正在处理…</span><button class="btn btn-light" :disabled="busy" @click="leave(mode === 'list' ? 'close' : 'list')">{{ mode === 'new' ? '取消' : '关闭' }}</button><button v-if="mode === 'new'" class="btn btn-primary" type="submit" form="task-processing-form" :disabled="busy || loading || stale">保存</button></template>
  </BootstrapModal>
  <ConfirmationModal v-if="discard" title="放弃填写" :busy="busy" @close="discard = undefined">
    <p class="mb-0">尚有未保存的处理记录，是否放弃填写？</p>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="discard = undefined">继续填写</button><button type="button" class="btn btn-danger" :disabled="busy" @click="finish(discard!)">放弃填写</button></template>
  </ConfirmationModal>
  <ConfirmationModal v-if="deleting" title="删除附件" :busy="busy" @close="deleting = undefined">
    <p class="text-break">确认删除附件“{{ deleting.name }}”？</p><ErrorNotice :error="error" />
    <button v-if="stale" type="button" class="btn btn-light" :disabled="busy || loading" @click="checkLatest">刷新附件</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="deleting = undefined">取消</button><button type="button" class="btn btn-danger" :disabled="busy || !canAttach" @click="remove">{{ deletingBusy ? '正在删除…' : '确认删除' }}</button></template>
  </ConfirmationModal>
</template>


