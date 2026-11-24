<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { dialogValidationKey } from '../forms/useDialogValidation'
import { useRetryDelay } from './useRetryDelay'
import FeedbackNotice from './FeedbackNotice.vue'
import { canRetry, isOperationalError, type AppError } from '../../services/common/errors'
const props = defineProps<{ error?: AppError | ''; retry?: boolean; busy?: boolean; latestTo?: string; refresh?: boolean; compact?: boolean }>()
const emit = defineEmits<{ retry: []; reload: [] }>()
const validation = inject(dialogValidationKey, undefined), applied = ref<string[]>([])
watch(() => props.error, value => { applied.value = value && value.code === 'VALIDATION' && value.fieldErrors ? validation?.show(value.fieldErrors) || [] : [] }, { immediate: true, flush: 'post' })
const remaining = computed(() => props.error && props.error.code === 'VALIDATION' && props.error.fieldErrors ? Object.entries(props.error.fieldErrors).filter(([key]) => !applied.value.includes(key)).map(([, text]) => text) : undefined)
const message = computed(() => remaining.value ? remaining.value.join('；') : props.error ? props.error.message : '')
const seconds = useRetryDelay(computed(() => props.error)), copied = ref(false)
watch(() => props.error, () => { copied.value = false })
function reloadPage() { window.location.reload() }
const operational = computed(() => isOperationalError(props.error))
const retryable = computed(() => !!props.error && props.retry && canRetry(props.error))
const hasActions = computed(() => props.error && (!operational.value || retryable.value || seconds.value || ['UNAUTHORIZED', 'FORBIDDEN', 'RESOURCE_LOAD'].includes(props.error.code)))
async function copy() { if (!props.error) return; try { await navigator.clipboard.writeText(props.error.diagnosticId); copied.value = true } catch { copied.value = false } }
</script>
<template>
  <FeedbackNotice v-if="error && message" :message="message" :trigger="error" :compact="compact" :tone="operational ? 'warning' : 'danger'" :title="operational ? '操作提示' : '系统提示'">
    <div class="text-break">{{ refresh ? '更新失败，当前仍显示上次加载的内容。' : '' }}{{ message }}</div>
    <div v-if="hasActions" class="d-flex flex-wrap align-items-center gap-2 mt-2">
      <span v-if="!retryable && seconds" role="status">请等待 {{ seconds }} 秒后再提交。</span>
      <button v-if="retryable" type="button" class="btn btn-sm" :class="operational ? 'btn-outline-primary' : 'btn-outline-danger'" :disabled="busy || seconds > 0" @click="emit('retry')">{{ seconds ? `${seconds} 秒后重试` : '重试' }}</button>
      <RouterLink v-if="error.code === 'UNAUTHORIZED' || error.code === 'FORBIDDEN'" class="alert-link" to="/identity">切换演示身份</RouterLink>
      <button v-if="error.code === 'RESOURCE_LOAD'" type="button" class="btn btn-sm btn-outline-danger" @click="reloadPage">刷新页面</button>
      <template v-if="!operational"><span class="small">诊断编号：{{ error.diagnosticId }}</span><button type="button" class="btn btn-link btn-sm p-0" @click="copy">{{ copied ? '已复制' : '复制编号' }}</button></template>
    </div>

  </FeedbackNotice>
</template>
