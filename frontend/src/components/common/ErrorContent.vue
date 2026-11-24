<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRetryDelay } from './useRetryDelay'
import { canRetry, isOperationalError, safeReturn, type AppError } from '../../services/common/errors'
const props = defineProps<{ error: AppError; standalone?: boolean; retry?: boolean; backTo?: string; backLabel?: string; title?: string; busy?: boolean }>()
defineEmits<{ retry: [] }>()
const seconds = useRetryDelay(computed(() => props.error))
const recovery = ref<HTMLElement>(), copied = ref(false)
const asset = (name: string) => `${import.meta.env.BASE_URL}template/assets/images/${name}`
const title = computed(() => props.title || ({ BAD_REQUEST: '访问参数有误', UNAUTHORIZED: '身份已失效', FORBIDDEN: '当前身份无权访问', NOT_FOUND: '记录不存在或已不可访问', VERSION_CONFLICT: '记录已更新', MAINTENANCE: '系统维护中', STORAGE_UNAVAILABLE: '本地业务数据暂不可用', STORAGE_WRITE: '数据未保存', RESOURCE_LOAD: '页面资源加载失败', NETWORK: '连接暂不可用' } as Record<string, string>)[props.error.code] || '暂时无法完成操作')
const icon = computed(() => props.error.code === 'FORBIDDEN' ? 'ti ti-lock' : props.error.code === 'UNAUTHORIZED' ? 'ti ti-user-x' : props.error.code.startsWith('STORAGE') ? 'ti ti-database' : 'ti ti-alert-circle')
watch(() => props.error, async () => { copied.value = false; await nextTick(); recovery.value?.querySelector<HTMLElement>('button, a')?.focus({ preventScroll: true }) }, { immediate: true })
function reloadPage() { window.location.reload() }
async function copy() { try { await navigator.clipboard.writeText(props.error.diagnosticId); copied.value = true } catch { copied.value = false } }
</script>
<template>
  <div class="row justify-content-center"><div :class="standalone ? 'col-xl-7 col-lg-8' : 'col-xl-8 col-lg-10'" class="text-center py-4">
    <img v-if="error.code === 'NOT_FOUND'" :src="asset('error400-cover.png')" alt="" class="img-fluid error-basic-img w-100" />
    <div v-else-if="error.code === 'INTERNAL'" class="error-500 position-relative"><img :src="asset('error500.png')" alt="" class="img-fluid error-500-img" /><div class="title text-muted">500</div></div>
    <img v-else-if="error.code === 'MAINTENANCE'" :src="asset('maintenance.png')" alt="" class="img-fluid error-basic-img w-100" />
    <template v-else><i :class="icon" class="display-4 text-primary" aria-hidden="true"></i><div v-if="error.status" class="display-3 fw-medium text-muted my-3">{{ error.status }}</div></template>
    <h3 class="mt-3">{{ title }}</h3><p class="text-muted text-break mb-4">{{ error.message }}</p>
    <div ref="recovery" class="d-flex justify-content-center flex-wrap gap-2">
      <button v-if="retry && canRetry(error)" type="button" class="btn btn-success" :disabled="busy || seconds > 0" @click="$emit('retry')"><i class="ti ti-refresh me-1" aria-hidden="true"></i>{{ busy ? '正在重试…' : seconds ? `${seconds} 秒后重试` : '重试' }}</button>
      <button v-if="standalone && error.code === 'RESOURCE_LOAD'" type="button" class="btn btn-light" @click="reloadPage">刷新页面</button>
      <RouterLink v-if="!standalone || backTo" class="btn btn-light" :to="error.code === 'UNAUTHORIZED' || error.code === 'FORBIDDEN' ? '/identity' : backTo ? safeReturn(backTo) : '/dashboard'">{{ error.code === 'UNAUTHORIZED' || error.code === 'FORBIDDEN' ? '账号信息' : backLabel || (backTo ? '返回列表' : '返回工作台') }}</RouterLink>
      <RouterLink v-if="!standalone && ['UNAUTHORIZED', 'FORBIDDEN'].includes(error.code)" class="btn btn-light" to="/dashboard">返回工作台</RouterLink>
    </div>
    <p v-if="!isOperationalError(error)" class="text-muted small mt-3 mb-0">诊断编号：{{ error.diagnosticId }} <button type="button" class="btn btn-link btn-sm" @click="copy">{{ copied ? '已复制' : '复制编号' }}</button></p>
  </div></div>
</template>
