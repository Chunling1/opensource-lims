<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import SaveProgress from '../common/SaveProgress.vue'
import { useSaveProgress } from '../common/useSaveProgress'
import SingleChoice from '../common/SingleChoice.vue'
import TablePagination from '../common/table/TablePagination.vue'
import ReportChangeCandidateTable from './ReportChangeCandidateTable.vue'
import ReportChangeExternalFields from './ReportChangeExternalFields.vue'
import AttachmentLeaveConfirmation from '../common/AttachmentLeaveConfirmation.vue'
import { useAttachmentDraft } from '../common/useAttachmentDraft'
import DataEntryPersonPicker from '../testing/DataEntryPersonPicker.vue'
import type { EntryPeopleScope, EntryPersonCandidate } from '../../types/testing/dataEntryDetail'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { reportChangeTypes, type ReportChangeCandidate, type ReportChangeDraft, type ReportChangeRow, type ReportChangeSource } from '../../types/reports/reportChange'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { clientToday } from '../../services/common/date'
const props = withDefaults(defineProps<{ mode: 'new' | 'edit' | 'view' | 'withdraw' | 'delete'; record?: ReportChangeRow; source?: ReportChangeSource }>(), { source: 'internal' })
const external = computed(() => props.source === 'external')
const emit = defineEmits<{ close: []; saved: [] }>()
const { active: saving, percent: savePercent, start: startSave, finish: finishSave } = useSaveProgress()
const choosing = ref(false), chosen = ref<ReportChangeCandidate[]>([]), selected = ref<ReportChangeCandidate[]>([])
const leftChecked = ref<string[]>([]), rightChecked = ref<string[]>([]), leftPage = ref(1), rightPage = ref(1), leftSize = ref(10), rightSize = ref(10)
const filters = reactive({ commissionCode: '', reportCode: '' })
const applied = ref({ ...filters })
const selectionError = ref('')
const validation = reactive({ report: '', reason: '' })
const pickerButton = ref<HTMLButtonElement>(), reasonInput = ref<HTMLInputElement>()
const excluded = computed(() => selected.value.length ? available.value.filter(row => row.commissionId !== selected.value[0]!.commissionId).map(row => row.id) : [])
const available = computed(() => candidates.value.filter(row => !selected.value.some(s => s.id === row.id)))
const leftRows = computed(() => available.value.slice((leftPage.value - 1) * leftSize.value, leftPage.value * leftSize.value))
const rightRows = computed(() => selected.value.slice((rightPage.value - 1) * rightSize.value, rightPage.value * rightSize.value))
const title = computed(() => choosing.value ? '选择报告' : pickingHandler.value ? '选择处理人' : ({ new: '新增申请', edit: '修改申请', view: '查看申请', withdraw: '撤销申请', delete: '删除申请' })[props.mode])
const record = ref<ReportChangeRow>(), loading = ref(false), busy = ref(false), error = ref<ErrorValue>(''), candidates = ref<ReportChangeCandidate[]>([]), candidateError = ref<ErrorValue>(''), finding = ref(false), withdrawal = ref('')
const draft = reactive<ReportChangeDraft>({ sampleId: '', sampleVersion: 0, releaseId: '', changeType: '委托信息更改', responsibility: '', before: '', after: '', reason: '', charge: false, amount: 0, ...(external.value ? { charge: true, external: { handlerId: '', handlerName: '', isCommissionCustomer: false, evidence: [], allReturned: true } } : {}) })
const uploads = useAttachmentDraft('external', () => props.record?.id, () => draft.external?.evidence || [], () => busy.value, { value: () => [draft, chosen.value], ready: () => ['new', 'edit'].includes(props.mode) && !loading.value && (!props.record || !!record.value) })
async function closeForm() { if ((await uploads.allowLeave())) emit('close') }
const pickingHandler = ref(false), handlerScope = ref<EntryPeopleScope>('department')
async function openHandler() {
  pickingHandler.value = true
  await nextTick()
  document.getElementById('entry-people-scope')?.focus()
}
async function closeHandler() {
  pickingHandler.value = false
  await nextTick()
  document.getElementById('external-handler-select')?.focus()
}
function selectHandler(person: EntryPersonCandidate) {
  if (!draft.external) return
  draft.external.handlerId = person.id; draft.external.handlerName = person.name
  void closeHandler()
}
const editing = computed(() => ['new', 'edit', 'view'].includes(props.mode))
const readonly = computed(() => props.mode === 'view' || props.mode === 'edit' && (!record.value || !record.value.canEdit))
const unavailable = computed(() => busy.value || uploads.blocked.value || loading.value || (!!props.record && !record.value) || readonly.value)
const applicationDate = computed(() => record.value ? new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date(record.value.appliedAt)) : clientToday())
let epoch = 0, candidateEpoch = 0, controller: AbortController | undefined, candidateController: AbortController | undefined
async function search() {
  const token = ++candidateEpoch; candidateController?.abort(); const active = candidateController = new AbortController()
  const query = { commissionCode: filters.commissionCode.trim(), reportCode: filters.reportCode.trim() }
  finding.value = true; candidateError.value = ''
  try {
    const result = await registrationDemo.reportChangeCandidates(query, active.signal, props.source)
    if (token === candidateEpoch) { candidates.value = result; applied.value = query; leftChecked.value = []; leftPage.value = 1 }
  } catch (e) { if (token === candidateEpoch && !active.signal.aborted) candidateError.value = normalizeError(e) }
  finally { if (token === candidateEpoch) finding.value = false }
}
function openPicker() { choosing.value = true; selected.value = [...chosen.value]; selectionError.value = ''; leftChecked.value = []; rightChecked.value = []; leftPage.value = 1; rightPage.value = 1; void search() }
function closePicker() { choosing.value = false; candidateEpoch++; candidateController?.abort(); finding.value = false }
function moveIn() {
  const rows = available.value.filter(row => leftChecked.value.includes(row.id))
  if (new Set([...selected.value, ...rows].map(row => row.commissionId)).size > 1) {
    selectionError.value = '只能选择同一委托单下的报告。'; return
  }
  selected.value.push(...rows)
  leftChecked.value = []
  selectionError.value = ''
}
function moveOut() {
  const removed = selected.value.filter(row => rightChecked.value.includes(row.id))
  selected.value = selected.value.filter(row => !rightChecked.value.includes(row.id))
  for (const row of removed) if (!candidates.value.some(s => s.id === row.id)
    && row.commissionCode.toLowerCase().includes(applied.value.commissionCode.toLowerCase()) && row.reportCode.toLowerCase().includes(applied.value.reportCode.toLowerCase())) candidates.value.push(row)
  rightChecked.value = []
  selectionError.value = ''
}
watch([() => available.value.length, leftSize], () => { leftPage.value = Math.min(leftPage.value, Math.max(1, Math.ceil(available.value.length / leftSize.value))) })
watch([() => selected.value.length, rightSize], () => { rightPage.value = Math.min(rightPage.value, Math.max(1, Math.ceil(selected.value.length / rightSize.value))) })
function choose() {
  chosen.value = [...selected.value]
  const s = chosen.value[0]
  draft.sampleId = s?.id || ''; draft.sampleVersion = s?.version || 0; draft.releaseId = s?.releaseId || ''; error.value = ''; closePicker()
}
watch(() => draft.sampleId, () => { validation.report = '' })
watch(() => draft.reason, () => { validation.reason = '' })
async function load() {
  if (!props.record) return
  const token = ++epoch; controller?.abort(); const active = controller = new AbortController(); error.value = ''; loading.value = true
  try {
    if (props.record) {
      const r = await registrationDemo.reportChangeDetail(props.record.id, active.signal, props.source)
      if (token === epoch) { record.value = r; Object.assign(draft, r) }
    }
  } catch (e) { if (token === epoch && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === epoch) loading.value = false }
}
async function submit(intent: 'save' | 'submit' = 'save') {
  if (busy.value || uploads.blocked.value || loading.value || props.mode === 'view' || (choosing.value || pickingHandler.value) || props.mode === 'delete' && error.value) return
  validation.report = ''; validation.reason = ''; error.value = ''
  if (editing.value) {
    if (!draft.sampleId) validation.report = '请选择报告。'
    if (intent === 'submit' && !draft.reason.trim()) validation.reason = '请填写更改原因。'
    if (validation.report || validation.reason) {
      await nextTick()
      if (validation.report) pickerButton.value?.focus()
      else reasonInput.value?.focus()
      return
    }
  }
  const token = epoch; busy.value = true; error.value = ''
  try {
    if (editing.value) await registrationDemo.saveReportChange(uploads.payload({ ...draft, version: record.value?.version, intent, ...(props.mode === 'new' ? { reports: chosen.value.map(s => ({ sampleId: s.id, sampleVersion: s.version, releaseId: s.releaseId })) } : {}) }), record.value?.id, props.source, external.value ? startSave() : undefined)
    else if (record.value) await registrationDemo.reportChangeAction(record.value.id, record.value.version, props.mode as 'withdraw' | 'delete', withdrawal.value, props.source)
    if (token === epoch) { uploads.commit(); emit('saved') }
  } catch (e) { if (token === epoch) error.value = normalizeError(e) }
  finally { finishSave(); if (token === epoch) busy.value = false }
}
watch(() => [props.mode, props.record?.id], () => {
  if (props.mode === 'delete' && props.record) record.value = { ...props.record }
  else void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; candidateEpoch++; controller?.abort(); candidateController?.abort() })
