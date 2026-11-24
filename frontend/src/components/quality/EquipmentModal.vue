<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ScrollableTabs from '../common/ScrollableTabs.vue'
import EquipmentCheckForm from './EquipmentCheckForm.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import RegistrationTestPlanBranch from '../commissions/RegistrationTestPlanBranch.vue'
import { emptyPlanSelection, type PlanSelectionCatalogue, type PlanSelectionState, type PlanSelectionToggle } from '../../types/samples/inbound'
import AttachmentDraftStatus from '../common/AttachmentDraftStatus.vue'
import AttachmentLeaveConfirmation from '../common/AttachmentLeaveConfirmation.vue'
import { useAttachmentDraft } from '../common/useAttachmentDraft'
import PersonnelAttachments from './PersonnelAttachments.vue'
import EquipmentBasicForm from './EquipmentBasicForm.vue'
import EquipmentHistoryForm from './EquipmentHistoryForm.vue'
import { clientToday } from '../../services/common/date'
import EquipmentRecordList from './EquipmentRecordList.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { useTestPlanCache } from '../../services/common/testPlanCache'
import { localPlanSelection } from '../../services/common/localPlanSelection'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { emptyEquipment, equipmentTabs, equipmentHistoryFields, equipmentRecordFields, equipmentAttachmentKinds, type EquipmentDraft, type EquipmentRecord, type EquipmentTab, type EquipmentHistoryKind, type EquipmentHistory, type EquipmentFormOptions, type EquipmentAttachmentKind } from '../../types/quality/equipmentForm'
const props = defineProps<{ mode?: 'new' | 'edit' | 'view'; recordId?: string; initial?: EquipmentDraft }>()
const emit = defineEmits<{ close: []; saved: [record: EquipmentRecord, copy: boolean] }>()
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
const draft = reactive(props.initial ? clone(props.initial) : emptyEquipment())
if (!props.initial) draft.departmentId = currentActor.value.departmentId
const readonly = computed(() => props.mode ? props.mode === 'view' : !!props.recordId), busy = ref(false), loading = ref(false), error = ref<ErrorValue>('')
const version = ref<number>()
const loaded = ref(!props.recordId), optionsReady = ref(false), loadError = ref<ErrorValue>('')
const options = ref<EquipmentFormOptions>({ departments: [], equipmentTypes: [], projects: [] })
const tab = ref<EquipmentTab>('basic'), form = ref<HTMLFormElement>()
const files = ref<EquipmentAttachmentKind>(), choosing = ref(false), keyword = ref(''), search = ref(''), planRevision = ref(0), planExpanded = ref(true), planState = ref<PlanSelectionState>(), planCatalogue = ref<PlanSelectionCatalogue>(), planBusy = ref(false), planError = ref<ErrorValue>('')
const history = ref<{ kind: EquipmentHistoryKind; mode: 'new' | 'view'; row: EquipmentHistory }>()
const cancelButton = ref<HTMLButtonElement>()
const removing = ref<{ tab: Exclude<EquipmentTab, 'basic' | 'reports'>; ids: string[] }>()
const historyLeave = useFormLeaveGuard(() => history.value?.row, () => !!history.value && ['new', 'edit'].includes(history.value.mode), () => busy.value, false)
const uploads = useAttachmentDraft('equipment', () => props.recordId, () => Object.values(draft.profile.attachments).flat(), () => busy.value, { value: () => [draft, historyLeave.dirty.value ? history.value?.row : undefined], ready: () => !readonly.value && loaded.value && !loading.value })
const subscreen = computed(() => !!files.value || !!history.value || choosing.value)
const title = computed(() => files.value ? `${equipmentAttachmentKinds.find(k => k.key === files.value)!.label}附件` : choosing.value ? '选择方案' : history.value ? `${history.value.mode === 'new' ? '新增' : '查看'}${equipmentTabs.find(t => t.key === history.value!.kind)!.label}` : readonly.value ? '查看设备' : props.recordId ? '编辑设备' : '新增设备')
const projectColumns = [{ key: 'code', label: '方案代码' }, { key: 'name', label: '方案名称' }] as const
const reportColumns = [{ key: 'commissionCode', label: '委托编号' }, { key: 'sampleCode', label: '样品编号' }, { key: 'reportCode', label: '报告编号' }, { key: 'project', label: '检测方案' }]
const recordRows = computed<EquipmentHistory[]>(() => tab.value === 'basic' || tab.value === 'reports' ? [] : tab.value === 'projects' ? draft.profile.projects.map(({ id, code, name }) => ({ id, code, name })) : draft.profile[tab.value].map(row => ({ ...row })))
const recordColumns = computed(() => tab.value === 'projects' ? projectColumns : tab.value === 'reports' || tab.value === 'basic' ? reportColumns : equipmentHistoryFields[tab.value].filter(field => tab.value !== 'usage' || field.key !== 'notes'))
let alive = true
const controller = new AbortController()
async function load() {
  if (loading.value) return
  loading.value = true; loadError.value = ''
  try {
    const [available, record] = await Promise.all([registrationDemo.equipmentFormOptions(controller.signal), props.recordId ? registrationDemo.equipmentDetail(props.recordId, controller.signal) : Promise.resolve(undefined)])
    if (!alive) return
    options.value = available; optionsReady.value = true; loaded.value = true
    if (record) { Object.assign(draft, record); version.value = record.version }
  } catch (issue) { if (alive) loadError.value = normalizeError(issue) }
  finally { if (alive) loading.value = false }
}
async function close() {
  if (busy.value) return
  if (files.value) files.value = undefined
  else if (history.value) { if (await historyLeave.allowLeave()) { history.value = undefined; error.value = '' } }
  else if (choosing.value) { choosing.value = false; planSequence++; planController?.abort(); planBusy.value = false }
  else if (removing.value) removing.value = undefined
  else if (readonly.value || (await uploads.allowLeave())) emit('close')
}
function openNew() {
  if (readonly.value || busy.value) return
  error.value = ''
  if (tab.value === 'projects' && !optionsReady.value) return
  if (tab.value === 'projects') { keyword.value = ''; search.value = ''; planRevision.value++; planExpanded.value = true; planState.value = undefined; choosing.value = true; void loadPlans() }
  else if (tab.value !== 'basic' && tab.value !== 'reports') {
    const row = { id: crypto.randomUUID(), ...Object.fromEntries(equipmentRecordFields(tab.value).map(f => [f.key, f.date ? clientToday() : ''])) }
    if (tab.value === 'checks') Object.assign(row, { equipmentDate: draft.lastTestDate || clientToday(), accuracyRequirement: draft.accuracy })
    history.value = { kind: tab.value, mode: 'new', row }
  }
}
const planCache = useTestPlanCache()
let planController: AbortController | undefined, planSequence = 0
async function loadPlans() {
  if (planBusy.value || !choosing.value) return
  const token = ++planSequence, active = planController = new AbortController()
  const cacheRevision = planCache?.revision, cached = planCache?.get<PlanSelectionCatalogue>('selection:equipment')
  const value = { ...emptyPlanSelection(), planIds: draft.profile.projects.map(p => p.id) }
  planError.value = ''
  if (cached) { planCatalogue.value = cached; planState.value = localPlanSelection(cached, value); return }
  planBusy.value = true
  try {
    const result = await registrationDemo.equipmentPlanSelection(value, undefined, active.signal)
    if (alive && choosing.value && token === planSequence) { planCache?.set('selection:equipment', result.catalogue, cacheRevision!); planCatalogue.value = result.catalogue; planState.value = localPlanSelection(result.catalogue, result.selection) }
  } catch (issue) { if (alive && token === planSequence && !active.signal.aborted) planError.value = normalizeError(issue) }
  finally { if (token === planSequence) planBusy.value = false }
}
function togglePlans(toggle: PlanSelectionToggle) {
  if (planState.value && planCatalogue.value && !planBusy.value) planState.value = localPlanSelection(planCatalogue.value, planState.value.selection, toggle)
}
function searchPlans() { search.value = keyword.value.trim(); planExpanded.value = true; planRevision.value++ }
function chooseAllPlans(event: Event) {
  const input = event.target as HTMLInputElement, checked = input.checked
  input.checked = !!planState.value?.total && planState.value.count === planState.value.total
  input.indeterminate = !!planState.value && planState.value.count > 0 && planState.value.count < planState.value.total
  togglePlans({ kind: 'all', id: '', checked })
}
function confirmPlans() {
  if (readonly.value || !optionsReady.value || !planState.value || planBusy.value || planError.value) return
  const selection = planState.value.selection
  draft.profile.projects = options.value.projects.filter(p => selection.groupIds.includes(p.parentId || '') ? !selection.excludedPlanIds.includes(p.id) : selection.planIds.includes(p.id)).map(p => ({ ...p }))
  choosing.value = false
}
function viewHistory(row: EquipmentHistory) { if (tab.value !== 'basic' && tab.value !== 'projects' && tab.value !== 'reports') history.value = { kind: tab.value, mode: 'view', row: { ...Object.fromEntries(equipmentRecordFields(tab.value).map(field => [field.key, ''])), ...clone(row) } } }
function saveHistory() {
  if (!history.value || readonly.value) return
  const { kind, row } = history.value
  if (!equipmentRecordFields(kind).some(f => row[f.key]?.trim())) { error.value = new AppError('VALIDATION', '请至少填写一项记录信息。'); return }
  if (draft.profile[kind].length >= 200) { error.value = new AppError('VALIDATION', '每类设备记录最多 200 条。'); return }
  draft.profile[kind].push(clone(row)); history.value = undefined; error.value = ''
}
function remove() {
  if (!removing.value || readonly.value) return
  const { tab, ids } = removing.value
  if (tab === 'projects') draft.profile.projects = draft.profile.projects.filter(r => !ids.includes(r.id))
  else draft.profile[tab] = draft.profile[tab].filter(r => !ids.includes(r.id))
  removing.value = undefined
}
async function save(copy = false) {
  if (readonly.value || busy.value || loading.value || !loaded.value || !optionsReady.value || uploads.blocked.value || subscreen.value || removing.value) return
  error.value = ''; tab.value = 'basic'; await nextTick()
  if (!form.value?.reportValidity()) return
  busy.value = true
  try {
    const record = await registrationDemo.saveEquipment(uploads.payload({ ...draft, version: version.value }), props.recordId)
    if (alive) { uploads.commit(); emit('saved', record, copy) }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
onBeforeUnmount(() => { alive = false; controller.abort(); planSequence++; planController?.abort() })
void load()
</script>
<template>
  <BootstrapModal :loading="loading || choosing && planBusy" open :title="title" :size="history?.kind === 'checks' ? 'xl' : files || history || choosing ? 'lg' : 'xl'" scrollable fullscreen-mobile :fill-height="choosing" :compact-height="!!files" :busy="busy" guard-close body-class="py-2" @close="close">
    <template v-if="!subscreen" #toolbar><ScrollableTabs v-model="tab" :tabs="equipmentTabs" label="设备资料" id-prefix="equipment" :disabled="busy || !loaded || !!removing" /></template>
    <template v-else-if="choosing" #toolbar><form class="row g-2 align-items-end mb-3" aria-label="检测方案查询" @submit.prevent="searchPlans"><div class="col"><label for="equipment-plan-search" class="form-label">方案名称或代码</label><input id="equipment-plan-search" v-model="keyword" class="form-control" maxlength="200" /></div><div class="col-auto"><button class="btn btn-primary" type="submit">查询</button></div></form></template>
    <PersonnelAttachments v-if="files" :files="draft.profile.attachments[files]" :readonly="readonly" label="设备附件" />
    <template v-else-if="choosing">
      <ErrorNotice :error="planError" retry :busy="planBusy" @retry="loadPlans" />
      <p v-if="!planState && planBusy" class="text-muted py-3 mb-0" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载检测方案…</p>
      <template v-if="planState">
        <div v-if="!search" class="d-flex align-items-center gap-1 mb-2">
          <input class="form-check-input ms-2 mt-0 flex-shrink-0" type="checkbox" aria-label="选择全部检测方案" :checked="!!planState.total && planState.count === planState.total" :indeterminate="planState.count > 0 && planState.count < planState.total" :disabled="planBusy" @change="chooseAllPlans" />
          <button type="button" class="btn text-start d-flex align-items-center gap-2" :aria-expanded="planExpanded" aria-controls="equipment-plan-tree" @click="planExpanded = !planExpanded"><i :class="planExpanded ? 'ti ti-chevron-down' : 'ti ti-chevron-right'" aria-hidden="true"></i><i class="text-warning fs-3" :class="planExpanded ? 'ti ti-folder-open' : 'ti ti-folder'" aria-hidden="true"></i>所有方案</button>
        </div>
        <div v-show="planExpanded" id="equipment-plan-tree"><RegistrationTestPlanBranch :key="planRevision" :query-plans="registrationDemo.equipmentTestPlans" :keyword="search" multiple :selection="planState" :disabled="planBusy" @toggle="togglePlans" /></div>
      </template>
    </template>
    <form v-else-if="history" id="equipment-history-form" class="row g-3" @submit.prevent="saveHistory">
      <EquipmentHistoryForm v-if="history.kind !== 'checks'" :kind="history.kind" :equipment="draft" :record="history.row" :readonly="history.mode === 'view' || readonly || busy" />
      <EquipmentCheckForm v-else :equipment="draft" :record="history.row" :readonly="history.mode === 'view' || readonly || busy" />
    </form>
    <div v-else-if="loading" class="text-center py-4" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载设备信息…</div>
    <template v-else-if="loaded && optionsReady">
      <form v-show="tab === 'basic'" id="equipment-panel-basic" ref="form" role="tabpanel" aria-labelledby="equipment-tab-basic" @submit.prevent="save()"><EquipmentBasicForm :draft="draft" :options="options" :busy="busy" :disabled="readonly || busy" @attachment="files = $event" /></form>
      <div v-if="tab !== 'basic'" :id="`equipment-panel-${tab}`" role="tabpanel" :aria-labelledby="`equipment-tab-${tab}`">
        <div v-if="tab !== 'projects' && tab !== 'reports'" class="row g-2 border-bottom pb-3 mb-3"><div v-for="key in (['code', 'name', 'model', 'serial', 'manufacturer'] as const)" :key="key" class="col-12 col-sm-6 col-lg-4"><span class="text-muted">{{ { code: '档案号', name: '仪器设备名称', model: '规格型号', serial: '仪器出厂号', manufacturer: '生产厂家' }[key] }}：</span><span class="text-break">{{ draft[key] || '—' }}</span></div></div>
        <EquipmentRecordList :create-disabled="tab === 'projects' && !optionsReady" :key="tab" :label="equipmentTabs.find(t => t.key === tab)!.label" :rows="recordRows" :columns="recordColumns" :readonly="readonly" :projects="tab === 'projects'" :reports="tab === 'reports'" :selected-only="tab !== 'projects' && tab !== 'reports'" :busy="busy || !!removing" @new="openNew" @view="viewHistory" @remove="removing = { tab: tab as Exclude<EquipmentTab, 'basic' | 'reports'>, ids: $event }">

        </EquipmentRecordList>
      </div>
    </template>
    <ErrorNotice v-if="!subscreen" :error="loadError" retry :busy="loading" @retry="load" />
    <ErrorNotice :error="error" />
    <AttachmentDraftStatus v-if="!files" />
    <template #footer>
      <span v-if="choosing && planState" class="text-muted me-auto" role="status">已选 {{ planState.count }} 个方案</span>
      <span v-if="busy || uploads.blocked.value" class="text-muted me-auto" role="status">{{ busy ? '正在保存…' : uploads.active.value ? '附件正在上传，请稍候' : '请重试或移除失败的附件后保存' }}</span>
      <button ref="cancelButton" type="button" class="btn btn-light" :disabled="busy" @click="close">{{ history?.mode === 'new' ? '取消' : subscreen || readonly ? '返回' : '取消' }}</button>
      <button v-if="files" type="button" class="btn btn-primary" @click="files = undefined">完成</button>
      <button v-else-if="choosing" type="button" class="btn btn-primary" :disabled="!planState || planBusy || !!planError" @click="confirmPlans">确定</button>
      <button v-else-if="history?.mode === 'new'" class="btn btn-primary" form="equipment-history-form">确认</button>
      <template v-else-if="!readonly && !subscreen"><button v-if="!recordId" type="button" class="btn btn-light" :disabled="busy || loading || !optionsReady || uploads.blocked.value || !options.departments.length" @click="save(true)">保存并复制</button><button type="button" class="btn btn-primary" :disabled="busy || loading || !optionsReady || uploads.blocked.value || !options.departments.length" @click="save()">保存</button></template>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="removing" title="删除设备记录" :busy="busy" @close="removing = undefined">
    <p class="mb-0">确认删除所选 {{ removing.ids.length }} 条{{ equipmentTabs.find(t => t.key === removing!.tab)?.label }}？</p>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="removing = undefined">取消</button><button type="button" class="btn btn-danger" :disabled="busy || readonly" @click="remove">确认删除</button></template>
  </ConfirmationModal>
  <AttachmentLeaveConfirmation />
  <FormLeaveConfirmation :guard="historyLeave" />
</template>
