<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import EquipmentCalibrationPlanModal from '../../components/quality/EquipmentCalibrationPlanModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { overallPlanSearchFields, overallPlanOperators } from '../../types/quality/equipmentOverallPlan'
import { calibrationPlanColumns, type CalibrationPlanQuery, type CalibrationPlanPage, type CalibrationPlanRow } from '../../types/quality/equipmentCalibrationPlan'
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const currentYearDates = () => ({ from: `${new Date().getFullYear()}-01-01`, to: `${new Date().getFullYear()}-12-31` })
const query = computed<CalibrationPlanQuery>(() => ({ field: text('field', 'code') as CalibrationPlanQuery['field'], operator: text('operator', 'contains') as CalibrationPlanQuery['operator'], value: text('value'), from: text('from', currentYearDates().from), to: text('to', currentYearDates().to), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ field: 'code', operator: 'contains', value: '', from: '', to: '' }), dates = ref<InstanceType<typeof TemplateDateRange>>()
watch(query, value => Object.assign(draft, { field: value.field, operator: value.operator, value: value.value, from: value.from, to: value.to }), { immediate: true })
const data = ref<CalibrationPlanPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), error = ref<ErrorValue>(''), modal = ref<{ mode: 'edit' | 'view'; row: CalibrationPlanRow }>()
const columnKeys = computed(() => parseTableColumns(calibrationPlanColumns, route.query.columns))
const columns = computed(() => calibrationPlanColumns.filter(column => columnKeys.value.includes(column.key)))
const exporting = ref(false), outputError = ref<ErrorValue>('')
const canWrite = computed(() => currentActor.value.roles.some(role => ['admin', 'quality'].includes(role)))
const toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, outputEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.calibrationPlans(query.value, request.signal); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value || !dates.value?.validate()) return
  const previous = route.fullPath
  await patch({ field: draft.field, operator: draft.operator, value: draft.value.trim() || undefined, from: draft.from, to: draft.to, page: '1' })
  if (previous === route.fullPath) void load()
}
async function saved(submitted: boolean) {
  message.value = submitted ? '已提交检定信息。' : '已保存检定计划。'; modal.value = undefined
  void load(); await nextTick(); toast.value?.show()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function output(onlySelected: boolean) {
  if (loading.value || error.value || exporting.value || onlySelected && !selected.value.length) return
  const token = ++outputEpoch; exporting.value = true; outputError.value = ''
  try {
    const blob = await registrationDemo.exportCalibrationPlans({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) })
    if (token === outputEpoch) downloadBlob(blob, '计量器具周期检定计划.csv')
  } catch (issue) { if (token === outputEpoch) outputError.value = normalizeError(issue) }
  finally { if (token === outputEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (values, old) => {
  outputEpoch++; exporting.value = false; outputError.value = ''
  if (old && values[1] !== old[1]) { modal.value = undefined; data.value.items = [] }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; outputEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading title="计量器具周期检定计划" />
  <section class="card" aria-label="计量器具周期检定计划列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">计量器具周期检定计划</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar label="计量器具周期检定计划" :columns="calibrationPlanColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="output($event)" />
    </div>
    <form class="card-body border-bottom" aria-label="计量器具周期检定计划查询" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3">
        <div class="col-12 col-sm-6 col-xl-3"><label for="calibration-filter-field" class="form-label">查询字段</label><select id="calibration-filter-field" v-model="draft.field" class="form-select"><option v-for="field in overallPlanSearchFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="calibration-filter-operator" class="form-label">匹配方式</label><select id="calibration-filter-operator" v-model="draft.operator" class="form-select"><option v-for="operator in overallPlanOperators" :key="operator.key" :value="operator.key">{{ operator.label }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="calibration-filter-value" class="form-label">查询值</label><input id="calibration-filter-value" v-model="draft.value" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="calibration-filter-date" class="form-label">检定日期</label><TemplateDateRange id="calibration-filter-date" ref="dates" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
      </div>
      <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="outputError" class="px-3 pt-3"><ErrorNotice :error="outputError" /></div>
    <DataTable label="计量器具周期检定计划" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>检定</button>
      </template>
    </DataTable>
  </section>
  <EquipmentCalibrationPlanModal v-if="modal" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <TemplateToast ref="toast" :message="message" />
</template>
