<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import TemplateMonth from '../../components/common/TemplateMonth.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
import { equipmentLedgerColumns, equipmentStatusClasses, type EquipmentLedgerPage } from '../../types/quality/equipmentLedger'
import type { MonthlyCalibrationQuery } from '../../types/quality/monthlyCalibration'

const props = defineProps<{ departmentMode?: boolean }>()
const title = computed(() => props.departmentMode ? '月检定计划[部门]' : '月检定计划')
const route = useRoute(), router = useRouter(), today = clientToday()
const currentYear = Number(today.slice(0, 4)), currentMonth = Number(today.slice(5, 7))
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<MonthlyCalibrationQuery>(() => ({
  year: Number(text('year', String(currentYear))), month: Number(text('month', String(currentMonth))),
  code: text('code'), name: text('name'), manufacturer: text('manufacturer'), serial: text('serial'), departmentId: text('departmentId'), ownDepartment: props.departmentMode || text('ownDepartment') === '1',
  sort: text('sort', 'code'), direction: text('direction') === 'desc' ? 'desc' : 'asc', page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10,
}))
const draft = reactive({ year: currentYear, month: currentMonth, code: '', name: '', manufacturer: '', serial: '', departmentId: '', ownDepartment: false })
watch(query, q => { for (const key of Object.keys(draft) as (keyof typeof draft)[]) Object.assign(draft, { [key]: q[key] }) }, { immediate: true })
const monthValue = computed({ get: () => `${draft.year}-${String(draft.month).padStart(2, '0')}`, set: (value: string) => { const [year, month] = value.split('-').map(Number); draft.year = year!; draft.month = month! } })
const fields = [{ key: 'manufacturer', label: '生产厂家' }, { key: 'serial', label: '仪器出厂号' }] as const
const more = ref(false), activeFilters = computed(() => [draft.manufacturer, draft.serial, draft.departmentId, draft.ownDepartment].filter(Boolean).length)
const rows = ref<EquipmentLedgerPage>({ items: [], total: 0, page: 1, pageSize: 10, departments: [] })
const selected = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>(''), exportError = ref<ErrorValue>(''), exporting = ref(false)
const columnKeys = computed(() => parseTableColumns(equipmentLedgerColumns, route.query.columns))
const columns = computed(() => equipmentLedgerColumns.filter(column => columnKeys.value.includes(column.key)))
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const active = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.monthlyCalibration(query.value, active.signal, props.departmentMode); if (token === epoch) rows.value = result }
  catch (issue) { if (token === epoch && !active.signal.aborted) { error.value = normalizeError(issue); rows.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  if (props.departmentMode) draft.ownDepartment = true
  const previous = route.fullPath
  await patch({ year: String(draft.year), month: String(draft.month), code: draft.code.trim() || undefined, name: draft.name.trim() || undefined, manufacturer: draft.manufacturer.trim() || undefined, serial: draft.serial.trim() || undefined, departmentId: draft.departmentId || undefined, ownDepartment: draft.ownDepartment ? '1' : undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try {
    const blob = await registrationDemo.exportMonthlyCalibration({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }, props.departmentMode)
    if (token === exportEpoch) downloadBlob(blob, `${title.value}-${query.value.year}-${String(query.value.month).padStart(2, '0')}.csv`)
  } catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => route.path], (values, old) => {
  exportEpoch++; exporting.value = false; exportError.value = ''
  if (old && (values[1] !== old[1] || values[2] !== old[2])) { rows.value.items = []; rows.value.departments = []; more.value = false }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar label="月检定计划" :columns="equipmentLedgerColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows" />
    </div>
    <form class="card-body border-bottom" aria-label="月检定计划查询" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-start">
          <div class="col-12 col-sm-6 col-xl-4"><label for="monthly-period" class="form-label">年月</label><TemplateMonth id="monthly-period" v-model="monthValue" required /></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="monthly-code" class="form-label">档案号</label><input id="monthly-code" v-model="draft.code" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="monthly-name" class="form-label">仪器设备名称</label><input id="monthly-name" v-model="draft.name" class="form-control" maxlength="200" /></div>
        </div>
        <div v-show="more" id="monthly-more-filters" class="row g-3 align-items-start mt-0">
          <div v-for="field in fields" :key="field.key" class="col-12 col-sm-6 col-xl-4"><label :for="`monthly-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`monthly-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl-4">
            <div class="row g-2 align-items-end">
              <div class="col"><label for="monthly-department" class="form-label">所属部门</label><select id="monthly-department" v-model="draft.departmentId" class="form-select"><option value="">全部</option><option v-for="department in rows.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
              <div class="col-auto"><div class="d-flex align-items-center py-2"><label class="form-check mb-0 text-nowrap"><input v-model="draft.ownDepartment" type="checkbox" class="form-check-input" :disabled="departmentMode" /><span class="form-check-label">本部门设备</span></label></div></div>
            </div>
          </div>
        </div>
        <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="monthly-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="月检定计划" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })">
      <template #cell-status="{ row }"><span class="badge" :class="equipmentStatusClasses[row.status]">{{ row.status }}</span></template>
      <template v-for="key in ['usageRecordCount', 'manualCount', 'certificateCount', 'acceptanceCount'] as const" :key="key" #[`cell-${key}`]="{ row }">{{ row[key] || '—' }}</template>
    </DataTable>
  </section>
</template>
