<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import TemplateEditableSelect from '../common/TemplateEditableSelect.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { equipmentStates, type EquipmentLedgerRow } from '../../types/quality/equipmentLedger'
import { equipmentBatchFields, type EquipmentBatchKey, type EquipmentBatchChanges, type EquipmentFormOptions } from '../../types/quality/equipmentForm'

const props = defineProps<{ records: EquipmentLedgerRow[] }>()
const emit = defineEmits<{ close: []; saved: [count: number]; refresh: [] }>()
const checked = ref<EquipmentBatchKey[]>([])
const draft = reactive<Record<EquipmentBatchKey, string>>(Object.fromEntries(equipmentBatchFields.map(field => [field.key, ''])) as Record<EquipmentBatchKey, string>)
const options = ref<EquipmentFormOptions>(), loading = ref(false), busy = ref(false), error = ref<ErrorValue>('')
const leave = useFormLeaveGuard(() => [draft, checked.value], () => !!options.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true
const controller = new AbortController()
async function loadOptions() {
  if (loading.value || busy.value) return
  loading.value = true; error.value = ''
  try { const result = await registrationDemo.equipmentFormOptions(controller.signal); if (alive) options.value = result }
  catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) loading.value = false }
}
async function save() {
  if (busy.value || loading.value || !options.value || !checked.value.length || !props.records.length) return
  const changes = Object.fromEntries(checked.value.map(key => [key, key === 'price' ? draft.price === '' ? null : Number(draft.price) : draft[key]])) as EquipmentBatchChanges
  busy.value = true; error.value = ''
  try {
    const result = await registrationDemo.batchUpdateEquipment({ records: props.records.map(row => ({ id: row.id, version: row.version || 1 })), changes })
    if (alive) { leave.commit(); emit('saved', result.count) }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
onBeforeUnmount(() => { alive = false; controller.abort() })
void loadOptions()
</script>
<template>
  <BootstrapModal guard-close open title="批量修改设备" size="lg" scrollable :loading="loading" :busy="busy" body-class="py-2" @close="closeForm">
    <template #toolbar><p class="text-muted mb-0">已选 {{ records.length }} 台设备</p></template>
    <form v-if="options" id="equipment-batch-form" @submit.prevent="save">
      <p class="text-muted small mb-3">仅修改勾选字段；勾选后留空将清空该字段，设备状态必须选择。</p>
      <fieldset :disabled="busy" class="vstack gap-2">
        <div v-for="field in equipmentBatchFields" :key="field.key" class="row g-2 align-items-center">
          <div class="col-12 col-sm-5"><label class="d-flex align-items-center gap-2 mb-0 py-1" :for="`batch-check-${field.key}`"><input :id="`batch-check-${field.key}`" v-model="checked" :value="field.key" type="checkbox" class="form-check-input m-0 flex-shrink-0" :aria-label="`修改${field.label}`" /><span>{{ field.label }}</span></label></div>
          <div class="col-12 col-sm-7">
            <TemplateDate v-if="field.kind === 'date'" :id="`batch-${field.key}`" :data-validation-key="field.key" :aria-label="field.label" v-model="draft[field.key]" :disabled="busy || !checked.includes(field.key)" within-modal />
            <TemplateEditableSelect v-else-if="field.kind === 'type'" :id="`batch-${field.key}`" :data-validation-key="field.key" :label="field.label" v-model="draft[field.key]" :options="options.equipmentTypes" :readonly="busy || !checked.includes(field.key)" :maxlength="1000" />
            <select v-else-if="field.kind === 'department'" :id="`batch-${field.key}`" :data-validation-key="field.key" :aria-label="field.label" v-model="draft[field.key]" class="form-select" :disabled="!checked.includes(field.key)"><option value="">无</option><option v-for="department in options.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select>
            <select v-else-if="field.kind === 'status'" :id="`batch-${field.key}`" :data-validation-key="field.key" :aria-label="field.label" v-model="draft[field.key]" class="form-select" :disabled="!checked.includes(field.key)" required><option value="" disabled>请选择</option><option v-for="status in equipmentStates" :key="status">{{ status }}</option></select>
            <input v-else :id="`batch-${field.key}`" :data-validation-key="field.key" :aria-label="field.label" v-model="draft[field.key]" class="form-control" :type="field.kind === 'price' ? 'number' : 'text'" :min="field.kind === 'price' ? 0 : undefined" :max="field.kind === 'price' ? 1000000000000 : undefined" :step="field.kind === 'price' ? '0.01' : undefined" maxlength="1000" :disabled="!checked.includes(field.key)" />
          </div>
        </div>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!options" :busy="loading || busy" class="mt-3" @retry="loadOptions" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">取消</button><button type="submit" form="equipment-batch-form" class="btn btn-primary" :disabled="busy || loading || !options || !checked.length"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '确认' }}</button></template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
