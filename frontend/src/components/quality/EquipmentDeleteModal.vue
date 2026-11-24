<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EquipmentRecord } from '../../types/quality/equipmentForm'
import type { EquipmentLedgerRow } from '../../types/quality/equipmentLedger'

const props = defineProps<{ row: EquipmentLedgerRow }>()
const emit = defineEmits<{ close: []; deleted: [] }>()
const record = ref<EquipmentRecord>(), loading = ref(false), busy = ref(false), error = ref<ErrorValue>('')
let active = true, controller: AbortController | undefined
const impact = computed(() => {
  const profile = record.value?.profile
  if (!profile) return ''
  const records = profile.calibrations.length + profile.maintenance.length + profile.usage.length + profile.checks.length
  const files = Object.values(profile.attachments).reduce((total, rows) => total + rows.length, 0)
  const parts = [records ? `${records} 条设备记录` : '', files ? `${files} 个附件` : '', profile.projects.length ? `${profile.projects.length} 项检测方案关联` : ''].filter(Boolean)
  return parts.length ? `同时删除该设备下的${parts.join('、')}。` : ''
})
async function load() {
  if (busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''
  try {
    const result = await registrationDemo.equipmentDetail(props.row.id, request.signal)
    if (active && !request.signal.aborted) record.value = result
  } catch (issue) { if (active && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (active && !request.signal.aborted) loading.value = false }
}
async function remove() {
  if (!record.value || busy.value || loading.value || error.value) return
  busy.value = true; error.value = ''
  try {
    await registrationDemo.deleteEquipment(record.value.id, record.value.version)
    if (active) emit('deleted')
  } catch (issue) { if (active) error.value = normalizeError(issue) }
  finally { if (active) busy.value = false }
}
onBeforeUnmount(() => { active = false; controller?.abort() })
void load()
</script>
<template>
  <BootstrapModal open title="删除设备" :busy="busy" scrollable body-class="py-2" @close="!busy && emit('close')">
    <p class="text-break" :class="{ 'mb-0': !loading && !impact && !error }">确认删除设备“{{ (record || row).name }}”（{{ (record || row).code }}）？</p>
    <p v-if="loading" class="text-muted small mb-0" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在核对关联记录…</p>
    <p v-else-if="impact" class="text-muted mb-0 text-break">{{ impact }}</p>
    <ErrorNotice :error="error" :busy="loading || busy" retry :class="{ 'mt-3': record && error }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button>
      <button type="button" class="btn btn-danger" :disabled="busy || loading || !record || !!error" @click="remove"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在删除…' : '确认删除' }}</button>
    </template>
  </BootstrapModal>
</template>
