<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import DataTable from '../common/table/DataTable.vue'
import TestEnvironmentPlanPicker from './TestEnvironmentPlanPicker.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { canManageDefinitions } from '../../types/quality/equipmentGroups'
import { environmentPlanColumns, type TestEnvironment, type EnvironmentPlan } from '../../types/quality/testEnvironments'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: TestEnvironment }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const record = ref(props.row), name = ref(''), plans = ref<EnvironmentPlan[]>([]), options = ref<EnvironmentPlan[]>([]), selected = ref<string[]>([])
const loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'delete'), error = ref<ErrorValue>(''), choosing = ref(false)
const picker = ref<InstanceType<typeof TestEnvironmentPlanPicker>>()
const planKeyword = ref(''), planQuery = ref('')
function openPicker() { planKeyword.value = ''; planQuery.value = ''; choosing.value = true }
const title = computed(() => choosing.value ? '关联检测方案' : `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}试验环境`)
const readonly = computed(() => props.mode === 'view' || busy.value || !canManageDefinitions(currentActor.value))
const canSelect = (row: EnvironmentPlan) => !readonly.value && options.value.some(item => item.id === row.id)
const leave = useFormLeaveGuard(() => [name.value, plans.value], () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false; choosing.value = false; selected.value = []
  try {
    const results = await Promise.allSettled([registrationDemo.testEnvironmentPlans(request.signal), props.row ? registrationDemo.testEnvironmentDetail(props.row.id, request.signal) : Promise.resolve(undefined)])
    if (!alive || request.signal.aborted) return
    const failed = results.find(result => result.status === 'rejected')
    if (failed?.status === 'rejected') throw failed.reason
    const [catalogue, detail] = results
    if (catalogue.status === 'fulfilled') options.value = catalogue.value
    if (detail.status === 'fulfilled' && detail.value) { record.value = detail.value; name.value = detail.value.name; plans.value = detail.value.plans }
    loaded.value = true
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save() {
  if (readonly.value || loading.value || !loaded.value || choosing.value) return
  if (props.mode !== 'delete' && !name.value.trim()) { error.value = new AppError('VALIDATION', '请填写试验环境描述。', { fieldErrors: { name: '请填写试验环境描述。' } }); return }
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteTestEnvironment(record.value!.id, record.value!.version)
    else await registrationDemo.saveTestEnvironment({ name: name.value.trim(), planIds: plans.value.map(row => row.id), ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
async function close() { if (busy.value) return; if (choosing.value) choosing.value = false; else await closeForm() }
if (props.mode !== 'delete') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal open :title="title" :size="mode === 'delete' ? undefined : choosing ? 'xl' : 'lg'" :busy="busy" :loading="loading" guard-close scrollable fullscreen-mobile :fill-height="choosing" :body-class="choosing ? 'px-3 pt-0 overflow-auto' : undefined" @close="close">
    <template v-if="choosing" #toolbar>
      <form class="mb-3" aria-label="检测方案查询" @submit.prevent="planQuery = planKeyword.trim().toLocaleLowerCase()">
        <div class="row gx-3 gy-2 align-items-center">
          <div class="col d-flex align-items-center gap-2"><label for="environment-plan-search" class="col-form-label text-nowrap">检测方案</label><input id="environment-plan-search" v-model="planKeyword" class="form-control" size="1" placeholder="方案名称或代码" maxlength="200" /></div>
          <div class="col-auto"><button type="submit" class="btn btn-primary">查询</button></div>
        </div>
      </form>
    </template>
    <TestEnvironmentPlanPicker v-if="choosing" :query="planQuery" ref="picker" :options="options" :value="plans" @select="plans = $event; selected = []; choosing = false" />
    <template v-else-if="mode === 'delete'"><p class="text-break">确认删除试验环境“{{ record?.name }}”？</p><p class="text-muted mb-0">同时解除检测方案关联，不删除检测方案。</p></template>
    <form v-else-if="loaded" id="test-environment-form" @submit.prevent="save">
      <div class="mb-3"><label for="environment-name" class="form-label">试验环境描述<span v-if="mode !== 'view'" class="text-danger ms-1" aria-hidden="true">*</span></label><input id="environment-name" data-validation-key="name" v-model="name" class="form-control" required maxlength="200" :disabled="readonly" /></div>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3"><h6 class="mb-0">检测方案 <span class="badge bg-light text-body">{{ plans.length }}</span></h6><div v-if="mode !== 'view'" class="d-flex gap-2"><button type="button" class="btn btn-primary" :disabled="readonly" @click="openPicker">关联检测方案</button><button type="button" class="btn btn-light" :disabled="readonly || !selected.length" @click="plans = plans.filter(row => !canSelect(row) || !selected.includes(row.id)); selected = []">移除关联</button></div></div>
      <DataTable label="关联检测方案" :rows="plans" :columns="environmentPlanColumns" :row-key="row => row.id" :row-label="row => row.name" :selected="mode === 'view' ? undefined : selected" :selectable="canSelect" @update:selected="selected = $event" />
    </form>
    <ErrorNotice v-if="!choosing" :error="error" :retry="!loaded" :busy="loading || busy" :class="{ 'mt-3': loaded && error }" @retry="load" />
    <template #footer>
      <span v-if="choosing" class="me-auto text-muted">已选 {{ picker?.selectedCount ?? plans.length }} 个检测方案</span>
      <button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ mode === 'view' ? '返回' : '取消' }}</button>
      <button v-if="choosing" type="button" class="btn btn-primary" @click="picker?.confirm()">确定</button>
      <button v-else-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="readonly || loading || !loaded" @click="save">{{ busy ? '正在删除…' : '确认删除' }}</button>
      <button v-else-if="mode !== 'view'" type="submit" form="test-environment-form" class="btn btn-primary" :disabled="readonly || loading || !loaded">{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
