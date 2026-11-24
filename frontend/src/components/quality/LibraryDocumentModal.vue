<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import PersonnelAttachments from './PersonnelAttachments.vue'
import AttachmentLeaveConfirmation from '../common/AttachmentLeaveConfirmation.vue'
import { useAttachmentDraft } from '../common/useAttachmentDraft'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import { canManageDocuments, type DocumentModule, type LibraryDocumentRow, type LibraryDocumentDraft } from '../../types/quality/documentLibrary'
import type { DemoAttachment } from '../../types/commissions/registration'
const props = withDefaults(defineProps<{ documentModule?: DocumentModule; mode: 'new' | 'edit' | 'view' | 'delete' | 'issue' | 'recover' | 'files'; row?: LibraryDocumentRow }>(), { documentModule: 'library' })
const emit = defineEmits<{ close: []; saved: [] }>()
const draft = reactive<LibraryDocumentDraft>({ code: '', name: '', category: '', quantity: 0, notes: '' }), files = ref<DemoAttachment[]>([]), record = ref(props.row)
const movement = reactive({ quantity: 1, date: clientToday(), person: currentActor.value.name })
const loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>('')
const uploads = useAttachmentDraft(props.documentModule === 'monitoring' ? 'monitoring-document' : 'document', () => props.row?.id, () => files.value, () => busy.value, { value: () => [draft, movement], ready: () => ['new', 'edit', 'issue', 'recover'].includes(props.mode) && loaded.value && !loading.value })
const readonly = computed(() => props.mode === 'view' || !canManageDocuments(currentActor.value) || busy.value)
const isMovement = props.mode === 'issue' || props.mode === 'recover'
const subject = props.documentModule === 'monitoring' ? '质量监控计划' : '文件基础信息'
const movementSubject = props.documentModule === 'monitoring' ? '质量监控计划' : '文件'
const title = computed(() => ({ new: `新增${subject}`, edit: `编辑${subject}`, view: `查看${subject}`, delete: `删除${subject}`, issue: `${movementSubject}领用登记`, recover: `${movementSubject}回收登记`, files: '附件管理' })[props.mode])
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.row || busy.value || !(await uploads.allowLeave())) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; loaded.value = false; error.value = ''
  try {
    const row = await registrationDemo.libraryDocumentDetail(props.row.id, request.signal, props.documentModule)
    if (alive && !request.signal.aborted) { record.value = row; Object.assign(draft, row); files.value = row.files; loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function close() { if (!busy.value && (await uploads.allowLeave())) emit('close') }
async function save() {
  if (readonly.value || loading.value || !loaded.value || uploads.blocked.value) return
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteLibraryDocument(record.value!.id, record.value!.version, props.documentModule)
    else if (props.mode === 'issue' || props.mode === 'recover') await registrationDemo.documentMovement(props.mode, { id: record.value!.id, version: record.value!.version, ...movement }, props.documentModule)
    else if (props.mode === 'files') await registrationDemo.saveLibraryDocumentFiles(uploads.payload({ id: record.value!.id, version: record.value!.version, files: files.value }), props.documentModule)
    else await registrationDemo.saveLibraryDocument({ ...draft, ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) }, props.documentModule)
    if (alive) { uploads.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (!loaded.value) void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal open :title="title" :size="mode === 'delete' ? undefined : 'lg'" :busy="busy" :loading="loading" :guard-close="true" :compact-height="mode === 'files'" :fullscreen-mobile="mode === 'files'" :body-class="mode === 'files' ? 'py-2' : undefined" scrollable @close="close">
    <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除文件“{{ record?.code }} · {{ record?.name }}”？</p>
    <template v-else-if="mode === 'files' && loaded">
      <p class="text-muted text-break">{{ record?.code }} · {{ record?.name }}</p>
      <PersonnelAttachments :files="files" :readonly="readonly" label="文件附件" />
    </template>
    <form v-else-if="loaded" id="library-document-form" @submit.prevent="save">
      <fieldset :disabled="readonly" class="row g-3">
        <template v-if="isMovement">
          <div class="col-12"><label for="document-target" class="form-label">文件</label><input id="document-target" :value="`${record?.code} · ${record?.name}`" class="form-control bg-light" readonly /></div>
          <div class="col-12 col-md-6"><label for="document-move-quantity" class="form-label">{{ mode === 'issue' ? '领用数量' : '回收数量' }}<span class="text-danger ms-1" aria-hidden="true">*</span></label><input id="document-move-quantity" v-model.number="movement.quantity" data-validation-key="quantity" type="number" min="1" :max="mode === 'issue' ? record?.remaining : record?.outstanding" step="1" class="form-control" required /><div class="form-text">{{ mode === 'issue' ? `剩余 ${record?.remaining} 份` : `未回收 ${record?.outstanding} 份` }}</div></div>
          <div class="col-12 col-md-6"><label for="document-move-date" class="form-label">登记日期<span class="text-danger ms-1" aria-hidden="true">*</span></label><TemplateDate id="document-move-date" v-model="movement.date" data-validation-key="date" required within-modal :disabled="readonly" /></div>
          <div class="col-12 col-md-6"><label for="document-person" class="form-label">{{ mode === 'issue' ? '领用人' : '回收人' }}<span class="text-danger ms-1" aria-hidden="true">*</span></label><input id="document-person" v-model="movement.person" data-validation-key="person" class="form-control" maxlength="200" required /></div>
        </template>
        <template v-else>
          <div v-for="field in [{ key: 'code', label: '文件编号', required: true }, { key: 'category', label: '文件分类', required: false }, { key: 'name', label: '文件名称', required: true }] as const" :key="field.key" :class="field.key === 'name' ? 'col-12' : 'col-12 col-md-6'"><label :for="`document-${field.key}`" class="form-label">{{ field.label }}<span v-if="field.required && mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><input :id="`document-${field.key}`" v-model="draft[field.key]" :data-validation-key="field.key" class="form-control" :required="field.required" maxlength="200" /></div>
          <div class="col-12 col-md-6"><label for="document-quantity" class="form-label">数量<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><input id="document-quantity" v-model.number="draft.quantity" data-validation-key="quantity" class="form-control" type="number" :min="record?.outstanding || 0" max="1000000" step="1" required /><div v-if="mode !== 'new'" class="form-text">总数量；目前未回收 {{ record?.outstanding }} 份。</div></div>
          <div v-if="mode !== 'new'" class="col-12 col-md-6"><label for="document-remaining" class="form-label">剩余数量</label><input id="document-remaining" :value="draft.quantity - (record?.outstanding || 0)" class="form-control bg-light" readonly /></div>
          <div class="col-12"><label for="document-notes" class="form-label">备注</label><textarea id="document-notes" v-model="draft.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="2000"></textarea></div>
        </template>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!loaded" :busy="busy || loading" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ mode === 'view' || !canManageDocuments(currentActor) ? '返回' : '取消' }}</button>
      <button v-if="mode !== 'view' && canManageDocuments(currentActor)" :type="mode === 'delete' || mode === 'files' ? 'button' : 'submit'" :form="mode === 'delete' || mode === 'files' ? undefined : 'library-document-form'" class="btn" :class="mode === 'delete' ? 'btn-danger' : 'btn-primary'" :disabled="readonly || loading || !loaded || uploads.blocked.value" @click="(mode === 'delete' || mode === 'files') && save()">{{ busy ? '正在保存…' : mode === 'delete' ? '确认删除' : isMovement ? '确认登记' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <AttachmentLeaveConfirmation />
</template>
