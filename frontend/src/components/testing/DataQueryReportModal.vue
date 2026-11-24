<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import DataCheckReportPreview from './DataCheckReportPreview.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EntryDetail } from '../../types/testing/dataEntryDetail'

const props = defineProps<{ sample: { id: string; code: string; name: string } }>()
defineEmits<{ close: [] }>()
const detail = ref<EntryDetail>(), loading = ref(false), error = ref<ErrorValue>('')
let sequence = 0, timer: ReturnType<typeof setTimeout> | undefined
async function load() {
  clearTimeout(timer)
  const token = ++sequence
  loading.value = true; error.value = ''
  try {
    const result = await registrationDemo.entryDetail(props.sample.id)
    if (token !== sequence) return
    detail.value = result
    if (result.reportStatus === 'running') timer = setTimeout(load, 2000)
  } catch (issue) { if (token === sequence) error.value = normalizeError(issue) }
  finally { if (token === sequence) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { sequence++; clearTimeout(timer) })
</script>
<template>
  <BootstrapModal :loading="loading" open title="报告预览" size="xl" scrollable compact @close="$emit('close')">
    <div v-if="loading && !detail" class="text-center py-3" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载报告…</div>
    <ErrorNotice v-if="error" :error="error" retry :busy="loading" @retry="load" />
    <DataCheckReportPreview v-if="detail" :detail="detail" :preview-title="`${sample.code} · ${sample.name}`" active compact @refresh="load" />
    <template #footer><button type="button" class="btn btn-light" @click="$emit('close')">关闭</button></template>
  </BootstrapModal>
</template>
