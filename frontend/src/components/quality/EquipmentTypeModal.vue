<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EquipmentTypeRow } from '../../types/quality/equipmentTypes'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: EquipmentTypeRow }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const record = ref(props.row), name = ref(''), lendable = ref(true), notes = ref(''), loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'new' || props.mode === 'delete'), error = ref<ErrorValue>('')
const title = computed(() => `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}设备类型`)
const leave = useFormLeaveGuard(() => [name.value, lendable.value, notes.value], () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.row || busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false
  try {
    const result = await registrationDemo.equipmentTypeDetail(props.row.id, request.signal)
    if (alive && !request.signal.aborted) { record.value = result; name.value = result.name; lendable.value = result.lendable; notes.value = result.notes; loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save() {
  if (busy.value || loading.value || !loaded.value || props.mode === 'view') return
  if (props.mode !== 'delete' && !name.value.trim()) { error.value = new AppError('VALIDATION', '请填写设备类型。', { fieldErrors: { name: '请填写设备类型。' } }); return }
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteEquipmentType(record.value!.id, record.value!.version)
    else await registrationDemo.saveEquipmentType({ name: name.value.trim(), lendable: lendable.value, notes: notes.value, ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode === 'view' || props.mode === 'edit') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :size="mode === 'delete' ? undefined : 'lg'" :busy="busy" :loading="loading" scrollable :body-class="mode === 'delete' ? 'py-2' : undefined" @close="closeForm">
    <template v-if="mode === 'delete'"><p class="text-break">确认删除设备类型“{{ record?.name }}”？</p><p class="text-muted mb-0">已被设备台账引用的类型无法删除。</p></template>
    <form v-else-if="loaded" id="equipment-type-form" @submit.prevent="save">
      <fieldset :disabled="mode === 'view' || busy" class="row g-3">
        <div class="col-12 col-sm-8"><label for="equipment-type-name" class="form-label">设备类型<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><input id="equipment-type-name" data-validation-key="name" v-model="name" class="form-control" required maxlength="200" /></div>
        <div class="col-12 col-sm-4"><span class="form-label d-none d-sm-block invisible" aria-hidden="true">选项</span><label class="form-check py-2 mb-0"><input v-model="lendable" data-validation-key="lendable" type="checkbox" class="form-check-input" /><span class="form-check-label">是否可借出</span></label></div>
        <div class="col-12"><label for="equipment-type-notes" class="form-label">备注</label><textarea id="equipment-type-notes" v-model="notes" data-validation-key="notes" class="form-control" rows="2" maxlength="2000"></textarea></div>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" :class="{ 'mt-3': loaded && error }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button>
      <button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !loaded" @click="save"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在删除…' : '确认删除' }}</button>
      <button v-else-if="mode !== 'view'" type="submit" form="equipment-type-form" class="btn btn-primary" :disabled="busy || loading || !loaded"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
