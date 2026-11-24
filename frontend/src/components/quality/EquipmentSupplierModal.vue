<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientToday } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptySupplier, emptyEvaluation, supplierFields, type SupplierListKind, type SupplierRecord, type EvaluationRecord } from '../../types/quality/equipmentSuppliers'
const props = defineProps<{ kind: SupplierListKind; mode: 'new' | 'edit' | 'view' | 'delete'; row?: SupplierRecord | EvaluationRecord; selectedSupplier?: SupplierRecord }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const isSupplier = props.kind === 'suppliers', title = computed(() => `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}${isSupplier ? '设备服务商' : '供应商评价'}`)
const supplier = reactive(emptySupplier()), evaluation = reactive({ ...emptyEvaluation(), reviewDate: clientToday(), supplierId: props.selectedSupplier?.id || '', services: props.selectedSupplier?.services || '' })
const record = ref(props.row)
const supplierName = computed(() => props.mode === 'new' ? props.selectedSupplier?.name || '' : record.value?.name || '')
const loading = ref(false), busy = ref(false), ready = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>('')
const readonly = computed(() => props.mode === 'view' || busy.value)
const leave = useFormLeaveGuard(() => [supplier, evaluation], () => ['new', 'edit'].includes(props.mode) && ready.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController()
  error.value = ''; loading.value = true
  if (props.mode !== 'new') ready.value = false
  try {
    const detail = props.row ? await (isSupplier ? registrationDemo.supplierDetail(props.row.id, request.signal) : registrationDemo.supplierEvaluationDetail(props.row.id, request.signal)) : undefined
    if (!alive || request.signal.aborted) return
    if (detail) { record.value = detail; if (isSupplier) Object.assign(supplier, detail); else Object.assign(evaluation, detail) }
    ready.value = true
  } catch (issue) { if (alive && !request.signal.aborted) { error.value = normalizeError(issue); ready.value = false } }
  finally { if (alive && !request.signal.aborted) { loading.value = false } }
}
async function save() {
  if (!ready.value || loading.value || busy.value || props.mode === 'view') return
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteEquipmentSupplierRecord(props.kind, record.value!.id, record.value!.version)
    else {
      const identity = props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}
      if (isSupplier) await registrationDemo.saveEquipmentSupplier({ ...supplier, ...identity })
      else await registrationDemo.saveSupplierEvaluation({ ...evaluation, ...identity })
    }
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode === 'edit' || props.mode === 'view') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :size="mode === 'delete' ? undefined : 'xl'" :busy="busy" :loading="loading" scrollable :body-class="mode === 'delete' ? 'py-2' : undefined" @close="closeForm">
    <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除{{ isSupplier ? '供应商' : '评价' }}“{{ record?.name }}{{ !isSupplier && record && 'reviewDate' in record ? ` · ${record.reviewDate}` : '' }}”？</p>
    <form v-else-if="ready" id="equipment-supplier-form" @submit.prevent="save">
      <fieldset :disabled="readonly">
        <div v-if="isSupplier" class="row g-3">
          <div v-for="field in supplierFields" :key="field.key" class="col-12 col-md-4"><label :for="`supplier-${field.key}`" class="form-label">{{ field.label }}<span v-if="field.key === 'name' && mode !== 'view'" class="text-danger ms-1">*</span></label><input :id="`supplier-${field.key}`" v-model="supplier[field.key]" :data-validation-key="field.key" class="form-control" :maxlength="field.max" /></div>
          <div class="col-12"><label for="supplier-services" class="form-label">服务商提供项目</label><textarea id="supplier-services" v-model="supplier.services" data-validation-key="services" class="form-control" rows="2" maxlength="2000"></textarea></div>
          <div class="col-12"><label for="supplier-notes" class="form-label">备注</label><textarea id="supplier-notes" v-model="supplier.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="2000"></textarea></div>
        </div>
        <div v-else class="row g-3">
          <div class="col-12 col-md-8"><label for="evaluation-supplier" class="form-label">单位名称</label><input id="evaluation-supplier" :value="supplierName" data-validation-key="supplierId" class="form-control bg-light" readonly /></div>
          <div class="col-12 col-md-4"><label for="evaluation-date" class="form-label">评审日期<span v-if="mode !== 'view'" class="text-danger ms-1">*</span></label><TemplateDate id="evaluation-date" v-model="evaluation.reviewDate" data-validation-key="reviewDate" within-modal :disabled="readonly" /></div>
          <div class="col-12"><label for="evaluation-services" class="form-label">服务提供项目</label><textarea id="evaluation-services" v-model="evaluation.services" data-validation-key="services" class="form-control" rows="2" maxlength="2000"></textarea></div>
          <div v-for="field in [{ key: 'quality', label: '评审（质量）' }, { key: 'price', label: '评审（价格）' }, { key: 'service', label: '评审（服务）' }] as const" :key="field.key" class="col-12 col-md-4"><label :for="`evaluation-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`evaluation-${field.key}`" v-model="evaluation[field.key]" :data-validation-key="field.key" class="form-control" maxlength="500" /></div>
          <div v-for="field in [{ key: 'opinions', label: '其它意见' }, { key: 'conclusion', label: '评审结论' }] as const" :key="field.key" class="col-12 col-md-6"><label :for="`evaluation-${field.key}`" class="form-label">{{ field.label }}</label><textarea :id="`evaluation-${field.key}`" v-model="evaluation[field.key]" :data-validation-key="field.key" class="form-control" rows="2" maxlength="2000"></textarea></div>
        </div>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!ready" :busy="busy || loading" :class="{ 'mt-3': error && ready }" @retry="load" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button><button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !ready" @click="save">{{ busy ? '正在删除…' : '确认删除' }}</button><button v-else-if="mode !== 'view'" type="submit" form="equipment-supplier-form" class="btn btn-primary" :disabled="busy || loading || !ready">{{ busy ? '正在保存…' : '保存' }}</button></template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
