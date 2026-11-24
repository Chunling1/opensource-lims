<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateEditableSelect from '../common/TemplateEditableSelect.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import LoadState from '../common/LoadState.vue'
import AttachmentDraftStatus from '../common/AttachmentDraftStatus.vue'
import AttachmentLeaveConfirmation from '../common/AttachmentLeaveConfirmation.vue'
import { useAttachmentDraft } from '../common/useAttachmentDraft'
import CertificateAttachments from './CertificateAttachments.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import type { DemoAttachment } from '../../types/commissions/registration'
const props = defineProps<{
  kind: 'certificate' | 'project'; mode: 'new' | 'edit'; owner: string; ownerId: string; ownerIds?: string[]
  record?: Record<string, string>; categories: string[]
}>()
const emit = defineEmits<{ close: []; saved: [count: number] }>()
const draft = reactive({ category: '', number: '', code: '', item: '', notes: '' })
const files = ref<DemoAttachment[]>([])
const attachmentsOpen = ref(false), saving = ref(false), loading = ref(false), loaded = ref(props.mode === 'new'), error = ref<ErrorValue>('')
const version = ref<number>()
const uploads = useAttachmentDraft('certificate', () => props.kind === 'certificate' ? props.record?.id : undefined, () => files.value, () => saving.value, { value: () => draft, ready: () => loaded.value && !loading.value })
const title = computed(() => attachmentsOpen.value ? '上岗证附件' : `${props.mode === 'new' ? '新增' : '编辑'}${props.kind === 'certificate' ? '上岗证' : '核准检测项目'}`)
const formId = 'certificate-edit-form'
let alive = true, controller: AbortController | undefined
async function close() { if (saving.value) return; if (attachmentsOpen.value) attachmentsOpen.value = false; else if ((await uploads.allowLeave())) emit('close') }
async function load() {
  if (!props.record?.id) return
  controller?.abort(); const active = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false
  try {
    const row = props.kind === 'certificate' ? await registrationDemo.certificateDetail(props.record.id, active.signal) : await registrationDemo.approvedProjectDetail(props.record.id, active.signal)
    if (!alive || active.signal.aborted) return
    for (const key of Object.keys(draft) as (keyof typeof draft)[]) draft[key] = key in row ? String(row[key as keyof typeof row] ?? '') : ''
    version.value = row.version
    files.value = 'files' in row ? row.files : []; loaded.value = true
  } catch (issue) { if (alive && !active.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !active.signal.aborted) loading.value = false }
}
async function save() {
  if (saving.value || loading.value || !loaded.value || uploads.blocked.value) return
  const values = Object.fromEntries(Object.entries(draft).filter(([, value]) => typeof value === 'string').map(([key, value]) => [key, value.trim()]))
  if (props.kind === 'certificate' ? !values.category || !values.number : !values.code || !values.item) { error.value = new AppError('VALIDATION', '请填写完整的必填信息。', { fieldErrors: Object.fromEntries((props.kind === 'certificate' ? ['category', 'number'] : ['code', 'item']).filter(key => !values[key]).map(key => [key, '请填写此项。'])) }); return }
  saving.value = true; error.value = ''
  try {
    let count = 1
    if (props.kind === 'certificate') await registrationDemo.saveCertificate(uploads.payload({ ...values, personId: props.ownerId, version: version.value, files: files.value }), props.record?.id)
    else count = (await registrationDemo.saveApprovedProjects({ ...values, version: version.value, certificateIds: props.ownerIds || [props.ownerId] }, props.record?.id)).count
    if (alive) { uploads.commit(); emit('saved', count) }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) saving.value = false }
}
onBeforeUnmount(() => { alive = false; controller?.abort() })
void load()
</script>

