<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateDate from '../common/TemplateDate.vue'
import DataTable from '../common/table/DataTable.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { currentActor } from '../../stores/session'
import { clientToday } from '../../services/common/date'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { equipmentConditionStates, type EquipmentCondition } from '../../types/quality/equipmentLoans'
import type { EquipmentLoanRow } from '../../types/quality/equipmentLoans'
const props = defineProps<{ mode: 'borrow' | 'return' | 'view'; ids: string[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const title = computed(() => props.mode === 'borrow' ? '领用设备' : props.mode === 'return' ? '归还设备' : '查看领用记录')
const rows = ref<EquipmentLoanRow[]>([]), loading = ref(false), busy = ref(false), ready = ref(false), error = ref<ErrorValue>('')
const draft = reactive({ date: clientToday(), borrower: currentActor.value.name, returner: currentActor.value.name, borrowedStatus: '正常' as EquipmentCondition, returnedStatus: '正常' as EquipmentCondition, notes: '' })
const conflict = computed(() => !!error.value && ['NOT_FOUND', 'FORBIDDEN'].includes(error.value.code))
const summaryColumns = [{ key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称' }, { key: 'model', label: '规格型号' }, { key: 'currentStatus', label: '当前状态' }, { key: 'keeper', label: '设备管理员' }] as const
const returnColumns = [{ key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称' }, { key: 'borrower', label: '领用人' }, { key: 'borrowedAt', label: '领用日期' }, { key: 'borrowedStatus', label: '领用时设备状态' }, { key: 'currentStatus', label: '当前台账状态' }] as const
const detailFields = [{ key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称' }, { key: 'model', label: '规格型号' }, { key: 'manufacturer', label: '生产厂家' }, { key: 'department', label: '所属部门' }, { key: 'keeper', label: '设备管理员' }, { key: 'borrower', label: '领用人' }, { key: 'borrowedAt', label: '领用日期' }, { key: 'borrowedStatus', label: '领用时设备状态' }, { key: 'borrowedBy', label: '领用操作人' }, { key: 'createdAt', label: '领用操作时间' }, { key: 'notes', label: '领用备注' }, { key: 'loanStatus', label: '归还状态' }, { key: 'returnedAt', label: '归还日期' }, { key: 'returnedStatus', label: '归还时设备状态' }, { key: 'returner', label: '归还人' }, { key: 'returnedBy', label: '归还操作人' }, { key: 'updatedAt', label: '归还操作时间' }, { key: 'returnNotes', label: '归还备注' }] as const
const leave = useFormLeaveGuard(() => draft, () => props.mode !== 'view' && ready.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; ready.value = false
  try {
    const result = props.mode === 'view' ? { items: [await registrationDemo.equipmentLoanDetail(props.ids[0]!, request.signal)] } : await registrationDemo.equipmentLoanContext(props.mode, props.ids, request.signal)
    if (!alive || request.signal.aborted) return
    rows.value = result.items
    ready.value = true
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function submit() {
  if (!ready.value || busy.value || conflict.value || props.mode === 'view') return
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'borrow') await registrationDemo.borrowEquipment({ ...draft, records: rows.value.map(row => ({ id: row.id, version: row.version, equipmentVersion: row.equipmentVersion })) })
    else await registrationDemo.returnEquipment({ returner: draft.returner, date: draft.date, returnedStatus: draft.returnedStatus, notes: draft.notes, records: rows.value.map(row => ({ id: row.id, version: row.version, equipmentVersion: row.equipmentVersion })) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" size="xl" scrollable :loading="loading" :busy="busy" @close="closeForm">
    <form v-if="ready && mode !== 'view'" id="equipment-loan-form" @submit.prevent="submit">
      <fieldset :disabled="busy || conflict">
        <template v-if="mode === 'borrow'">
          <DataTable label="本次领用设备" :rows="rows" :columns="summaryColumns" :row-key="row => row.id" :row-label="row => row.code" />
          <div class="row g-3 mt-1">
            <div class="col-12 col-md-4"><label for="loan-borrower" class="form-label">领用人 <span class="text-danger">*</span></label><input id="loan-borrower" v-model="draft.borrower" data-validation-key="borrower" class="form-control" maxlength="100" /></div>
            <div class="col-12 col-md-4"><label for="loan-status" class="form-label">设备状态 <span class="text-danger">*</span></label><select id="loan-status" v-model="draft.borrowedStatus" data-validation-key="borrowedStatus" class="form-select"><option v-for="status in equipmentConditionStates" :key="status">{{ status }}</option></select></div>
            <div class="col-12 col-md-4"><label for="loan-date" class="form-label">领用日期 <span class="text-danger">*</span></label><TemplateDate id="loan-date" v-model="draft.date" data-validation-key="date" within-modal :disabled="busy || conflict" /></div>
            <div class="col-12"><label for="loan-notes" class="form-label">备注</label><textarea id="loan-notes" v-model="draft.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="1000"></textarea></div>
          </div>
        </template>
        <template v-else>
          <DataTable label="本次归还设备" :rows="rows" :columns="returnColumns" :row-key="row => row.id" :row-label="row => row.code" />
          <div class="row g-3 mt-1">
            <div class="col-12 col-md-4"><label for="loan-returner" class="form-label">归还人 <span class="text-danger">*</span></label><input id="loan-returner" v-model="draft.returner" data-validation-key="returner" class="form-control" maxlength="100" /></div>
            <div class="col-12 col-md-4"><label for="return-status" class="form-label">设备状态 <span class="text-danger">*</span></label><select id="return-status" v-model="draft.returnedStatus" data-validation-key="returnedStatus" class="form-select"><option v-for="status in equipmentConditionStates" :key="status">{{ status }}</option></select></div>
            <div class="col-12 col-md-4"><label for="loan-date" class="form-label">归还日期 <span class="text-danger">*</span></label><TemplateDate id="loan-date" v-model="draft.date" data-validation-key="date" within-modal :disabled="busy || conflict" /></div>
            <div class="col-12"><label for="loan-notes" class="form-label">备注</label><textarea id="loan-notes" v-model="draft.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="1000"></textarea></div>
          </div>
        </template>
      </fieldset>
    </form>
    <dl v-if="ready && mode === 'view' && rows[0]" class="row mb-0"><div v-for="field in detailFields" :key="field.key" class="col-12 col-md-6 mb-2"><dt class="text-muted fw-normal">{{ field.label }}</dt><dd class="text-break">{{ rows[0][field.key] || '—' }}</dd></div></dl>
    <ErrorNotice :error="error" :retry="!ready && !conflict" :busy="busy || loading" @retry="load" />
    <button v-if="conflict" type="button" class="btn btn-light mt-3" :disabled="busy || loading" @click="load">刷新设备信息</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button><button v-if="mode !== 'view'" type="submit" form="equipment-loan-form" class="btn btn-primary" :disabled="!ready || loading || busy || conflict">{{ busy ? '正在提交…' : mode === 'borrow' ? '确认领用' : '确认归还' }}</button></template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
