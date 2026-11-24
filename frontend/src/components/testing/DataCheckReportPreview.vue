<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import DataEntryPreview from './DataEntryPreview.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EntryDetail } from '../../types/testing/dataEntryDetail'

const props = defineProps<{ detail: EntryDetail; active: boolean; compact?: boolean; previewTitle?: string }>()
const emit = defineEmits<{ refresh: [] }>()
const url = ref(''), blob = ref<Blob>(), loading = ref(false), error = ref<ErrorValue>('')
const filename = computed(() => `${props.detail.sample.code}-最终报告.pdf`)
const waiting = computed(() => props.detail.reportStatus === 'running')
const emptyText = computed(() => loading.value ? '正在加载报告预览…' : waiting.value ? '报告正在生成，请稍候…' : error.value ? '报告预览尚不可用' : props.detail.reportStatus === 'stale' ? '报告已更新，请完成报告填写后再预览' : props.detail.reportStatus === 'failed' ? '报告生成失败，请重新完成报告填写' : '暂无可预览报告')
let sequence = 0
function clear() {
  sequence++
  if (url.value) URL.revokeObjectURL(url.value)
  url.value = ''; blob.value = undefined; loading.value = false; error.value = ''
}
async function load() {
  clear()
  if (!props.active || props.detail.reportStatus !== 'ready' || !props.detail.job || !props.detail.capabilities.canView) return
  const token = sequence, sampleId = props.detail.sample.id, taskId = props.detail.job.id
  loading.value = true
  try {
    const result = await registrationDemo.entryDownload(sampleId, `report-tasks/${encodeURIComponent(taskId)}/pdf`)
    if (token !== sequence) return
    blob.value = result; url.value = URL.createObjectURL(result)
  } catch (issue) { if (token === sequence) error.value = normalizeError(issue) }
  finally { if (token === sequence) loading.value = false }
}
watch(() => [props.active, props.detail.sample.id, props.detail.sample.version, props.detail.reportRevision, props.detail.job?.id, props.detail.reportStatus], load, { immediate: true })
onBeforeUnmount(clear)
</script>
<template>
  <section :class="compact ? 'mb-0' : 'mb-4'" aria-label="报告预览工作区" :aria-busy="loading || waiting">
    <DataEntryPreview id="check-report-preview" persistent :url="url" :blob="blob" :name="filename" type="application/pdf" :title="previewTitle || '报告预览'">
      <template #before>
        <ErrorNotice :error="error" />
        <button v-if="error || ['stale', 'failed'].includes(detail.reportStatus)" type="button" class="btn btn-light mb-3" :disabled="loading" @click="emit('refresh')">刷新预览</button>
      </template>
      <template #empty><div class="text-center text-muted py-5" role="status"><span v-if="loading || waiting" class="spinner-border spinner-border-sm d-block mx-auto mb-3" aria-hidden="true"></span><i v-else class="ti ti-file-type-pdf display-4 d-block mb-3" aria-hidden="true"></i>{{ emptyText }}</div></template>
    </DataEntryPreview>
  </section>
</template>
