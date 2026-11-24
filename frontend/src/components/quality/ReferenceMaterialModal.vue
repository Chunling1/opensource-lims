<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, nextTick, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateDate from '../common/TemplateDate.vue'
import DataEntryPersonPicker from '../testing/DataEntryPersonPicker.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import type { EntryPersonCandidate } from '../../types/testing/dataEntryDetail'
import { emptyMaterial, emptyAcceptance, acceptanceTextFields, acceptanceStatuses, type MaterialKind, type MaterialRecord, type AcceptanceRecord } from '../../types/quality/referenceMaterials'
const props = defineProps<{ kind: MaterialKind; mode: 'new' | 'edit' | 'view' | 'delete'; row?: MaterialRecord | AcceptanceRecord; selectedMaterial?: MaterialRecord }>()
const emit = defineEmits<{ close: []; saved: []; invalidated: [] }>()
const isMaterial = props.kind === 'materials', today = clientToday()
const material = reactive({ ...emptyMaterial(), purchasedAt: today, receivedAt: today })
const acceptance = reactive({ ...emptyAcceptance(), materialId: props.selectedMaterial?.id || '', materialVersion: props.selectedMaterial?.version || 0, supplier: props.selectedMaterial?.supplier || '', manufacturer: props.selectedMaterial?.manufacturer || '', useDepartmentId: currentActor.value.departmentId, acceptedAt: today, acceptorId: currentActor.value.id })
const record = ref(props.row), materialName = ref(props.selectedMaterial?.name || ''), acceptor = ref(currentActor.value.name), keeper = ref('')
const loading = ref(false), busy = ref(false), ready = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>(''), picker = ref<'acceptorId' | 'keeperId'>()
const readonly = computed(() => props.mode === 'view' || busy.value)
const title = computed(() => picker.value ? picker.value === 'acceptorId' ? '选择验收人' : '选择保管人' : `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}${isMaterial ? '标准物质登记' : '物质验收'}`)
const departments = computed(() => registrationDepartments.filter(dept => currentActor.value.scope === 'all' || dept.id === currentActor.value.departmentId))
const pickerPerson = computed(() => picker.value && acceptance[picker.value] ? { id: acceptance[picker.value], name: picker.value === 'acceptorId' ? acceptor.value : keeper.value } : undefined)
const leave = useFormLeaveGuard(() => [material, acceptance], () => ['new', 'edit'].includes(props.mode) && ready.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; ready.value = false; error.value = ''
  try {
    if (props.mode === 'new' && !isMaterial) {
      const parent = await registrationDemo.referenceMaterialDetail(acceptance.materialId, request.signal)
      if (!alive || request.signal.aborted) return
      if (parent.accepted) throw new AppError('BUSINESS_RULE', `“${parent.name}”已验收，请关闭弹窗后查看验收记录。`)
      acceptance.materialVersion = parent.version; materialName.value = parent.name
      acceptance.supplier = parent.supplier; acceptance.manufacturer = parent.manufacturer
    } else if (props.row) {
      if (isMaterial) { const row = await registrationDemo.referenceMaterialDetail(props.row.id, request.signal); if (!alive || request.signal.aborted) return; record.value = row; Object.assign(material, row) }
      else { const row = await registrationDemo.materialAcceptanceDetail(props.row.id, request.signal); if (!alive || request.signal.aborted) return; record.value = row; Object.assign(acceptance, row); materialName.value = row.name; acceptor.value = row.acceptor; keeper.value = row.keeper }
    }
    ready.value = true
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function selectPerson(person: EntryPersonCandidate) {
  if (!picker.value) return
  const key = picker.value; acceptance[key] = person.id
  if (key === 'acceptorId') acceptor.value = person.name; else keeper.value = person.name
  picker.value = undefined
  await nextTick(); document.getElementById(`acceptance-${key}`)?.dispatchEvent(new Event('change', { bubbles: true }))
}
async function close() { if (busy.value) return; if (picker.value) picker.value = undefined; else await closeForm() }
async function save() {
  if (!ready.value || readonly.value || loading.value) return
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteMaterialRecord(props.kind, record.value!.id, record.value!.version, 'materialVersion' in record.value! ? record.value!.materialVersion : undefined)
    else {
      const identity = props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}
      if (isMaterial) await registrationDemo.saveReferenceMaterial({ ...material, ...identity })
      else await registrationDemo.saveMaterialAcceptance({ ...acceptance, ...identity })
    }
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) { error.value = normalizeError(issue); if (error.value.code === 'BUSINESS_RULE' || error.value.code === 'NOT_FOUND') emit('invalidated') } }
  finally { if (alive) busy.value = false }
}
if (props.mode === 'edit' || props.mode === 'view') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :size="mode === 'delete' ? undefined : 'xl'" :busy="busy" :loading="loading" scrollable :fill-height="!!picker" :body-class="picker ? 'p-0 overflow-hidden' : mode === 'delete' ? 'py-2' : undefined" @close="close">
    <DataEntryPersonPicker v-if="picker" embedded :title="title" purpose="reference-material" sample-id="" role="tester" :value="pickerPerson" @close="close" @select="selectPerson" />
    <div v-show="!picker">
      <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除{{ isMaterial ? '登记' : '验收' }}记录“{{ record?.name }}”？<span v-if="!isMaterial" class="d-block text-muted mt-2">删除后，关联登记将恢复为未验收。</span></p>
      <form v-else-if="ready" id="reference-material-form" @submit.prevent="save">
        <fieldset :disabled="readonly">
          <div v-if="isMaterial" class="row g-3">
            <div class="col-12 col-md-8"><label for="material-name" class="form-label">品名<span v-if="mode !== 'view'" class="text-danger ms-1">*</span></label><input id="material-name" v-model="material.name" data-validation-key="name" class="form-control" maxlength="200" /></div>
            <div class="col-12 col-md-4"><label for="material-specification" class="form-label">规格</label><input id="material-specification" v-model="material.specification" data-validation-key="specification" class="form-control" maxlength="200" /></div>
            <div v-for="field in [{ key: 'supplier', label: '供应单位' }, { key: 'manufacturer', label: '生产厂家' }] as const" :key="field.key" class="col-12 col-md-6"><label :for="`material-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`material-${field.key}`" v-model="material[field.key]" :data-validation-key="field.key" class="form-control" maxlength="200" /></div>
            <div class="col-12 col-md-4"><label for="material-purchasedAt" class="form-label">购置日期</label><TemplateDate id="material-purchasedAt" v-model="material.purchasedAt" data-validation-key="purchasedAt" within-modal :disabled="readonly" /></div>
            <div class="col-12 col-md-4"><label for="material-purchasedQuantity" class="form-label">购置数量</label><input id="material-purchasedQuantity" v-model.number="material.purchasedQuantity" type="number" step="any" min="0" data-validation-key="purchasedQuantity" class="form-control" /></div>
            <div class="col-12 col-md-4"><label for="material-purchaseStatus" class="form-label">购置状态</label><input id="material-purchaseStatus" v-model="material.purchaseStatus" data-validation-key="purchaseStatus" class="form-control" maxlength="200" /></div>
            <div class="col-12 col-md-4"><label for="material-receivedAt" class="form-label">领用日期</label><TemplateDate id="material-receivedAt" v-model="material.receivedAt" data-validation-key="receivedAt" within-modal :disabled="readonly" /></div>
            <div class="col-12 col-md-4"><label for="material-receivedQuantity" class="form-label">领用数量</label><input id="material-receivedQuantity" v-model.number="material.receivedQuantity" type="number" step="any" min="0" data-validation-key="receivedQuantity" class="form-control" /></div>
            <div class="col-12 col-md-4"><label for="material-validity" class="form-label">有效期</label><input id="material-validity" v-model="material.validity" data-validation-key="validity" class="form-control" maxlength="200" /></div>
            <div class="col-12"><label for="material-notes" class="form-label">备注</label><textarea id="material-notes" v-model="material.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="2000"></textarea></div>
          </div>
          <div v-else class="row g-3">
            <div class="col-12 col-md-4"><label for="acceptance-name" class="form-label">物质名称</label><input id="acceptance-name" :value="materialName" class="form-control bg-light" readonly /></div>
            <div class="col-12 col-md-4"><label for="acceptance-department" class="form-label">使用部门<span v-if="mode !== 'view'" class="text-danger ms-1">*</span></label><select id="acceptance-department" v-model="acceptance.useDepartmentId" data-validation-key="useDepartmentId" class="form-select"><option v-for="department in departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
            <div v-for="field in acceptanceTextFields.filter(field => field.key !== 'certificate')" :key="field.key" class="col-12 col-md-4"><label :for="`acceptance-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`acceptance-${field.key}`" v-model="acceptance[field.key]" :data-validation-key="field.key" class="form-control" maxlength="200" /></div>
            <div class="col-12 col-md-4"><label for="acceptance-status" class="form-label">验收状态<span v-if="mode !== 'view'" class="text-danger ms-1">*</span></label><select id="acceptance-status" v-model="acceptance.status" data-validation-key="status" class="form-select"><option value="">请选择</option><option v-for="status in acceptanceStatuses" :key="status">{{ status }}</option></select></div>
            <div class="col-12 col-md-4"><label for="acceptance-date" class="form-label">验收日期<span v-if="mode !== 'view'" class="text-danger ms-1">*</span></label><TemplateDate id="acceptance-date" v-model="acceptance.acceptedAt" data-validation-key="acceptedAt" within-modal :disabled="readonly" /></div>
            <div class="col-12 col-md-4"><label for="acceptance-certificate" class="form-label">相关证书</label><input id="acceptance-certificate" v-model="acceptance.certificate" data-validation-key="certificate" class="form-control" maxlength="200" /></div>
            <div v-for="field in [{ key: 'acceptorId', label: '验收人' }, { key: 'keeperId', label: '保管人' }] as const" :key="field.key" class="col-12 col-md-6"><label :for="`acceptance-${field.key}`" class="form-label">{{ field.label }}<span v-if="field.key === 'acceptorId' && mode !== 'view'" class="text-danger ms-1">*</span></label><div class="input-group"><input :id="`acceptance-${field.key}`" :value="field.key === 'acceptorId' ? acceptor : keeper" :data-validation-key="field.key" class="form-control bg-light" readonly /><button v-if="mode !== 'view'" type="button" class="btn btn-light" :aria-label="`选择${field.label}`" @click="picker = field.key"><i class="ti ti-search" aria-hidden="true"></i></button></div></div>
            <div class="col-12"><label for="acceptance-notes" class="form-label">备注</label><textarea id="acceptance-notes" v-model="acceptance.notes" data-validation-key="notes" class="form-control" rows="2" maxlength="2000"></textarea></div>
          </div>
        </fieldset>
      </form>
      <ErrorNotice :error="error" :retry="!ready" :busy="busy || loading" :class="{ 'mt-3': error && ready }" @retry="load" />
    </div>
    <template v-if="!picker" #footer><button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ mode === 'view' ? '返回' : '取消' }}</button><button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !ready" @click="save">{{ busy ? '正在删除…' : '确认删除' }}</button><button v-else-if="mode !== 'view'" type="submit" form="reference-material-form" class="btn btn-primary" :disabled="busy || loading || !ready">{{ busy ? '正在保存…' : '保存' }}</button></template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