</script>
<template>
  <BootstrapModal :loading="loading && mode !== 'delete' || choosing && finding" open :title="title" :size="choosing ? 'xl' : editing ? 'lg' : undefined" scrollable :fullscreen-mobile="choosing || pickingHandler" :fill-height="choosing || pickingHandler" :body-class="pickingHandler ? 'p-0 overflow-hidden' : choosing ? 'px-3 pt-0 overflow-auto' : editing || external ? 'py-2' : undefined" :busy="busy" :guard-close="true" @close="choosing ? closePicker() : pickingHandler ? closeHandler() : closeForm()">
    <template v-if="choosing" #toolbar>
      <form class="mb-3" aria-label="报告选择查询" @submit.prevent="search">
        <div class="row gx-3 gy-2 align-items-center">
          <div class="col-12 col-sm d-flex align-items-center gap-2"><label for="change-candidate-commission" class="col-form-label text-nowrap">委托编号</label><input id="change-candidate-commission" v-model="filters.commissionCode" class="form-control" size="1" maxlength="200" /></div>
          <div class="col-12 col-sm d-flex align-items-center gap-2"><label for="change-candidate-report" class="col-form-label text-nowrap">报告编号</label><input id="change-candidate-report" v-model="filters.reportCode" class="form-control" size="1" maxlength="200" /></div>
          <div class="col-auto"><button type="submit" class="btn btn-primary" :disabled="finding">查询</button></div>
        </div>
      </form>
      <ErrorNotice :error="candidateError" retry :busy="finding" @retry="search" />
      <div v-if="selectionError" class="invalid-feedback d-block mb-3" role="alert">{{ selectionError }}</div>
    </template>
    <div v-if="choosing" class="row g-2 h-100 flex-lg-nowrap">
      <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="未选报告">
        <div class="card border shadow-none h-100 mb-0">
          <div class="card-header py-2"><h6 class="mb-0">未选报告 <span class="badge bg-light text-body">{{ available.length }}</span></h6></div>
          <div class="overflow-auto flex-grow-1" :aria-busy="finding">
            <div v-if="finding" class="text-center py-4" role="status"><span class="spinner-border spinner-border-sm me-2"></span>正在加载报告…</div>
            <ReportChangeCandidateTable v-else-if="!candidateError" label="未选报告" :rows="leftRows" :unavailable="excluded" v-model:checked="leftChecked" />
          </div>
          <fieldset :disabled="finding || !!candidateError"><TablePagination label="未选报告" :total="available.length" :page="leftPage" :page-size="leftSize" :sizes="[10, 20, 50]" @page="leftPage = $event" @size="leftSize = $event; leftPage = 1" /></fieldset>
        </div>
      </section>
      <div class="col-12 col-lg-auto flex-shrink-0 d-flex flex-lg-column align-items-center justify-content-center gap-2">
        <button type="button" class="btn btn-primary btn-sm btn-icon" aria-label="移入" title="移入" :disabled="finding || !!candidateError || !leftChecked.length" @click="moveIn"><i class="ti ti-arrow-right d-none d-lg-inline" aria-hidden="true"></i><i class="ti ti-arrow-down d-lg-none" aria-hidden="true"></i></button>
        <button type="button" class="btn btn-light btn-sm btn-icon" aria-label="移出" title="移出" :disabled="finding || !rightChecked.length" @click="moveOut"><i class="ti ti-arrow-left d-none d-lg-inline" aria-hidden="true"></i><i class="ti ti-arrow-up d-lg-none" aria-hidden="true"></i></button>
      </div>
      <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="已选报告">
        <div class="card border shadow-none h-100 mb-0">
          <div class="card-header py-2"><h6 class="mb-0">已选报告 <span class="badge bg-light text-body">{{ selected.length }}</span></h6></div>
          <div class="overflow-auto flex-grow-1"><ReportChangeCandidateTable label="已选报告" :rows="rightRows" v-model:checked="rightChecked" /></div>
          <TablePagination label="已选报告" :total="selected.length" :page="rightPage" :page-size="rightSize" :sizes="[10, 20, 50]" @page="rightPage = $event" @size="rightSize = $event; rightPage = 1" />
        </div>
      </section>
    </div>
    <DataEntryPersonPicker v-else-if="pickingHandler" embedded title="选择处理人" purpose="report-change" :change-source="source" :sample-id="draft.sampleId" role="tester" :initial-scope="handlerScope" :value="draft.external?.handlerId ? { id: draft.external.handlerId, name: draft.external.handlerName } : undefined" @scope="handlerScope = $event" @select="selectHandler" @close="closeHandler" />
    <div v-else-if="loading && mode !== 'delete'" class="text-center py-4" role="status"><span class="spinner-border spinner-border-sm me-2"></span>正在加载申请信息…</div>
    <form v-else-if="!props.record || record" id="internal-change-form" @submit.prevent="submit()">
      <template v-if="editing">
        <fieldset :disabled="busy" class="vstack gap-2">
          <div class="row g-2 align-items-start"><label for="change-original-report" class="col-12 col-sm-2 col-form-label">原报告编号</label><div class="col"><textarea rows="1" id="change-original-report" class="form-control" :class="{ 'is-invalid': validation.report }" :aria-invalid="!!validation.report" :aria-describedby="validation.report ? 'change-report-error' : undefined" :value="record?.reportCode || chosen.map(s => s.reportCode).join('、')" readonly></textarea><div v-if="validation.report" id="change-report-error" class="invalid-feedback" role="alert">{{ validation.report }}</div></div><div v-if="mode === 'new'" class="col-auto"><button ref="pickerButton" type="button" class="btn btn-light" :aria-describedby="validation.report ? 'change-report-error' : undefined" @click="openPicker">选择报告</button></div></div>
          <div class="row g-2 align-items-center"><label for="change-sample" class="col-12 col-sm-2 col-form-label">样品编号</label><div class="col"><textarea rows="1" id="change-sample" class="form-control" :value="record?.sampleCode || chosen.map(s => s.code).join('、')" readonly></textarea></div></div>
          <ReportChangeExternalFields v-if="external" :draft="draft" :readonly="readonly" :busy="busy" @handler="openHandler">
            <template #reason><div class="row g-2 align-items-start"><label for="change-reason" class="col-12 col-sm-2 col-form-label">更改原因</label><div class="col"><input id="change-reason" data-validation-key="reason" ref="reasonInput" :disabled="readonly" v-model="draft.reason" type="text" class="form-control" :class="{ 'is-invalid': validation.reason }" :aria-invalid="!!validation.reason" :aria-describedby="validation.reason ? 'change-reason-error' : undefined" maxlength="1000" /><div v-if="validation.reason" id="change-reason-error" class="invalid-feedback" role="alert">{{ validation.reason }}</div></div></div></template>
          </ReportChangeExternalFields>
          <div v-else class="row g-2 align-items-start"><label for="change-reason" class="col-12 col-sm-2 col-form-label">更改原因</label><div class="col"><input id="change-reason" data-validation-key="reason" ref="reasonInput" :disabled="readonly" v-model="draft.reason" type="text" class="form-control" :class="{ 'is-invalid': validation.reason }" :aria-invalid="!!validation.reason" :aria-describedby="validation.reason ? 'change-reason-error' : undefined" maxlength="1000" /><div v-if="validation.reason" id="change-reason-error" class="invalid-feedback" role="alert">{{ validation.reason }}</div></div></div>
          <div class="d-flex flex-wrap gap-3" role="group" aria-label="更改类型"><div v-for="(type, index) in reportChangeTypes" :key="type" class="d-flex align-items-center gap-2"><SingleChoice :id="`change-type-${index}`" name="change-type" :value="type" :checked="draft.changeType === type" :label="type" :disabled="readonly || busy" @change="draft.changeType = type" /><label :for="`change-type-${index}`" class="mb-0">{{ type }}</label></div></div>
          <div class="row border-top mt-0 g-2 pt-2">
            <div class="col-12 col-md-4 d-flex align-items-center gap-2"><label for="change-department" class="col-form-label text-nowrap">申请部门</label><input id="change-department" class="form-control" :value="record?.department || registrationDepartments.find(d => d.id === currentActor.departmentId)?.name" readonly /></div>
            <div class="col-12 col-md-4 d-flex align-items-center gap-2"><label for="change-applicant" class="col-form-label text-nowrap">申请人</label><input id="change-applicant" class="form-control" :value="record?.applicant || currentActor.name" readonly /></div>
            <div class="col-12 col-md-4 d-flex align-items-center gap-2"><label for="change-application-date" class="col-form-label text-nowrap">申请日期</label><input id="change-application-date" class="form-control" :value="applicationDate" readonly /></div>
          </div>
          <div v-if="record?.withdrawalReason" class="row g-2 align-items-start"><label for="change-withdrawn" class="col-12 col-sm-2 col-form-label">撤回原因</label><div class="col"><textarea id="change-withdrawn" :value="record.withdrawalReason" class="form-control" readonly rows="2"></textarea></div></div>
        </fieldset>
      </template>
      <template v-else><p><strong>{{ record?.code }}</strong> · {{ record?.sampleCode }}</p><template v-if="mode === 'withdraw'"><p>撤销后恢复为申请中，可编辑并重新提交。</p><label for="change-withdraw-reason" class="form-label">撤回原因</label><textarea id="change-withdraw-reason" data-validation-key="reason" v-model="withdrawal" class="form-control" rows="3" maxlength="1000" required></textarea></template><p v-else>确认删除这条申请？</p></template>
    </form>
    <ErrorNotice v-if="!choosing && !pickingHandler" :error="error" :retry="!!props.record && (!record || mode === 'delete')" :busy="loading || busy" @retry="load" @reload="load" />
    <p v-if="mode === 'delete' && loading" class="text-muted small" role="status">正在核对最新信息…</p>
    <template v-if="!pickingHandler" #footer>
      <span v-if="uploads.blocked.value" class="me-auto text-muted" role="status">{{ uploads.active.value ? '附件正在上传，请稍候' : '请重试或移除失败的附件后保存' }}</span>
      <SaveProgress :active="saving" :percent="savePercent" />
      <template v-if="choosing"><span class="me-auto text-muted">已选 {{ selected.length }} 份报告</span><button type="button" class="btn btn-light" @click="closePicker">返回</button><button type="button" class="btn btn-primary" :disabled="finding || !!candidateError" @click="choose">确认</button></template>
      <template v-else><button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button><template v-if="editing && mode !== 'view'"><button class="btn btn-light" form="internal-change-form" :disabled="unavailable">保存</button><button type="button" class="btn btn-primary" :disabled="unavailable" @click="submit('submit')">提交</button></template><button v-else-if="!editing" class="btn" :class="mode === 'delete' ? 'btn-danger' : 'btn-primary'" form="internal-change-form" :disabled="busy || loading || !record || mode === 'delete' && !!error">{{ busy ? mode === 'delete' ? '正在删除…' : '正在处理…' : mode === 'delete' ? '确认删除' : '确认撤销' }}</button></template>
    </template>
  </BootstrapModal>
  <AttachmentLeaveConfirmation />
</template>
