<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import EquipmentInterimPlanModal from '../../components/quality/EquipmentInterimPlanModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns, tableCellText } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob, printTablePdf } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { overallPlanSearchFields, overallPlanOperators } from '../../types/quality/equipmentOverallPlan'
import { interimPlanColumns, type InterimPlanQuery, type InterimPlanPage, type InterimPlanRow } from '../../types/quality/equipmentInterimPlan'
const route = useRoute(), router = useRouter()
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<InterimPlanQuery>(() => ({ field: text('field', 'code') as InterimPlanQuery['field'], operator: text('operator', 'contains') as InterimPlanQuery['operator'], value: text('value'), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ field: 'code', operator: 'contains', value: '' })
watch(query, value => Object.assign(draft, { field: value.field, operator: value.operator, value: value.value }), { immediate: true })
const data = ref<InterimPlanPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), exporting = ref(false), printing = ref(false), error = ref<ErrorValue>(''), outputError = ref<ErrorValue>('')
const canWrite = computed(() => currentActor.value.roles.some(role => ['admin', 'quality'].includes(role)))
const columnKeys = computed(() => parseTableColumns(interimPlanColumns, route.query.columns))
const columns = computed(() => interimPlanColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'view' | 'edit' | 'delete'; row?: InterimPlanRow }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const actions = computed(() => [
  { label: '打印', icon: 'ti ti-printer', disabled: loading.value || !!error.value || printing.value || !data.value.total, busy: printing.value, hint: selected.value.length ? `打印已选 ${selected.value.length} 条记录` : '打印查询结果' },
])
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
let epoch = 0, outputEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.interimPlans(query.value, request.signal); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  const previous = route.fullPath
  await patch({ field: draft.field, operator: draft.operator, value: draft.value.trim() || undefined, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) {
  const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key)
  void patch({ columns: [...keys].join(',') })
}
async function saved() {
  message.value = modal.value?.mode === 'delete' ? '已删除期间核查计划。' : '已保存期间核查计划。'; modal.value = undefined
  void load(); await nextTick(); toast.value?.show()
}
async function output(onlySelected: boolean, print = false) {
  if (loading.value || error.value || exporting.value || printing.value || onlySelected && !selected.value.length) return
  const token = ++outputEpoch; outputError.value = ''; exporting.value = !print; printing.value = print
  const input = { ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }, outputColumns = [...columns.value]
  try {
    if (print) {
      const result = await registrationDemo.printInterimPlans(input)
      if (token === outputEpoch) await printTablePdf('设备期间核查计划', outputColumns.map(column => column.label), result.items.map(row => outputColumns.map(column => tableCellText(row[column.key], {}))))
    } else {
      const blob = await registrationDemo.exportInterimPlans(input)
      if (token === outputEpoch) downloadBlob(blob, '设备期间核查计划.csv')
    }
  } catch (issue) { if (token === outputEpoch) outputError.value = normalizeError(issue) }
  finally { if (token === outputEpoch) { exporting.value = false; printing.value = false } }
}
function action(index: number) {
  if (index === 0) void output(!!selected.value.length, true)
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (values, old) => {
  outputEpoch++; exporting.value = false; printing.value = false; outputError.value = ''
  if (old && values[1] !== old[1]) { modal.value = undefined; data.value.items = [] }
  void load()
}, { immediate: true })
onBeforeUnmount(() => { epoch++; outputEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading title="设备期间核查计划" />
  <section class="card" aria-label="设备期间核查计划列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">设备期间核查计划</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar label="设备期间核查计划" :adaptive-actions="actions" :columns="interimPlanColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting || printing" @action="action" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="output($event)"><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" aria-label="设备期间核查计划查询" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3">
        <div class="col-12 col-sm-6 col-xl-4"><label for="interim-filter-field" class="form-label">查询字段</label><select id="interim-filter-field" v-model="draft.field" class="form-select"><option v-for="field in overallPlanSearchFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-4"><label for="interim-filter-operator" class="form-label">匹配方式</label><select id="interim-filter-operator" v-model="draft.operator" class="form-select"><option v-for="operator in overallPlanOperators" :key="operator.key" :value="operator.key">{{ operator.label }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-4"><label for="interim-filter-value" class="form-label">查询值</label><input id="interim-filter-value" v-model="draft.value" class="form-control" maxlength="200" /></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="outputError" class="px-3 pt-3"><ErrorNotice :error="outputError" /></div>
    <DataTable label="设备期间核查计划" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button type="button" class="dropdown-item text-danger" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <EquipmentInterimPlanModal v-if="modal" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <TemplateToast ref="toast" :message="message" />
</template>
