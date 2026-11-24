<script setup lang="ts">
import ConfirmationModal from './ConfirmationModal.vue'
import { useFormAttachments } from './useAttachmentDraft'
const uploads = useFormAttachments()
</script>
<template>
  <ConfirmationModal v-if="uploads.leaveRequested.value" title="放弃未保存内容" @close="uploads.finishLeave(false)">
    <p class="mb-0">{{ uploads.active.value ? '附件正在处理，离开将取消上传并放弃未保存内容。确定离开？' : '内容尚未保存，离开将放弃未保存内容。确定离开？' }}</p>
    <template #footer>
      <button type="button" class="btn btn-light" @click="uploads.finishLeave(false)">继续编辑</button>
      <button type="button" class="btn btn-danger" @click="uploads.finishLeave(true)">放弃更改</button>
    </template>
  </ConfirmationModal>
</template>
