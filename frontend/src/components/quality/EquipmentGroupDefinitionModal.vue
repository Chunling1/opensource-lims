<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { canManageDefinitions, definitionSubject, type DefinitionModule, type EquipmentGroupRow } from '../../types/quality/equipmentGroups'
const props = withDefaults(defineProps<{ definitionModule?: DefinitionModule; mode: 'new' | 'edit' | 'view' | 'delete'; row?: EquipmentGroupRow }>(), { definitionModule: 'equipment' })
const emit = defineEmits<{ close: []; saved: [] }>()
const record = ref(props.row), name = ref(''), loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>('')
const subject = computed(() => definitionSubject(props.definitionModule))
const title = computed(() => `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}${subject.value}`)
const department = computed(() => record.value?.department ?? registrationDepartments.find(item => item.id === currentActor.value.departmentId)?.name ?? '无')
const leave = useFormLeaveGuard(() => name.value, () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.row || busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false
  try {
    const result = await registrationDemo.equipmentGroupDetail(props.row.id, request.signal, props.definitionModule)
    if (alive && !request.signal.aborted) { record.value = result; name.value = result.name; loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save() {
  if (!canManageDefinitions(currentActor.value) || busy.value || loading.value || !loaded.value || props.mode === 'view') return
  if (props.mode !== 'delete' && !name.value.trim()) { error.value = new AppError('VALIDATION', '请填写列表项值。', { fieldErrors: { name: '请填写列表项值。' } }); return }
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteEquipmentGroupDefinition(record.value!.id, record.value!.version, props.definitionModule)
    else await registrationDemo.saveEquipmentGroupDefinition({ name: name.value.trim(), ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) }, props.definitionModule)
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode === 'view' || props.mode === 'edit') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :busy="busy" :loading="loading" scrollable :body-class="mode === 'delete' ? 'py-2' : undefined" @close="closeForm">
    <template v-if="mode === 'delete'"><p class="text-break">确认删除{{ subject }}“{{ record?.name }}”？</p><p v-if="definitionModule === 'equipment'" class="text-muted mb-0">同时解除该分组与设备的关联，不删除设备。</p><p v-else class="text-muted mb-0">同时解除该分组与检测标准的关联，不删除检测标准。</p></template>
    <form v-else-if="loaded" id="equipment-group-form" @submit.prevent="save">
      <div class="mb-3"><label for="equipment-group-department" class="form-label">部门</label><input id="equipment-group-department" class="form-control" :value="department" disabled /></div>
      <div><label for="equipment-group-name" class="form-label">列表项值<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><input id="equipment-group-name" data-validation-key="name" v-model="name" class="form-control" required maxlength="200" :disabled="mode === 'view' || busy" /></div>
    </form>
    <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" :class="{ 'mt-3': loaded && error }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button>
      <button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !loaded" @click="save"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在删除…' : '确认删除' }}</button>
      <button v-else-if="mode !== 'view'" type="submit" form="equipment-group-form" class="btn btn-primary" :disabled="busy || loading || !loaded"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
