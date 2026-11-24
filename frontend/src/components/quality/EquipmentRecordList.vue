<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DataTable from '../common/table/DataTable.vue'
import AdaptiveTableActions from '../common/table/AdaptiveTableActions.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { downloadBlob, printTablePdf } from '../../services/reports/reportPdf'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EquipmentHistory } from '../../types/quality/equipmentForm'
import type { TableColumn } from '../../types/common/table'
const props = defineProps<{ label: string; rows: EquipmentHistory[]; columns: readonly TableColumn[]; readonly?: boolean; projects?: boolean; reports?: boolean; selectedOnly?: boolean; busy?: boolean; createDisabled?: boolean }>()
const emit = defineEmits<{ new: []; view: [EquipmentHistory]; remove: [string[]] }>()
const selected = ref<string[]>([]), page = ref(1), size = ref(5), error = ref<ErrorValue>(''), printing = ref(false)
const outputDisabled = computed(() => !!props.busy || !props.rows.length || !!props.selectedOnly && !selected.value.length)
const outputHint = computed(() => props.selectedOnly && !selected.value.length ? '请先勾选需要操作的记录' : undefined)
const deleteActions = computed(() => props.readonly ? [] : [{ label: '删除', icon: 'ti ti-trash', disabled: props.busy || !selected.value.length }])
const actions = computed(() => props.reports ? [] : props.projects ? deleteActions.value : [
  ...deleteActions.value, { label: '查看', icon: 'ti ti-eye', disabled: selected.value.length !== 1 },
  { label: '打印', icon: 'ti ti-printer', disabled: printing.value || outputDisabled.value, hint: outputHint.value }, { label: '导出', icon: 'ti ti-download', disabled: outputDisabled.value, hint: outputHint.value },
])
async function action(index: number) {
  const item = actions.value[index]
  if (!item || item.disabled) return
  const label = item.label, rows = selected.value.length || props.selectedOnly ? props.rows.filter(r => selected.value.includes(r.id)) : props.rows
  if (label === '删除') { emit('remove', [...selected.value]); return }
  if (label === '查看') { emit('view', rows[0]!); return }
  const values = rows.map(row => props.columns.map(c => row[c.key] || '')), headers = props.columns.map(c => c.label)
  error.value = ''
  try {
    if (label === '打印') { printing.value = true; await printTablePdf(props.label, headers, values) }
    else { const cell = (value: string) => `"${value.replace(/^[\s]*[=+@-]/, "'$&").replaceAll('"', '""')}"`; downloadBlob(new Blob(['\uFEFF', [headers, ...values].map(row => row.map(cell).join(',')).join('\r\n')], { type: 'text/csv;charset=utf-8' }), `${props.label}.csv`) }
  } catch (issue) { error.value = normalizeError(issue) } finally { printing.value = false }
}
watch(() => props.rows, () => { selected.value = selected.value.filter(id => props.rows.some(r => r.id === id)); page.value = Math.min(page.value, Math.max(1, Math.ceil(props.rows.length / size.value))) }, { deep: true })
</script>
<template>
  <section :aria-label="label"><div :inert="busy" class="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-3"><h6 class="mb-0">{{ label }} <span class="badge bg-light text-body">{{ rows.length }}</span></h6><AdaptiveTableActions v-if="!reports" :label="label" :actions="actions" :table-controls="false" @action="action"><template v-if="!readonly && !reports" #default><button class="btn btn-primary text-nowrap" type="button" :disabled="busy || createDisabled" @click="$emit('new')"><i class="ti ti-plus me-1" aria-hidden="true"></i>{{ projects ? '选择方案' : '新增' }}</button></template></AdaptiveTableActions></div>
    <ErrorNotice :error="error" />
    <slot name="confirmation" />
    <div :inert="busy"><DataTable :label="label" :rows="rows.slice((page - 1) * size, page * size)" :columns="columns" :row-key="r => r.id" :row-label="r => columns.map(c => r[c.key]).filter(Boolean).join(' ')" :selected="reports ? undefined : selected" @update:selected="selected = $event" :pagination="{ total: rows.length, page, pageSize: size, sizes: [5, 10, 20] }" @page="page = $event; selected = []" @size="size = $event; page = 1; selected = []" /></div>
  </section>
</template>
