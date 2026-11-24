<script setup lang="ts">
import FilePondUpload from '../common/FilePondUpload.vue'
import AttachmentFileList from '../common/AttachmentFileList.vue'
import type { AttachmentUploader } from '../common/fileUploadProgress'
import type { DemoAttachment, RegistrationKind } from '../../types/commissions/registration'
withDefaults(defineProps<{ files: DemoAttachment[]; canAttach: boolean; busy: boolean; upload: AttachmentUploader; local?: boolean; kind?: RegistrationKind; label?: string; fillEmpty?: boolean; uploadRevision?: number }>(), { kind: 'commissions' })
defineEmits<{ download: [DemoAttachment]; remove: [DemoAttachment]; discard: [File] }>()
</script>
<template>
  <section :aria-label="label || (kind === 'samples' ? '样品附件' : '委托附件')" :inert="busy" :aria-busy="busy">
    <FilePondUpload v-if="canAttach" :key="uploadRevision" @discard="$emit('discard', $event)" :upload="upload" :disabled="busy" :local="local" />
    <AttachmentFileList :files="files" :can-attach="canAttach" :busy="busy" :fill-empty="fillEmpty" @download="$emit('download', $event)" @remove="$emit('remove', $event)" />
  </section>
</template>
