<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EquipmentGroupContext, EquipmentGroupState } from '../../types/quality/equipmentGroups'

const props = defineProps<{ ids: string[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const data = ref<EquipmentGroupContext>(), states = ref<Record<string, EquipmentGroupState>>({})
const loading = ref(false), busy = ref(false), error = ref<ErrorValue>('')
const changed = computed(() => data.value?.groups.some(group => states.value[group.id] !== group.state) || false)
const leave = useFormLeaveGuard(() => states.value, () => !!data.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (busy.value || loading.value) return
  const request = controller = new AbortController()
  loading.value = true; error.value = ''
  try {
    const result = await registrationDemo.standardGroupContext(props.ids, request.signal)
    if (alive) { data.value = result; states.value = Object.fromEntries(result.groups.map(group => [group.id, group.state])) }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) loading.value = false }
}
function toggle(id: string, checked: boolean) {
  if (!loading.value && !busy.value) states.value[id] = checked ? 'checked' : 'unchecked'
}
async function save() {
  if (!data.value || !changed.value || loading.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    await registrationDemo.saveStandardGroups({ records: data.value.records, groups: data.value.groups.map(group => ({ id: group.id, version: group.version, state: states.value[group.id]! })) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
onBeforeUnmount(() => { alive = false; controller?.abort() })
void load()
</script>
<template>
  <BootstrapModal guard-close open title="分组关联" scrollable :loading="loading" :busy="busy" body-class="py-2" @close="closeForm">
    <template #toolbar><p class="text-muted mb-0">已选 {{ ids.length }} 条标准</p></template>
    <div v-if="data" class="table-responsive border rounded">
      <table class="table table-hover align-middle mb-0" aria-label="标准分组列表">
        <thead class="table-light"><tr><th scope="col">分组名称</th></tr></thead>
        <tbody>
          <tr v-for="group in data.groups" :key="group.id"><td><div class="d-flex align-items-center gap-2"><input type="checkbox" class="form-check-input m-0 flex-shrink-0" :aria-label="group.name" :aria-checked="states[group.id] === 'mixed' ? 'mixed' : states[group.id] === 'checked'" :checked="states[group.id] === 'checked'" :indeterminate="states[group.id] === 'mixed'" :disabled="busy || loading" @change="toggle(group.id, ($event.target as HTMLInputElement).checked)" /><span class="text-break">{{ group.name }}</span></div></td></tr>
          <tr v-if="!data.groups.length"><td class="text-center text-muted py-4">暂无标准分组</td></tr>
        </tbody>
      </table>
    </div>
    <ErrorNotice :error="error" :retry="!data" :busy="loading || busy" class="mt-3" @retry="load" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">取消</button><button type="button" class="btn btn-primary" :disabled="busy || loading || !changed" @click="save"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '确认' }}</button></template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