<template>
  <BootstrapModal :loading="loading" open :title="title" size="lg" scrollable fullscreen-mobile body-class="py-2" :compact-height="attachmentsOpen" :busy="saving" guard-close @close="close">
    <CertificateAttachments v-if="attachmentsOpen" :files="files" />
    <LoadState v-else-if="loading" loading />
    <template v-else-if="loaded">
      <p class="text-muted small mb-3 text-break">{{ kind === 'certificate' ? '所属人员' : '所属上岗证' }}：{{ owner }}</p>
      <form :id="formId" @submit.prevent="save"><fieldset class="vstack gap-3" :disabled="saving">
        <template v-if="kind === 'certificate'">
          <div class="row g-2 align-items-start"><label for="certificate-category" class="col-12 col-sm-auto col-form-label w-auto">上岗证类别<span class="text-danger ms-1" aria-hidden="true">*</span></label><div class="col"><TemplateEditableSelect id="certificate-category" data-validation-key="category" v-model="draft.category" label="上岗证类别" :options="categories" :readonly="saving" placeholder="请选择或输入" required :maxlength="100" /></div></div>
          <div class="row g-2 align-items-start"><label for="certificate-number" class="col-12 col-sm-auto col-form-label w-auto">上岗证号<span class="text-danger ms-1" aria-hidden="true">*</span></label><div class="col"><input id="certificate-number" data-validation-key="number" v-model="draft.number" class="form-control" required maxlength="100" /></div></div>
          <div class="row g-2 align-items-start"><span id="certificate-files-label" class="col-12 col-sm-auto col-form-label w-auto">上传附件</span><div class="col"><div class="d-flex align-items-center gap-2"><span class="text-muted">{{ files.length }} 个附件</span><button type="button" class="btn btn-light" aria-label="管理上岗证附件" @click="attachmentsOpen = true">浏览</button></div></div></div>
        </template>
        <template v-else>
          <div class="row g-2 align-items-start"><label for="approved-code" class="col-12 col-sm-auto col-form-label w-auto">核准项目代码<span class="text-danger ms-1" aria-hidden="true">*</span></label><div class="col"><input id="approved-code" data-validation-key="code" v-model="draft.code" class="form-control" required maxlength="100" /></div></div>
          <div class="row g-2 align-items-start"><label for="approved-item" class="col-12 col-sm-auto col-form-label w-auto">核准检测项目<span class="text-danger ms-1" aria-hidden="true">*</span></label><div class="col"><input id="approved-item" data-validation-key="item" v-model="draft.item" class="form-control" required maxlength="200" /></div></div>
          <div class="row g-2 align-items-start"><label for="approved-category" class="col-12 col-sm-auto col-form-label w-auto">类别</label><div class="col"><TemplateEditableSelect id="approved-category" data-validation-key="category" v-model="draft.category" label="类别" :options="categories" :readonly="saving" placeholder="请选择或输入" :maxlength="100" /></div></div>
        </template>
        <div class="row g-2 align-items-start"><label for="certificate-notes" class="col-12 col-sm-auto col-form-label w-auto">备注</label><div class="col"><textarea id="certificate-notes" data-validation-key="notes" v-model="draft.notes" class="form-control" rows="4" maxlength="2000"></textarea></div></div>
      </fieldset></form>
    </template>
    <ErrorNotice :error="error" :retry="!loaded && !loading" @retry="load" />
    <AttachmentDraftStatus v-if="!attachmentsOpen" :files="files" />
    <template #footer>
      <span v-if="uploads.blocked.value && !attachmentsOpen" class="me-auto text-muted" role="status">{{ uploads.active.value ? '附件正在上传，请稍候' : '请重试或移除失败的附件后保存' }}</span>
      <template v-if="attachmentsOpen"><button type="button" class="btn btn-light" :disabled="saving" @click="close">返回</button><button type="button" class="btn btn-primary" :disabled="saving" @click="close">完成</button></template>
      <template v-else><button type="button" class="btn btn-light" :disabled="saving" @click="close">取消</button><button type="submit" class="btn btn-primary" :form="formId" :disabled="saving || loading || !loaded || uploads.blocked.value">{{ saving ? '正在保存…' : '保存' }}</button></template>
    </template>
  </BootstrapModal>
  <AttachmentLeaveConfirmation />
</template>
