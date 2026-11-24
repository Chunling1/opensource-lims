<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ScrollableTabs from '../../components/common/ScrollableTabs.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import EquipmentLoanModal from '../../components/quality/EquipmentLoanModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { availableEquipmentColumns, equipmentLoanColumns, canManageEquipmentLoans, type LoanTab, type EquipmentLoanQuery, type EquipmentLoanPage } from '../../types/quality/equipmentLoans'
const tabs = [{ key: 'available', label: '可领用设备' }, { key: 'records', label: '待归还设备' }] as const
const tab = ref<LoanTab>('available'), label = computed(() => tabs.find(item => item.key === tab.value)!.label)
function state() { return { draft: { code: '', name: '', manufacturer: '', status: 'open' as 'all' | 'open' | 'returned' }, query: { code: '', name: '', manufacturer: '', status: 'open', page: 1, pageSize: 10 } as EquipmentLoanQuery, data: { items: [], total: 0, page: 1, pageSize: 10 } as EquipmentLoanPage, columns: undefined as string | undefined, dirty: true, error: '' as ErrorValue } }
const panels = reactive({ available: state(), records: state() }), current = computed(() => panels[tab.value])
const allColumns = computed(() => tab.value === 'available' ? availableEquipmentColumns : equipmentLoanColumns)
const columnKeys = computed(() => parseTableColumns(allColumns.value, current.value.columns)), columns = computed(() => allColumns.value.filter(column => columnKeys.value.includes(column.key)))
const selected = ref<string[]>([]), loading = ref(false), exporting = ref(false), outputError = ref<ErrorValue>(''), canWrite = computed(() => canManageEquipmentLoans(currentActor.value))
const modal = ref<{ mode: 'borrow' | 'return' | 'view'; ids: string[] }>(), toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const actions = computed(() => [{ label: tab.value === 'available' ? '领用' : '归还', icon: tab.value === 'available' ? 'ti ti-login' : 'ti ti-logout', disabled: !canWrite.value || loading.value || !!current.value.error || !selected.value.length }])
let epoch = 0, outputEpoch = 0, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch, kind = tab.value, panel = panels[kind]
  loading.value = true; panel.error = ''; selected.value = []
  try { const result = await registrationDemo.equipmentLoans(kind, { ...panel.query }, request.signal); if (token === epoch) { panel.data = result; panel.query.page = result.page; panel.dirty = false } }
  catch (issue) { if (token === epoch && !request.signal.aborted) { panel.error = normalizeError(issue); panel.data.items = []; panel.dirty = true } }
  finally { if (token === epoch) loading.value = false }
}
function search() { Object.assign(current.value.query, current.value.draft, { page: 1 }); void load() }
function paginate(page: number, size?: number) { current.value.query.page = page; if (size) current.value.query.pageSize = size; void load() }
function toggleColumn(key: string, checked: boolean) { const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key); current.value.columns = [...keys].join(',') }
async function saved() {
  message.value = modal.value?.mode === 'borrow' ? '已领用所选设备。' : '已归还所选设备。'; modal.value = undefined
  panels.available.dirty = true; panels.records.dirty = true; void load(); await nextTick(); toast.value?.show()
}
async function output(onlySelected: boolean) {
  if (loading.value || exporting.value || current.value.error || onlySelected && !selected.value.length) return
  const token = ++outputEpoch, name = label.value; exporting.value = true; outputError.value = ''
  try { const blob = await registrationDemo.exportEquipmentLoans(tab.value, { ...current.value.query, ...(onlySelected ? { ids: [...selected.value] } : {}) }); if (token === outputEpoch) downloadBlob(blob, `${name}.csv`) }
  catch (issue) { if (token === outputEpoch) outputError.value = normalizeError(issue) }
  finally { if (token === outputEpoch) exporting.value = false }
}
watch(tab, () => {
  controller?.abort(); epoch++; loading.value = false; selected.value = []; outputEpoch++; exporting.value = false; outputError.value = ''
  if (current.value.dirty) void load()
})
watch(() => currentActor.value.id, () => { modal.value = undefined; Object.assign(panels, { available: state(), records: state() }); outputEpoch++; exporting.value = false; outputError.value = ''; void load() })
void load()
onBeforeUnmount(() => { epoch++; outputEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading title="领用与归还" />
  <section class="card" aria-label="领用与归还列表区域">
    <div class="card-header pb-0 border-bottom-0"><ScrollableTabs variant="underline" id-prefix="equipment-loans" label="领用与归还" v-model="tab" :tabs="tabs" /></div>
    <div :id="`equipment-loans-panel-${tab}`" role="tabpanel" :aria-labelledby="`equipment-loans-tab-${tab}`">
      <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3"><div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ label }}</h5><span v-if="!loading && !current.error" class="badge bg-primary-subtle text-body">{{ current.data.total }}</span></div><TableToolbar :key="tab" :label="label" :adaptive-actions="actions" :columns="allColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!current.error || exporting" @action="modal = { mode: tab === 'available' ? 'borrow' : 'return', ids: [...selected] }" @column="toggleColumn" @reset="current.columns = undefined" @export="output" /></div>
      <form class="card-body border-bottom" :aria-label="`${label}查询`" @submit.prevent="search"><QueryFormLayout><div class="row g-3"><div v-for="field in [{ key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称' }, { key: 'manufacturer', label: '生产厂家' }] as const" :key="field.key" class="col-12 col-sm-6" :class="tab === 'records' ? 'col-xl-3' : 'col-xl-4'"><label :for="`loan-filter-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`loan-filter-${field.key}`" v-model="current.draft[field.key]" class="form-control" maxlength="200" /></div><div v-if="tab === 'records'" class="col-12 col-sm-6 col-xl-3"><label for="loan-filter-status" class="form-label">归还状态</label><select id="loan-filter-status" v-model="current.draft.status" class="form-select"><option value="all">全部</option><option value="open">未归还</option><option value="returned">已归还</option></select></div></div><template #actions><button type="submit" class="btn btn-primary" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template></QueryFormLayout></form>
      <div v-if="outputError" class="px-3 pt-3"><ErrorNotice :error="outputError" /></div>
      <DataTable :label="label" :rows="current.data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :selectable="row => tab === 'available' || !row.returnedAt" :selection-disabled-reason="row => row.returnedAt ? '该记录已归还' : undefined" :loading="loading" :error="current.error" preserve-rows-on-loading :pagination="{ ...current.data, sizes: [10, 20, 50] }" @retry="load" @page="paginate($event)" @size="paginate(1, $event)">
        <template #cell-loanStatus="{ row }"><span class="badge" :class="row.loanStatus === '未归还' ? 'bg-warning-subtle text-warning-emphasis' : 'bg-success-subtle text-success'">{{ row.loanStatus }}</span></template>
      </DataTable>
    </div>
  </section>
  <EquipmentLoanModal v-if="modal" :mode="modal.mode" :ids="modal.ids" @close="modal = undefined" @saved="saved" />
  <TemplateToast ref="toast" :message="message" />
</template>
