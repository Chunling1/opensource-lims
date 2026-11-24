<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { clientMonthRange } from '../../services/common/date'
import { downloadBlob } from '../../services/reports/reportPdf'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { equipmentLoanRecordColumns, loanRecordDateFields, loanRecordSearchFields, type EquipmentLoanQuery, type EquipmentLoanPage } from '../../types/quality/equipmentLoans'

const route = useRoute(), router = useRouter(), label = '领用与归还记录'
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const initialDates = clientMonthRange()
const query = computed<EquipmentLoanQuery>(() => ({ status: 'all', dateField: text('dateField') as EquipmentLoanQuery['dateField'], from: text('from', initialDates.from), to: text('to', initialDates.to), field: text('field') as EquipmentLoanQuery['field'], value: text('value'), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ dateField: '', ...initialDates, field: '', value: '' }), dates = ref<InstanceType<typeof TemplateDateRange>>()
watch(query, value => Object.assign(draft, { dateField: value.dateField, from: value.from, to: value.to, field: value.field, value: value.value }), { immediate: true })
const data = ref<EquipmentLoanPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), exporting = ref(false), error = ref<ErrorValue>(''), outputError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(equipmentLoanRecordColumns, route.query.columns))
const columns = computed(() => equipmentLoanRecordColumns.filter(column => columnKeys.value.includes(column.key)))
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, outputEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.equipmentLoans('records', query.value, request.signal); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value || draft.dateField && !dates.value?.validate()) return
  const previous = route.fullPath
  await patch({ dateField: draft.dateField || undefined, from: draft.from, to: draft.to, field: draft.field || undefined, value: draft.field ? draft.value.trim() || undefined : undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function output(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++outputEpoch; exporting.value = true; outputError.value = ''
  try { const blob = await registrationDemo.exportEquipmentLoanRecords({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }); if (token === outputEpoch) downloadBlob(blob, `${label}.csv`) }
  catch (issue) { if (token === outputEpoch) outputError.value = normalizeError(issue) }
  finally { if (token === outputEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (values, previous) => {
  outputEpoch++; exporting.value = false; outputError.value = ''; if (previous && values[1] !== previous[1]) data.value.items = []; void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; outputEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="label" />
  <section class="card" aria-label="领用与归还记录列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ label }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar :label="label" :columns="equipmentLoanRecordColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="output" />
    </div>
    <form class="card-body border-bottom" aria-label="领用与归还记录查询" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3">
        <div class="col-12 col-sm-6 col-xl-2"><label for="loan-record-date-field" class="form-label">日期类型</label><select id="loan-record-date-field" v-model="draft.dateField" class="form-select"><option value="">不限</option><option v-for="field in loanRecordDateFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-4"><label for="loan-record-dates" class="form-label">日期范围</label><TemplateDateRange id="loan-record-dates" ref="dates" :from="draft.from" :to="draft.to" :disabled="!draft.dateField" @change="Object.assign(draft, $event)" /></div>
        <div class="col-12 col-sm-6 col-xl-2"><label for="loan-record-field" class="form-label">查询内容</label><select id="loan-record-field" v-model="draft.field" class="form-select"><option value="">不限</option><option v-for="field in loanRecordSearchFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-4"><label for="loan-record-value" class="form-label">包含</label><input id="loan-record-value" v-model="draft.value" class="form-control" maxlength="200" :disabled="!draft.field" /></div>
      </div>
      <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="outputError" class="px-3 pt-3"><ErrorNotice :error="outputError" /></div>
    <DataTable :label="label" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" />
  </section>
</template>
