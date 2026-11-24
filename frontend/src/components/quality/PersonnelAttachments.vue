<script setup lang="ts">
import { ref } from 'vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import type { UploadProgress } from '../common/fileUploadProgress'
import type { DemoAttachment } from '../../types/commissions/registration'
import RegistrationAttachments from '../commissions/RegistrationAttachments.vue'
import AttachmentDraftStatus from '../common/AttachmentDraftStatus.vue'
import { useFormAttachments } from '../common/useAttachmentDraft'
const props = withDefaults(defineProps<{ files: DemoAttachment[]; readonly: boolean; label?: string }>(), { label: '人员附件' })
const uploads = useFormAttachments(), busy = ref(false), uploadRevision = ref(0), error = ref('')
const deleting = ref<DemoAttachment>()
function requestRemove(file: DemoAttachment) {
  if (props.readonly || busy.value || uploads.active.value) return
  error.value = ''; deleting.value = file
}
function cancelRemove() { if (!busy.value) { deleting.value = undefined; error.value = '' } }
async function upload(file: File, progress: UploadProgress) {
  if (props.readonly || busy.value) throw new Error('当前不可上传附件')
  busy.value = true
  try { await uploads.upload(file, props.files, progress) } finally { busy.value = false }
}
async function action(file: DemoAttachment, remove = false) {
  if (busy.value || uploads.active.value || remove && props.readonly) return
  busy.value = true
  error.value = ''
  try { if (remove) { await uploads.remove(file, props.files); deleting.value = undefined } else await uploads.download(file) }
  catch (issue) { error.value = issue instanceof Error ? issue.message : '附件操作失败，请重试。' }
  finally { busy.value = false }
}
</script>
<template>
  <RegistrationAttachments fill-empty :label="label" :upload-revision="uploadRevision" @discard="uploads.dismissFailed($event, files)" :files="files" :can-attach="!readonly" :busy="busy || uploads.active.value" :upload="upload" @download="action($event)" @remove="requestRemove" />
  <AttachmentDraftStatus v-if="!busy" @reset="uploadRevision++" :files="files" />
  <div v-if="error && !deleting" class="invalid-feedback d-block mt-3" role="alert">{{ error }}</div>
  <ConfirmationModal v-if="deleting" title="删除附件" :busy="busy" @close="cancelRemove">
    <p class="text-break">确认删除附件“{{ deleting.name }}”？</p>
    <div v-if="error" class="invalid-feedback d-block" role="alert">{{ error }}</div>
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="cancelRemove">取消</button>
      <button type="button" class="btn btn-danger" :disabled="busy || readonly" @click="action(deleting, true)">{{ busy ? '正在删除…' : '确认删除' }}</button>
    </template>
  </ConfirmationModal>
</template>
