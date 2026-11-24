<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyMaintenanceCost, maintenanceCostTotal, type MaintenanceCostRecord } from '../../types/quality/maintenanceCosts'
import TemplateDate from '../common/TemplateDate.vue'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: MaintenanceCostRecord }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const record = ref(props.row), loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>('')
const draft = reactive({ ...emptyMaintenanceCost(), maintainedAt: clientToday(), departmentId: currentActor.value.departmentId })
const departments = computed(() => registrationDepartments.filter(dept => currentActor.value.scope === 'all' || dept.id === currentActor.value.departmentId))
const numericInput = (value: unknown) => value === null || value === '' ? null : Number(value)
const total = computed(() => maintenanceCostTotal(numericInput(draft.unitPrice), numericInput(draft.quantity)))
const readonly = computed(() => props.mode === 'view' || busy.value)
const title = computed(() => `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}设备维护费用`)
const leave = useFormLeaveGuard(() => draft, () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.row || busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false
  try {
    const result = await registrationDemo.maintenanceCostDetail(props.row.id, request.signal)
    if (alive && !request.signal.aborted) { record.value = result; Object.assign(draft, result); loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save() {
  if (busy.value || loading.value || !loaded.value || props.mode === 'view') return

  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteMaintenanceCost(record.value!.id, record.value!.version)
    else await registrationDemo.saveMaintenanceCost({ ...draft, unitPrice: numericInput(draft.unitPrice), quantity: numericInput(draft.quantity), ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode === 'view' || props.mode === 'edit') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :size="mode === 'delete' ? undefined : 'lg'" :busy="busy" :loading="loading" scrollable :body-class="mode === 'delete' ? 'py-2' : undefined" @close="closeForm">
    <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除设备维护费用“{{ record?.name }}”？</p>
    <form v-else-if="loaded" id="maintenance-cost-form" @submit.prevent="save">
      <fieldset :disabled="readonly" class="row g-3">
        <div class="col-12 col-md-6"><label for="maintenance-cost-name" class="form-label">维护项目<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><input id="maintenance-cost-name" v-model="draft.name" data-validation-key="name" class="form-control" required maxlength="200" /></div>
        <div class="col-12 col-md-6"><label for="maintenance-cost-date" class="form-label">维护日期<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><TemplateDate id="maintenance-cost-date" v-model="draft.maintainedAt" data-validation-key="maintainedAt" required within-modal :disabled="readonly" /></div>
        <div class="col-12 col-md-6"><label for="maintenance-cost-price" class="form-label">单价</label><input id="maintenance-cost-price" v-model.number="draft.unitPrice" data-validation-key="unitPrice" class="form-control" type="number" min="0" max="1000000" step="0.01" /></div>
        <div class="col-12 col-md-6"><label for="maintenance-cost-quantity" class="form-label">数量</label><input id="maintenance-cost-quantity" v-model.number="draft.quantity" data-validation-key="quantity" class="form-control" type="number" min="0" max="1000000" step="0.001" /></div>
        <div class="col-12 col-md-6"><label for="maintenance-cost-total" class="form-label">总金额</label><input id="maintenance-cost-total" :value="total === null ? '' : total.toFixed(2)" class="form-control bg-light" readonly /><div v-if="mode !== 'view'" class="form-text">根据单价和数量自动计算。</div></div>
        <div class="col-12 col-md-6"><label for="maintenance-cost-department" class="form-label">部门</label><select id="maintenance-cost-department" v-model="draft.departmentId" data-validation-key="departmentId" class="form-select"><option v-for="department in departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
        <div class="col-12"><label for="maintenance-cost-notes" class="form-label">备注</label><textarea id="maintenance-cost-notes" v-model="draft.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="2000"></textarea></div>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" :class="{ 'mt-3': loaded && error }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button>
      <button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !loaded" @click="save"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在删除…' : '确认删除' }}</button>
      <button v-else-if="mode !== 'view'" type="submit" form="maintenance-cost-form" class="btn btn-primary" :disabled="busy || loading || !loaded"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
