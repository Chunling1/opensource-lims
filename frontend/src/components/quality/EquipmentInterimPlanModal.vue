<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import TemplateDate from '../common/TemplateDate.vue'
import TemplateYear from '../common/TemplateYear.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import EquipmentSelectPanel from './EquipmentSelectPanel.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import type { EquipmentLedgerRow } from '../../types/quality/equipmentLedger'
import type { InterimPlanDraft, InterimPlanRow } from '../../types/quality/equipmentInterimPlan'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: InterimPlanRow }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const today = clientToday(), currentYear = Number(today.slice(0, 4))
const draft = reactive<InterimPlanDraft>({ equipmentId: '', year: currentYear, testDate: today, checkDate: today, points: '', method: '', departmentId: currentActor.value.departmentId, notes: '' })
const basic = reactive({ code: '', name: '', model: '', accuracy: '', range: '' }), record = ref(props.row)
const loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>('')
const picking = ref(false), candidate = ref<EquipmentLedgerRow>()
const title = computed(() => picking.value ? '选择设备' : `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}设备期间核查计划`)
const readonly = computed(() => props.mode === 'view' || busy.value)
const departments = computed(() => registrationDepartments.filter(item => currentActor.value.scope === 'all' || item.id === currentActor.value.departmentId))
const basicFields = [{ key: 'model', label: '规格型号' }, { key: 'accuracy', label: '精度' }, { key: 'range', label: '量程' }] as const
const leave = useFormLeaveGuard(() => draft, () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
function assignBasic(value: typeof basic) { for (const key of Object.keys(basic) as (keyof typeof basic)[]) basic[key] = value[key] }
async function load() {
  if (!props.row || busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false
  try {
    const value = await registrationDemo.interimPlanDetail(props.row.id, request.signal)
    if (alive && !request.signal.aborted) { record.value = value; for (const key of Object.keys(draft) as (keyof InterimPlanDraft)[]) Object.assign(draft, { [key]: value[key] }); assignBasic(value); loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function choose() {
  if (!candidate.value) return
  draft.equipmentId = candidate.value.id; assignBasic(candidate.value)
  draft.testDate = candidate.value.lastTestDate || today
  picking.value = false
  await nextTick(); document.getElementById('interim-code')?.dispatchEvent(new Event('change', { bubbles: true }))
}
async function close() { if (!busy.value) { if (picking.value) picking.value = false; else await closeForm() } }
async function save() {
  if (readonly.value || loading.value || !loaded.value) return
  if (props.mode !== 'delete' && !draft.equipmentId) { error.value = new AppError('VALIDATION', '请选择设备。', { fieldErrors: { equipmentId: '请选择设备。' } }); return }
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteInterimPlan(record.value!.id, record.value!.version)
    else await registrationDemo.saveInterimPlan({ ...draft, ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode === 'view' || props.mode === 'edit') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal open :title="title" :size="mode === 'delete' ? undefined : 'xl'" scrollable :busy="busy" :loading="loading" guard-close :body-class="mode === 'delete' ? 'py-2' : undefined" @close="close">
    <EquipmentSelectPanel v-if="picking" :value="candidate" @select="candidate = $event" />
    <template v-else>
      <template v-if="mode === 'delete'"><p class="text-break">确认删除设备“{{ record?.code }} / {{ record?.name }}”的 {{ record?.year }} 年期间核查计划？</p><p class="text-muted mb-0">仅删除此计划，设备台账保留。</p></template>
      <form v-else-if="loaded" id="interim-plan-form" @submit.prevent="save">
        <fieldset :disabled="readonly" class="row g-3">
          <div class="col-12 col-md-4"><label for="interim-code" class="form-label">设备编号<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><div class="input-group"><input id="interim-code" data-validation-key="equipmentId" :value="basic.code" class="form-control" readonly /><button v-if="mode !== 'view'" type="button" class="btn btn-light" aria-label="选择设备" @click="candidate = undefined; picking = true"><i class="ti ti-search" aria-hidden="true"></i></button></div></div>
          <div class="col-12 col-md-8"><label for="interim-name" class="form-label">设备名称</label><input id="interim-name" :value="basic.name" class="form-control" disabled /></div>
          <div v-for="field in basicFields" :key="field.key" class="col-12 col-md-4"><label :for="`interim-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`interim-${field.key}`" :value="basic[field.key]" class="form-control" disabled /></div>
          <div class="col-12 col-md-4"><label for="interim-test-date" class="form-label">检定日期</label><TemplateDate id="interim-test-date" data-validation-key="testDate" v-model="draft.testDate" within-modal :disabled="readonly" /></div>
          <div class="col-12 col-md-4"><label for="interim-check-date" class="form-label">核查时间</label><TemplateDate id="interim-check-date" data-validation-key="checkDate" v-model="draft.checkDate" within-modal :disabled="readonly" /></div>
          <div class="col-12 col-md-4"><label for="interim-points" class="form-label">检测点</label><input id="interim-points" data-validation-key="points" v-model="draft.points" class="form-control" maxlength="1000" /></div>
          <div class="col-12 col-md-4"><label for="interim-method" class="form-label">核查方法</label><input id="interim-method" data-validation-key="method" v-model="draft.method" class="form-control" maxlength="1000" /></div>
          <div class="col-12 col-md-4"><label for="interim-department" class="form-label">实施部门</label><select id="interim-department" data-validation-key="departmentId" v-model="draft.departmentId" class="form-select" required><option v-for="department in departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
          <div class="col-12 col-md-4"><label for="interim-year" class="form-label">年度</label><TemplateYear id="interim-year" data-validation-key="year" v-model="draft.year" required :disabled="readonly" /></div>
          <div class="col-12"><label for="interim-notes" class="form-label">备注</label><textarea id="interim-notes" data-validation-key="notes" v-model="draft.notes" class="form-control" rows="2" maxlength="1000"></textarea></div>
        </fieldset>
      </form>
      <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" :class="{ 'mt-3': !!error && loaded }" @retry="load" />
    </template>
    <template #footer>
      <template v-if="picking"><button type="button" class="btn btn-light" @click="picking = false">返回</button><button type="button" class="btn btn-primary" :disabled="!candidate" @click="choose">确定</button></template>
      <template v-else>
        <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button>
        <button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !loaded" @click="save">{{ busy ? '正在删除…' : '确认删除' }}</button>
        <button v-else-if="mode !== 'view'" type="submit" form="interim-plan-form" class="btn btn-primary" :disabled="busy || loading || !loaded"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '确定' }}</button>
      </template>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
