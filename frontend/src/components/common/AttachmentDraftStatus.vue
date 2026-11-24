<script setup lang="ts">
import { useFormAttachments } from './useAttachmentDraft'
import type { DemoAttachment } from '../../types/commissions/registration'
defineProps<{ files?: DemoAttachment[] }>()
const uploads = useFormAttachments()
const emit = defineEmits<{ reset: [] }>()
</script>
<template>
  <div v-if="uploads.pending(files).length" class="vstack gap-2 my-2" aria-live="polite">
    <div v-for="task in uploads.pending(files)" :key="task.id" class="d-flex flex-wrap align-items-center gap-2 rounded p-2" :class="task.phase === 'failed' ? 'bg-danger-subtle text-danger-emphasis' : 'bg-primary-subtle text-primary-emphasis'" :role="task.phase === 'failed' ? 'alert' : 'status'">
      <i :class="task.phase === 'failed' ? 'ti ti-alert-circle' : 'ti ti-file-upload'" aria-hidden="true"></i>
      <span class="text-break">{{ task.file.name }}</span>
      <span class="ms-auto">{{ task.phase === 'failed' ? task.error : task.phase === 'reading' ? '正在读取' : task.phase === 'saving' ? '正在保存附件…' : `正在上传${task.percent === undefined ? '' : ` ${task.percent}%`}` }}</span>
      <button v-if="task.phase === 'failed'" class="btn btn-sm btn-danger-lt" type="button" @click="uploads.retry(task); emit('reset')">重试</button>
      <button v-if="task.phase === 'failed'" class="btn btn-sm btn-light" type="button" @click="uploads.removeTask(task); emit('reset')">移除</button>
    </div>
  </div>
</template>
