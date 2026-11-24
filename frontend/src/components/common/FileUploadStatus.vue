<script setup lang="ts">
import type { FileUploadState } from './useFileUpload'
defineProps<{ state?: FileUploadState; leaveAttempted?: boolean }>()
</script>
<template>
  <div v-if="state" class="d-flex align-items-start gap-2 text-primary py-2" role="status" aria-live="polite" aria-atomic="true">
    <span class="spinner-border spinner-border-sm flex-shrink-0 mt-1" aria-hidden="true"></span>
    <div class="text-break"><span>{{ state.phase === 'reading' ? '正在读取' : state.phase === 'saving' ? '正在保存' : '正在上传' }}：{{ state.name }}</span><span v-if="state.total > 1" class="ms-2 text-muted">第 {{ state.index }} / {{ state.total }} 个</span><div v-if="leaveAttempted" class="small text-muted">文件处理尚未完成，请完成后再离开页面。</div></div>
  </div>
</template>
