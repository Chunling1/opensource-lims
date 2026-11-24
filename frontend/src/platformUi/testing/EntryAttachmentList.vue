<script setup lang="ts">
import FilePondUpload from '../../components/common/FilePondUpload.vue'
import AttachmentFileList from '../../components/common/AttachmentFileList.vue'
import type { AttachmentUploader } from '../../components/common/fileUploadProgress'
import type { DemoAttachment, RegistrationKind } from '../../types/commissions/registration'
withDefaults(defineProps<{ files: DemoAttachment[]; canAttach: boolean; busy: boolean; upload: AttachmentUploader; local?: boolean; kind?: RegistrationKind; label?: string; fillEmpty?: boolean; uploadRevision?: number }>(), { kind: 'commissions' })
defineEmits<{ download: [DemoAttachment]; remove: [DemoAttachment]; discard: [File] }>()
</script>
<template>
  <section :aria-label="label || (kind === 'samples' ? '样品附件' : '委托附件')" :inert="busy" :aria-busy="busy">
    <FilePondUpload v-if="canAttach" :key="uploadRevision" @discard="$emit('discard', $event)" :upload="upload" :disabled="busy" :local="local" accept=".pdf,.docx,.png,.jpg,.jpeg" :max-size="500 * 1024 * 1024" />
    <AttachmentFileList :files="files" :can-attach="canAttach" :busy="busy" :fill-empty="fillEmpty" @download="$emit('download', $event)" @remove="$emit('remove', $event)" />
  </section>
</template>
