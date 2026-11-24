<script setup lang="ts">
import ConfirmationModal from '../../components/common/ConfirmationModal.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import type { UploadProgress } from '../../components/common/fileUploadProgress'
import { inject, computed, onBeforeUnmount, ref, watch } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import FileUploadStatus from '../../components/common/FileUploadStatus.vue'
import { useFileUpload } from '../../components/common/useFileUpload'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import RegistrationAttachments from './EntryAttachmentList.vue'
const registrationDemo=inject<any>('platform-entry-services')!
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import type { DemoAttachment, RegistrationCommission, RegistrationAttachmentContext, RegistrationKind } from '../../types/commissions/registration'

const props = withDefaults(defineProps<{ id?: string; kind?: RegistrationKind; readonly?: boolean; title?: string }>(), { kind: 'commissions', title: '附件' })
const emit = defineEmits<{ close: []; changed: [record: Pick<RegistrationCommission, 'id' | 'version'> & { kind: RegistrationKind; attachmentCount: number }] }>()
const record = ref<RegistrationAttachmentContext>(), deleting = ref<DemoAttachment>()
const uploadStatus = useFileUpload()
const deletingBusy = ref(false)
const loading = ref(false), busy = ref(false), stale = ref(false)
const error = ref<ErrorValue>(''), success = ref('')
const successToast = ref<InstanceType<typeof TemplateToast>>()
watch(success, value => { if (value) successToast.value?.show(); else successToast.value?.hide() }, { flush: 'post' })
const canAttach = computed(() => record.value?.canManageAttachments === true && !stale.value && !props.readonly)
const recordLabel = computed(() => props.kind === 'samples' ? '样品' : '委托')
function readRecord(id: string, signal?: AbortSignal) { return registrationDemo.attachments(id, props.kind, signal) }
let epoch = 0, controller: AbortController | undefined, reader: FileReader | undefined
function invalidate() { deletingBusy.value = false; epoch++; controller?.abort(); reader?.abort(); uploadStatus.finish() }
async function load() {
  invalidate(); record.value = undefined; deleting.value = undefined; error.value = ''; success.value = ''; stale.value = false; busy.value = false
  if (!props.id) { loading.value = false; return }
  loading.value = true
  const token = epoch, abort = controller = new AbortController()
  try { const latest = await readRecord(props.id, abort.signal); if (token === epoch) record.value = latest }
  catch (e) { if (token === epoch && !abort.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === epoch) loading.value = false }
}
watch(() => [props.id, props.kind], load, { immediate: true })
watch(currentActor, () => { invalidate(); emit('close') }, { flush: 'sync' })
onBeforeUnmount(invalidate)
function close() { if (!busy.value) { invalidate(); emit('close') } }
function failure(e: unknown) {
  error.value = normalizeError(e)
  // Do not retry a write against an old version, or after an uncertain network result.
  if (['NETWORK', 'UNAVAILABLE', 'FORBIDDEN', 'BUSINESS_RULE', 'NOT_FOUND'].includes(error.value.code)) stale.value = true
}
async function upload(file: File, progress: UploadProgress) {
  const row = record.value
  if (!row || !canAttach.value || busy.value) throw new Error('当前不可上传附件')
  const token = epoch; busy.value = true; uploadStatus.start(file.name); error.value = ''; success.value = ''; deleting.value = undefined
  try {
    if (file.size > 500 * 1024 * 1024) throw new AppError('VALIDATION', '附件不能超过 500 MB。')
    if (token !== epoch) return
    uploadStatus.processing(); progress('uploading')
    const attach = props.kind === 'samples' ? registrationDemo.attachSample : registrationDemo.attach
    const updated = await attach(row.id, row.version, file, 'registration', (loaded: number, total: number) => progress(loaded === total ? 'saving' : 'uploading', loaded === total ? undefined : loaded, loaded === total ? undefined : total))
    if (token === epoch) { record.value = updated; success.value = '附件已上传。'; emit('changed', { kind: props.kind, id: updated.id, version: updated.version, attachmentCount: updated.attachments.length }) }
  } catch (e) { if (token === epoch) failure(e); throw e }
  finally { if (token === epoch) { busy.value = false; uploadStatus.finish(); reader = undefined } }
}
async function remove() {
  const row = record.value, file = deleting.value
  if (!row || !file || !canAttach.value || busy.value) return
  const token = epoch; busy.value = true; deletingBusy.value = true; error.value = ''; success.value = ''
  try {
    const removeAttachment = props.kind === 'samples' ? registrationDemo.deleteSampleAttachment : registrationDemo.deleteAttachment
    const updated = await removeAttachment(row.id, row.version, file.id, 'registration')
    if (token === epoch) { record.value = updated; deleting.value = undefined; success.value = '附件已删除。'; emit('changed', { kind: props.kind, id: updated.id, version: updated.version, attachmentCount: updated.attachments.length }) }
  } catch (e) { if (token === epoch) failure(e) }
  finally { if (token === epoch) { busy.value = false; deletingBusy.value = false } }
}
async function download(file: DemoAttachment) {
  if (!record.value || busy.value) return
  const token = epoch; busy.value = true; error.value = ''; success.value = ''
  try {
    const latest = await readRecord(record.value.id)
    if (token !== epoch) return
    record.value = latest
    const attachment = latest.attachments.find((item: DemoAttachment) => item.id === file.id)
    if (!attachment) throw new AppError('NOT_FOUND', '附件不存在或已不可访问。')
    await registrationDemo.downloadAttachment(attachment)
  } catch (e) { if (token === epoch) failure(e) }
  finally { if (token === epoch) busy.value = false }
}
</script>

