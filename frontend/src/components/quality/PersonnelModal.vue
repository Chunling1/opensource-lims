<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ScrollableTabs from '../common/ScrollableTabs.vue'
import TemplateDate from '../common/TemplateDate.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import SaveProgress from '../common/SaveProgress.vue'
import { useSaveProgress } from '../common/useSaveProgress'
import DataEntryPersonPicker from '../testing/DataEntryPersonPicker.vue'
import PersonnelBasicForm from './PersonnelBasicForm.vue'
import PersonnelHistoryList from './PersonnelHistoryList.vue'
import PersonnelAttachments from './PersonnelAttachments.vue'
import AttachmentLeaveConfirmation from '../common/AttachmentLeaveConfirmation.vue'
import { useAttachmentDraft } from '../common/useAttachmentDraft'
import AttachmentDraftStatus from '../common/AttachmentDraftStatus.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyPersonnel, emptyPersonnelProfile, personnelAttachmentKinds, type PersonnelRecord, type PersonnelDraft, type PersonnelProfile, type PersonnelHistory, type PersonnelAttachmentKind } from '../../types/quality/personnel'
import type { DemoAttachment } from '../../types/commissions/registration'
import type { EntryPersonCandidate } from '../../types/testing/dataEntryDetail'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { clientToday } from '../../services/common/date'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'delete'; record?: PersonnelRecord }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { active: saving, percent: savePercent, start: startSave, finish: finishSave } = useSaveProgress()
const draft = reactive<PersonnelDraft & { profile: PersonnelProfile }>({ ...emptyPersonnel(), profile: emptyPersonnelProfile() }), version = ref(props.record?.version)
const loading = ref(false), busy = ref(false), error = ref<ErrorValue>(''), loaded = ref(!props.record), picker = ref(false)
type HistoryKind = 'awards' | 'trainings'
const tab = ref<'basic' | HistoryKind>('basic'), tabs = [{ key: 'basic', label: '基本信息' }, { key: 'awards', label: '获奖信息' }, { key: 'trainings', label: '继续教育记录' }] as const
const history = ref<{ kind: HistoryKind; mode: 'new' | 'edit' | 'view' | 'delete'; row: PersonnelHistory }>()
const deleting = ref<{ kind: HistoryKind; mode: 'delete'; row: PersonnelHistory }>()
const files = ref<{ title: string; items: DemoAttachment[] }>()
const historyLeave = useFormLeaveGuard(() => history.value?.row, () => !!history.value && ['new', 'edit'].includes(history.value.mode), () => busy.value, false)
const uploads = useAttachmentDraft('personnel', () => props.record?.id, () => [...Object.values(draft.profile.attachments).flat(), ...draft.profile.awards.flatMap(row => row.attachments), ...draft.profile.trainings.flatMap(row => row.attachments), ...(history.value?.row.attachments || [])], () => busy.value, { value: () => [draft, historyLeave.dirty.value ? history.value?.row : undefined], ready: () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value })
const form = ref<HTMLFormElement>()
const readonly = computed(() => props.mode === 'view' || !loaded.value)
const subscreen = computed(() => !!history.value || !!files.value || picker.value)
const title = computed(() => picker.value ? '选择人员' : files.value ? files.value.title : history.value ? ({ new: '新增', edit: '修改', view: '查看', delete: '删除' })[history.value.mode] + (history.value.kind === 'awards' ? '获奖情况' : '继续教育记录') : ({ new: '新增人员', edit: '编辑人员', view: '查看人员', delete: '删除人员' })[props.mode])
const historyFields = computed(() => history.value?.kind === 'awards' ? [{ key: 'name', label: '获奖名称', required: true }, { key: 'project', label: '获奖项目' }, { key: 'date', label: '获奖日期', required: true }, { key: 'issuer', label: '颁奖单位' }] as const : [{ key: 'date', label: '培训时间', required: true }, { key: 'place', label: '培训地点' }, { key: 'content', label: '培训内容', required: true }, { key: 'result', label: '培训结果' }] as const)
draft.department = registrationDepartments.find(d => d.id === currentActor.value.departmentId)?.name || ''
draft.gender = '男'; draft.joinedAt = clientToday()
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T
let alive = true
const controller = new AbortController()
async function load() {
  if (!props.record) return
  loading.value = true; error.value = ''
  try { const row = await registrationDemo.personnelDetail(props.record.id, controller.signal); if (alive) { Object.assign(draft, row, { profile: { ...emptyPersonnelProfile(), ...row.profile } }); version.value = row.version; loaded.value = true } }
  catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) loading.value = false }
}
async function close() {
  if (busy.value) return
  if (picker.value) { picker.value = false; await nextTick(); document.getElementById('personnel-select-name')?.focus() }
  else if (files.value) files.value = undefined
  else if (history.value) { if (await historyLeave.allowLeave()) history.value = undefined }
  else if ((await uploads.allowLeave())) emit('close')
}
async function selectPerson(person: EntryPersonCandidate) { draft.name = person.name; draft.profile.accountId = person.id; await close(); await nextTick(); document.getElementById('personnel-name')?.dispatchEvent(new Event('change', { bubbles: true })) }
async function openPicker() { picker.value = true; await nextTick(); document.getElementById('personnel-user-account')?.focus() }
function openHistory(kind: HistoryKind, mode: 'new' | 'edit' | 'view' | 'delete' | 'attachments', row?: PersonnelHistory) {
  if (uploads.blocked.value && ['new', 'edit', 'delete'].includes(mode)) return
  if (mode === 'attachments' && row) { openFiles('附件管理', row.attachments); return }
  if (mode === 'attachments') return
  if (mode === 'delete' && row) { error.value = ''; deleting.value = { kind, mode, row: copy(row) }; return }
  history.value = { kind, mode, row: row ? copy(row) : { id: crypto.randomUUID(), date: clientToday(), name: '', project: '', issuer: '', place: '', content: '', result: '', attachments: [] } }
}
async function saveHistory() {
  const h = deleting.value || history.value
  if (!h || readonly.value || h.mode === 'view' || uploads.blocked.value) return
  const rows = draft.profile[h.kind], index = rows.findIndex(r => r.id === h.row.id)
  if (h.mode === 'delete') {
    busy.value = true
    try {
      if (index >= 0) {
        for (const file of [...rows[index]!.attachments]) if (!file.dataUrl) await uploads.remove(file, rows[index]!.attachments)
        rows.splice(index, 1)
      }
    } catch (issue) { error.value = normalizeError(issue); return }
    finally { busy.value = false }
  }
  else if (index >= 0) rows[index] = copy(h.row)
  else rows.push(copy(h.row))
  history.value = undefined; deleting.value = undefined
}
function openFiles(label: string, target: DemoAttachment[]) {
  files.value = { title: label, items: target }
}
function basicFiles(kind: PersonnelAttachmentKind) { openFiles(personnelAttachmentKinds.find(f => f.key === kind)!.label, draft.profile.attachments[kind]) }
function saveFiles() { files.value = undefined }
async function save() {
  if (busy.value || loading.value || readonly.value || subscreen.value || uploads.blocked.value || props.mode === 'delete' && error.value) return
  if (props.mode !== 'delete') { tab.value = 'basic'; await nextTick(); if (!form.value?.reportValidity()) return }
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete' && props.record) await registrationDemo.deletePersonnel(props.record.id, version.value!)
    else await registrationDemo.savePersonnel(uploads.payload({ ...draft, version: version.value }), props.record?.id, startSave())
    if (alive) { uploads.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { finishSave(); if (alive) busy.value = false }
}
onBeforeUnmount(() => { alive = false; controller.abort() })
if (props.mode === 'delete' && props.record) {
  Object.assign(draft, props.record, { profile: { ...emptyPersonnelProfile(), ...props.record.profile } })
  loaded.value = true
} else void load()
</script>
<template>
  <BootstrapModal :loading="loading && mode !== 'delete'" open :title="title" :size="mode === 'delete' ? undefined : subscreen && !picker ? 'lg' : 'xl'" scrollable :fullscreen-mobile="mode !== 'delete'" :fill-height="picker" :compact-height="!!files" :busy="busy" :guard-close="true" :body-class="picker ? 'p-0 overflow-hidden' : 'py-2'" @close="close">
    <template v-if="!subscreen && mode !== 'delete'" #toolbar><ScrollableTabs v-model="tab" :tabs="tabs" label="人员资料" id-prefix="personnel" :disabled="busy || loading || !loaded" /></template>
    <DataEntryPersonPicker v-if="picker" embedded title="选择人员" purpose="personnel" sample-id="" role="tester" :value="draft.profile.accountId ? { id: draft.profile.accountId, name: draft.name } : undefined" @close="close" @select="selectPerson" />
    <PersonnelAttachments v-else-if="files" :files="files.items" :readonly="readonly" />
    <form v-else-if="history" id="personnel-history-form" @submit.prevent="saveHistory">
      <p v-if="history.mode === 'delete'">确认删除{{ history.kind === 'awards' ? history.row.name : history.row.content }}？</p>
      <fieldset v-else :disabled="history.mode === 'view' || readonly" class="vstack gap-3"><div v-for="f in historyFields" :key="f.key" class="row g-2 align-items-center"><label :for="'history-' + f.key" class="col-12 col-sm-3 col-form-label">{{ f.label }}</label><div class="col"><TemplateDate v-if="f.key === 'date'" :id="'history-' + f.key" v-model="history.row.date" :required="'required' in f && f.required" :disabled="history.mode === 'view' || readonly || busy" within-modal /><input v-else :id="'history-' + f.key" v-model="history.row[f.key]" type="text" class="form-control" :required="'required' in f && f.required" maxlength="1000" /></div></div></fieldset>
    </form>
    <div v-else-if="loading && mode !== 'delete'" class="text-center py-4" role="status">正在加载人员信息…</div>
    <template v-else-if="loaded">
      <p v-if="mode === 'delete'">确认删除 {{ draft.name }}（{{ draft.code }}）？</p>
      <template v-else>
        <form v-show="tab === 'basic'" id="personnel-panel-basic" ref="form" role="tabpanel" aria-labelledby="personnel-tab-basic" @submit.prevent="save"><PersonnelBasicForm :draft="draft" :readonly="readonly" :busy="busy" @person="openPicker" @attachment="basicFiles" /></form>
        <div v-for="kind in (['awards', 'trainings'] as const)" v-show="tab === kind" :id="'personnel-panel-' + kind" :key="kind" role="tabpanel" :aria-labelledby="'personnel-tab-' + kind"><PersonnelHistoryList :kind="kind" :rows="draft.profile[kind]" :readonly="readonly" :busy="busy || uploads.blocked.value" @open="(mode, row) => openHistory(kind, mode, row)" /></div>
      </template>
      <p v-if="mode === 'delete' && loading" class="text-muted small" role="status">正在核对最新信息…</p>
      <ErrorNotice v-if="!deleting" :error="error" :retry="mode === 'delete'" :busy="loading || busy" @retry="load" />
    </template>
    <ErrorNotice v-if="!loaded && !loading" :error="error" retry @retry="load" />
    <ErrorNotice v-if="history && error" :error="error" />
    <AttachmentDraftStatus v-if="!files && !picker && (tab !== 'basic' || history)" />
    <template v-if="!picker" #footer>
      <span v-if="uploads.blocked.value && !files" class="me-auto text-muted" role="status">{{ uploads.active.value ? '附件正在上传，请稍候' : '请重试或移除失败的附件后保存' }}</span>
      <SaveProgress :active="saving" :percent="savePercent" />
      <button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ readonly || history?.mode === 'view' ? '关闭' : files ? '返回' : '取消' }}</button>
      <button v-if="files && !readonly" type="button" class="btn btn-primary" :disabled="busy" @click="saveFiles">完成</button>
      <button v-else-if="history && history.mode !== 'view' && !readonly" class="btn" :class="history.mode === 'delete' ? 'btn-danger' : 'btn-primary'" :disabled="busy || uploads.blocked.value" form="personnel-history-form">{{ busy && history.mode === 'delete' ? '正在删除…' : history.mode === 'delete' ? '删除' : '保存' }}</button>
      <button v-else-if="!subscreen && mode !== 'view'" type="button" class="btn" :class="mode === 'delete' ? 'btn-danger' : 'btn-primary'" :disabled="busy || loading || !loaded || uploads.blocked.value || mode === 'delete' && !!error" @click="save">{{ busy ? mode === 'delete' ? '正在删除…' : '正在保存…' : mode === 'delete' ? '删除' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="deleting" :title="deleting.kind === 'awards' ? '删除获奖情况' : '删除继续教育记录'" :busy="busy" @close="deleting = undefined">
    <p class="text-break">确认删除{{ deleting.kind === 'awards' ? deleting.row.name : deleting.row.content }}？</p><ErrorNotice :error="error" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="deleting = undefined">取消</button><button type="button" class="btn btn-danger" :disabled="busy || readonly || uploads.blocked.value" @click="saveHistory">{{ busy ? '正在删除…' : '确认删除' }}</button></template>
  </ConfirmationModal>
  <AttachmentLeaveConfirmation />
  <FormLeaveConfirmation :guard="historyLeave" />
</template>
