<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import SingleChoice from '../common/SingleChoice.vue'
import TablePagination from '../common/table/TablePagination.vue'
import AdaptiveTableActions from '../common/table/AdaptiveTableActions.vue'
import { emptySampleSubproject, sampleSubprojectFields, sampleSubprojectReceiptTypes, type SampleSubproject, type SampleSubprojectOption } from '../../types/commissions/sampleForm'

const props = defineProps<{ modelValue: SampleSubproject[]; options: SampleSubprojectOption[]; readonly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [SampleSubproject[]] }>()
const selectedId = ref(''), page = ref(1), pageSize = ref(5)
const mode = ref<'' | 'add' | 'edit' | 'view' | 'delete'>(''), draft = ref(emptySampleSubproject())
const selected = computed(() => props.modelValue.find(row => row.id === selectedId.value))
const toolbarActions = computed(() => [
  { label: '修改', icon: 'ti ti-edit', disabled: props.readonly || !selected.value },
  { label: '删除', icon: 'ti ti-trash', disabled: props.readonly || !selected.value },
  { label: '查看', icon: 'ti ti-eye', disabled: !selected.value },
])
function toolbarAction(index: number) { open((['edit', 'delete', 'view'] as const)[index]!) }
const rows = computed(() => props.modelValue.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const titles = { add: '新增子项目', edit: '修改子项目', view: '查看子项目', delete: '删除子项目' }
function open(action: Exclude<typeof mode.value, ''>) {
  if (action !== 'add' && !selected.value || props.readonly && action !== 'view') return
  draft.value = action === 'add' ? { ...emptySampleSubproject(), id: crypto.randomUUID() } : { ...selected.value! }
  mode.value = action
}
function chooseName() {
  if (props.readonly || mode.value === 'view') return
  const option = props.options.find(item => item.name === draft.value.name)
  draft.value.accountingDepartment = option?.accountingDepartment || ''
  draft.value.businessCategory = option?.businessCategory || ''
}
function save() {
  if (props.readonly || !['add', 'edit'].includes(mode.value)) return
  const row = { ...draft.value, name: draft.value.name.trim() }
  if (!props.options.some(option => option.name === row.name)) return
  const result = mode.value === 'add' ? [...props.modelValue, row] : props.modelValue.map(item => item.id === row.id ? row : item)
  emit('update:modelValue', result); selectedId.value = row.id
  if (mode.value === 'add') page.value = Math.ceil(result.length / pageSize.value)
  mode.value = ''
}
function remove() { if (!props.readonly) emit('update:modelValue', props.modelValue.filter(row => row.id !== draft.value.id)); mode.value = '' }
function money(value: string) { return value === '' ? '—' : Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
watch(() => props.modelValue, value => { page.value = Math.min(page.value, Math.max(1, Math.ceil(value.length / pageSize.value))); if (!value.some(row => row.id === selectedId.value)) selectedId.value = '' })
watch(() => props.readonly, () => { mode.value = '' })
</script>

<template>
  <div class="d-flex mb-3">
    <AdaptiveTableActions label="子项目" :actions="toolbarActions" :table-controls="false" @action="toolbarAction">
    <button type="button" class="btn btn-primary" :disabled="readonly || modelValue.length >= 200" @click="open('add')"><i class="ti ti-plus me-1" aria-hidden="true"></i>增加</button>
    </AdaptiveTableActions>
  </div>
  <div class="table-responsive">
    <table class="table table-striped table-hover table-nowrap align-middle mb-0" aria-label="子项目明细">
      <thead class="table-light"><tr><th scope="col" aria-label="选择"></th><th scope="col">序号</th><th v-for="field in sampleSubprojectFields" :key="field.key" scope="col" :class="{ 'text-end': 'money' in field }">{{ field.label }}</th></tr></thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="row.id" :class="{ 'table-active': selectedId === row.id }">
          <td><SingleChoice name="sample-subproject" :value="row.id" :checked="selectedId === row.id" :label="`选择子项目 ${row.name}`" @change="selectedId = row.id" /></td><td>{{ (page - 1) * pageSize + index + 1 }}</td>
          <td v-for="field in sampleSubprojectFields" :key="field.key" :class="{ 'text-end': 'money' in field }">{{ 'money' in field ? money(row[field.key]) : row[field.key] || '—' }}</td>
        </tr>
        <tr v-if="!rows.length"><td colspan="10" class="text-center text-muted py-4">暂无子项目</td></tr>
      </tbody>
    </table>
  </div>
  <TablePagination label="子项目" :total="modelValue.length" :page="page" :page-size="pageSize" :sizes="[5, 10, 20]" @page="page = $event" @size="pageSize = $event; page = 1" />
  <BootstrapModal :open="!!mode" :title="mode ? titles[mode] : ''" size="lg" scrollable fullscreen-mobile @close="mode = ''">
    <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除子项目“{{ draft.name }}”？</p>
    <form v-else id="sample-subproject-form" class="row g-3" @submit.prevent="save">
      <div v-for="field in sampleSubprojectFields" :key="field.key" :class="field.key === 'notes' ? 'col-12' : 'col-md-6'">
        <label class="form-label" :for="`subproject-${field.key}`">{{ field.label }}<span v-if="field.key === 'name' && mode !== 'view'" class="text-danger"> *</span></label>
        <select v-if="field.key === 'name'" :id="`subproject-${field.key}`" v-model="draft.name" class="form-select" required :disabled="mode === 'view'" @change="chooseName"><option value="">请选择</option><option v-for="option in options" :key="option.name">{{ option.name }}</option></select>
        <textarea v-else-if="field.key === 'notes'" :id="`subproject-${field.key}`" v-model="draft.notes" class="form-control" rows="2" maxlength="500" :readonly="mode === 'view'"></textarea>
        <select v-else-if="field.key === 'receiptType'" :id="`subproject-${field.key}`" v-model="draft.receiptType" class="form-select" :disabled="mode === 'view'"><option value="">请选择</option><option v-for="type in sampleSubprojectReceiptTypes" :key="type">{{ type }}</option></select>
        <input v-else :id="`subproject-${field.key}`" :value="draft[field.key]" class="form-control" @input="draft[field.key] = ($event.target as HTMLInputElement).value" :type="'money' in field ? 'number' : 'text'" :min="'money' in field ? 0 : undefined" :max="'money' in field ? '999999999999.99' : undefined" :step="'money' in field ? '0.01' : undefined" maxlength="500" :readonly="mode === 'view'" />
      </div>
    </form>
    <template #footer><button class="btn btn-light" type="button" @click="mode = ''">{{ mode === 'view' ? '返回' : '取消' }}</button><button v-if="mode === 'delete'" class="btn btn-danger" type="button" @click="remove">确认删除</button><button v-else-if="mode !== 'view'" class="btn btn-primary" type="submit" form="sample-subproject-form">确定</button></template>
  </BootstrapModal>
</template>
