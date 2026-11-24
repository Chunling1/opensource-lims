<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyOverallPlan, overallPlanSections, overallPlanFields, type OverallPlanKey, type OverallPlanRow } from '../../types/quality/equipmentOverallPlan'
const props = defineProps<{ mode: 'view' | 'edit' | 'batch'; records: OverallPlanRow[] }>()
const emit = defineEmits<{ close: []; saved: [number]; refresh: [] }>()
const title = computed(() => props.mode === 'batch' ? '批量修改设备总体计划' : `${props.mode === 'view' ? '查看' : '编辑'}设备总体计划`)
const draft = reactive(emptyOverallPlan()), checked = ref<OverallPlanKey[]>([]), record = ref<OverallPlanRow>()
const loading = ref(false), busy = ref(false), error = ref<ErrorValue>('')
const readonly = computed(() => props.mode === 'view' || busy.value)
const basicFields = [{ key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称' }, { key: 'model', label: '规格型号' }, { key: 'accuracy', label: '精度' }, { key: 'range', label: '量程' }] as const
const leave = useFormLeaveGuard(() => [draft, checked.value], () => props.mode !== 'view' && (props.mode === 'batch' || !!record.value) && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.records[0] || busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; record.value = undefined
  try {
    const result = await registrationDemo.overallPlanDetail(props.records[0].id, request.signal)
    if (alive && !request.signal.aborted) { record.value = result; for (const field of overallPlanFields) draft[field.key] = result[field.key] }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save() {
  if (readonly.value || loading.value || props.mode === 'batch' && !checked.value.length || props.mode !== 'batch' && !record.value) return
  busy.value = true; error.value = ''
  try {
    const records = props.mode === 'batch' ? props.records : [record.value!]
    const keys = props.mode === 'batch' ? checked.value : overallPlanFields.map(field => field.key)
    const result = await registrationDemo.saveOverallPlan({ records: records.map(row => ({ id: row.id, version: row.version, equipmentVersion: row.equipmentVersion })), changes: Object.fromEntries(keys.map(key => [key, draft[key]])) }, props.mode === 'batch')
    if (alive) { leave.commit(); emit('saved', result.count) }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode !== 'batch') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :size="mode === 'batch' ? 'lg' : 'xl'" scrollable :loading="loading" :busy="busy" @close="closeForm">
    <template v-if="mode === 'batch'" #toolbar><p class="text-muted mb-0">已选 {{ records.length }} 台设备</p></template>
    <form v-if="mode === 'batch' || record" id="overall-plan-form" @submit.prevent="save">
      <template v-if="mode === 'batch'">
        <p class="text-muted small">仅修改勾选字段；勾选后留空会清空该字段。</p>
        <fieldset :disabled="readonly" class="vstack gap-2">
          <div v-for="field in overallPlanFields" :key="field.key" class="row g-2 align-items-center">
            <div class="col-12 col-sm-5"><label class="d-flex align-items-center gap-2 mb-0 py-1"><input v-model="checked" :value="field.key" type="checkbox" class="form-check-input m-0 flex-shrink-0" :aria-label="`修改${field.label}`" /><span>{{ field.label }}</span></label></div>
            <div class="col-12 col-sm-7">
              <select v-if="field.key === 'checkRequired'" v-model="draft[field.key]" :data-validation-key="field.key" :aria-label="field.label" class="form-select" :disabled="!checked.includes(field.key)"><option value="">未设置</option><option>是</option><option>否</option></select>
              <input v-else v-model="draft[field.key]" :data-validation-key="field.key" :aria-label="field.label" class="form-control" maxlength="1000" :disabled="!checked.includes(field.key)" />
            </div>
          </div>
        </fieldset>
      </template>
      <template v-else-if="record">
        <div class="row g-3">
          <div v-for="field in basicFields" :key="field.key" class="col-12" :class="field.key === 'name' ? 'col-md-8' : 'col-md-4'"><label :for="`overall-basic-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`overall-basic-${field.key}`" :value="record[field.key]" class="form-control" disabled /></div>
        </div>
        <fieldset v-for="(section, index) in overallPlanSections" :key="index" :disabled="readonly" class="mt-3" :class="{ 'border-top pt-3': section.label }">
          <legend v-if="section.label" class="float-none w-auto fs-5 fw-semibold mb-2">{{ section.label }}</legend>
          <div class="row g-3"><div v-for="field in section.fields" :key="field.key" class="col-12" :class="section.fields.length > 1 ? 'col-md-4' : undefined">
            <label :for="`overall-${field.key}`" class="form-label">{{ field.label }}</label>
            <select v-if="field.key === 'checkRequired'" :id="`overall-${field.key}`" v-model="draft[field.key]" :data-validation-key="field.key" class="form-select"><option value="">未设置</option><option>是</option><option>否</option></select>
            <input v-else :id="`overall-${field.key}`" v-model="draft[field.key]" :data-validation-key="field.key" class="form-control" maxlength="1000" />
          </div></div>
        </fieldset>
      </template>
    </form>
    <ErrorNotice :error="error" :retry="mode !== 'batch' && !record" :busy="loading || busy" :class="{ 'mt-3': !!error && (record || mode === 'batch') }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button>
      <button v-if="mode !== 'view'" type="submit" form="overall-plan-form" class="btn btn-primary" :disabled="busy || loading || (mode === 'batch' ? !checked.length : !record)"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
