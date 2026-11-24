<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateDate from '../common/TemplateDate.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { calibrationPlanFields, type CalibrationPlanRow, type CalibrationPlanValues } from '../../types/quality/equipmentCalibrationPlan'
const props = defineProps<{ mode: 'edit' | 'view'; row: CalibrationPlanRow }>()
const emit = defineEmits<{ close: []; saved: [submitted: boolean] }>()
const record = ref<CalibrationPlanRow>(), draft = ref<CalibrationPlanValues>(), error = ref<ErrorValue>(''), loading = ref(false), busy = ref(false), submitting = ref(false)
const title = computed(() => `${props.mode === 'view' ? '查看' : '检定'}计量器具周期检定计划`)
const readonly = computed(() => props.mode === 'view' || busy.value)
const leave = useFormLeaveGuard(() => draft.value, () => props.mode === 'edit' && !!draft.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''
  try {
    const row = await registrationDemo.calibrationPlanDetail(props.row.id, request.signal)
    if (alive && !request.signal.aborted) {
      record.value = row
      draft.value = Object.fromEntries(calibrationPlanFields.map(field => [field.key, row[field.key]])) as CalibrationPlanValues
    }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save(submit: boolean) {
  if (!record.value || !draft.value || readonly.value || loading.value) return
  busy.value = true; submitting.value = submit; error.value = ''
  try {
    await registrationDemo.saveCalibrationPlan({ id: record.value.id, version: record.value.version, equipmentVersion: record.value.equipmentVersion, values: { ...draft.value } }, submit)
    if (alive) { leave.commit(); emit('saved', submit) }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" size="xl" scrollable :loading="loading" :busy="busy" @close="closeForm">
    <template #title-suffix><span v-if="record && !loading" class="badge ms-2 align-middle small" :class="record.submitted ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning-emphasis'">{{ record.submitted ? '已检定' : '未检定' }}</span></template>
    <form v-if="record && draft" id="calibration-plan-form" @submit.prevent="save(($event as SubmitEvent).submitter?.getAttribute('value') === 'submit')">
      <div class="row g-3 mb-3"><div class="col-12 col-md-4"><label for="calibration-code" class="form-label">设备编号</label><input id="calibration-code" :value="record.code" class="form-control" disabled /></div><div class="col-12 col-md-8"><label for="calibration-name" class="form-label">设备名称</label><input id="calibration-name" :value="record.name" class="form-control" disabled /></div></div>
      <fieldset :disabled="readonly" class="row g-3">
        <div v-for="field in calibrationPlanFields" :key="field.key" class="col-12" :class="'full' in field ? '' : 'wide' in field ? 'col-md-8' : 'col-md-4'">
          <label :for="`calibration-${field.key}`" class="form-label">{{ field.label }}</label>
          <TemplateDate v-if="'date' in field" :id="`calibration-${field.key}`" :data-validation-key="field.key" v-model="draft[field.key]" within-modal :disabled="readonly" />
          <input v-else-if="field.key === 'fee'" id="calibration-fee" data-validation-key="fee" :value="draft.fee" @input="draft.fee = ($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value)" type="number" min="0" max="999999999" step="0.01" class="form-control" />
          <textarea v-else-if="'area' in field" :id="`calibration-${field.key}`" :data-validation-key="field.key" v-model="draft[field.key]" class="form-control" rows="2" maxlength="1000"></textarea>
          <input v-else :id="`calibration-${field.key}`" :data-validation-key="field.key" v-model="draft[field.key]" class="form-control" maxlength="1000" />
        </div>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!record" :busy="loading || busy" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">返回</button>
      <template v-if="mode !== 'view' && record">
        <button type="submit" form="calibration-plan-form" value="save" class="btn btn-light" :disabled="busy || loading">{{ busy && !submitting ? '正在保存…' : '保存' }}</button>
        <button type="submit" form="calibration-plan-form" value="submit" class="btn btn-primary" :disabled="busy || loading">{{ busy && submitting ? '正在提交…' : '提交' }}</button>
      </template>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