<template>
  <BootstrapModal :loading="loading" :open="!!id" :title="title" size="lg" scrollable compact-height body-class="pt-0 pb-2" :busy="busy" @close="close">
    <template #toolbar><TemplateToast ref="successToast" :message="success" tone="success" within-modal /></template>
    <div v-if="loading" class="text-center py-4" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载附件…</div>
    <ErrorNotice v-if="!deleting" :error="error" :retry="!record" :busy="busy || loading" @retry="load" />
    <FeedbackNotice v-if="stale" message="请刷新附件，核对最新内容后再操作。">请刷新附件，核对最新内容后再操作。<button type="button" class="btn btn-sm btn-light ms-2" :disabled="busy" @click="load">刷新附件</button></FeedbackNotice>
    <template v-if="record">
      <p class="text-break mb-2"><span class="fw-medium">{{ record.code }}</span><span class="text-muted ms-2">{{ record.name }}</span></p>
      <p v-if="readonly || !record.canManageAttachments" class="text-muted mb-2">当前{{ recordLabel }}仅支持查看和下载附件。</p>
      <FileUploadStatus :state="uploadStatus.state.value" :leave-attempted="uploadStatus.leaveAttempted.value" />
      <RegistrationAttachments fill-empty :kind="kind" :files="record.attachments" :can-attach="canAttach" :busy="busy" :upload="upload" @download="download" @remove="deleting = $event; success = ''; error = ''" />
    </template>
    <template #footer>
      <span v-if="busy && !uploadStatus.active.value" class="text-muted me-auto" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在处理…</span>
      <button type="button" class="btn btn-light" :disabled="busy" @click="close">关闭</button>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="deleting" title="删除附件" :busy="busy" @close="deleting = undefined">
    <p class="text-break">确认删除附件“{{ deleting.name }}”？</p>
    <ErrorNotice :error="error" />
    <button v-if="stale" type="button" class="btn btn-light" :disabled="busy" @click="load">刷新附件</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="deleting = undefined">取消</button><button type="button" class="btn btn-danger" :disabled="busy || !canAttach" @click="remove">{{ deletingBusy ? '正在删除…' : '确认删除' }}</button></template>
  </ConfirmationModal>
</template>


