<script setup lang="ts">
import { computed } from 'vue'
import ErrorPage from './ErrorPage.vue'
import ErrorNotice from './ErrorNotice.vue'
import { canRetry, normalizeError, type AppError } from '../../services/common/errors'
const props = defineProps<{ loading?: boolean; error?: AppError | string; hasData?: boolean; backTo?: string }>()
defineEmits<{ retry: [] }>()
const issue = computed(() => props.error ? normalizeError(props.error) : undefined)
</script>
<template>
  <div v-if="loading" class="text-center p-5" role="status"><span class="spinner-border spinner-border-sm text-primary me-2"></span>正在加载…</div>
  <template v-else-if="issue"><ErrorNotice v-if="hasData || ['VALIDATION', 'BUSINESS_RULE'].includes(issue.code)" :error="issue" :retry="canRetry(issue)" :refresh="hasData" @retry="$emit('retry')" /><ErrorPage v-else :error="issue" :back-to="backTo" retry @retry="$emit('retry')" /></template>
</template>
