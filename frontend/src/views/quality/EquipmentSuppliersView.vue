<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import EquipmentSupplierModal from '../../components/quality/EquipmentSupplierModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { supplierColumns, evaluationColumns, supplierSearchFields, evaluationSearchFields, canWriteSuppliers, type SupplierListKind, type SupplierQuery, type SupplierPage, type SupplierRecord, type EvaluationRecord } from '../../types/quality/equipmentSuppliers'

const kinds = ['suppliers', 'evaluations'] as const, labels = { suppliers: '供应商', evaluations: '评价' }
function state<Row>(pageSize: number) { return { draft: { field: '', value: '' }, query: { field: '', value: '', page: 1, pageSize } as SupplierQuery, data: { items: [], total: 0, page: 1, pageSize } as SupplierPage<Row>, selected: [] as string[], columns: undefined as string | undefined, loading: false, exporting: false, error: '' as ErrorValue, outputError: '' as ErrorValue } }
const panels = reactive({ suppliers: state<SupplierRecord>(5), evaluations: state<EvaluationRecord>(10) })
const collapsed = ref(false), linked = ref(true), canWrite = computed(() => canWriteSuppliers(currentActor.value))
const allColumns = (kind: SupplierListKind) => kind === 'suppliers' ? supplierColumns : evaluationColumns
const keys = (kind: SupplierListKind) => parseTableColumns(allColumns(kind), panels[kind].columns)
const supplierVisibleColumns = computed(() => supplierColumns.filter(column => keys('suppliers').includes(column.key)))
const evaluationVisibleColumns = computed(() => evaluationColumns.filter(column => keys('evaluations').includes(column.key)))
const selectionCaption = computed(() => {
  const selected = panels.suppliers.selected
  if (selected.length > 1) return `已选 ${selected.length} 家供应商`
  const row = panels.suppliers.data.items.find(row => row.id === selected[0])
  return row ? [row.code, row.name].filter(Boolean).join(' · ') : ''
})
const canAddEvaluation = computed(() => canWrite.value && !panels.suppliers.loading && !panels.suppliers.error && panels.suppliers.selected.length === 1 && panels.suppliers.data.items.some(row => row.id === panels.suppliers.selected[0]))
const evaluationReady = computed(() => !linked.value || !!panels.suppliers.selected.length)
const modal = ref<{ kind: SupplierListKind; mode: 'new' | 'edit' | 'view' | 'delete'; row?: SupplierRecord | EvaluationRecord; selectedSupplier?: SupplierRecord }>()
const toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const epochs = { suppliers: 0, evaluations: 0 }, exportEpochs = { suppliers: 0, evaluations: 0 }, controllers: Partial<Record<SupplierListKind, AbortController>> = {}
const requestQuery = (kind: SupplierListKind): SupplierQuery => ({ ...panels[kind].query, ...(kind === 'evaluations' && linked.value ? { supplierIds: [...panels.suppliers.selected] } : {}) })
async function load(kind: SupplierListKind) {
  controllers[kind]?.abort(); const request = controllers[kind] = new AbortController(), token = ++epochs[kind], panel = panels[kind]
  panel.selected = []; panel.error = ''; panel.outputError = ''; exportEpochs[kind]++; panel.exporting = false
  if (kind === 'evaluations' && !evaluationReady.value) { panel.data.items = []; panel.data.total = 0; panel.loading = false; return }
  panel.loading = true
  try {
    if (kind === 'suppliers') { const data = await registrationDemo.equipmentSuppliers(requestQuery(kind), request.signal); if (token === epochs[kind]) { panels.suppliers.data = data; panels.suppliers.query.page = data.page } }
    else { const data = await registrationDemo.supplierEvaluations(requestQuery(kind), request.signal); if (token === epochs[kind]) { panels.evaluations.data = data; panels.evaluations.query.page = data.page } }
  } catch (issue) { if (token === epochs[kind] && !request.signal.aborted) { panel.error = normalizeError(issue); panel.data.items = [] } }
  finally { if (token === epochs[kind]) panel.loading = false }
}
function search(kind: SupplierListKind) { Object.assign(panels[kind].query, panels[kind].draft, { page: 1 }); void load(kind) }
function paginate(kind: SupplierListKind, page: number, size?: number) { panels[kind].query.page = page; if (size) panels[kind].query.pageSize = size; void load(kind) }
function toggleColumn(kind: SupplierListKind, key: string, checked: boolean) { const selected = new Set<string>(keys(kind)); if (checked) selected.add(key); else selected.delete(key); panels[kind].columns = [...selected].join(',') }
function selectSuppliers(ids: string[]) { panels.suppliers.selected = ids; linked.value = true }
function selectSupplierRow(id: string) { if (!panels.suppliers.selected.includes(id)) selectSuppliers([id]) }
function add(kind: SupplierListKind) {
  if (!canWrite.value || kind === 'evaluations' && !canAddEvaluation.value) return
  modal.value = { kind, mode: 'new', selectedSupplier: kind === 'evaluations' ? panels.suppliers.data.items.find(row => row.id === panels.suppliers.selected[0]) : undefined }
}
function addEvaluation(row: SupplierRecord) {
  if (!canWrite.value || panels.suppliers.loading) return
  selectSuppliers([row.id]); add('evaluations')
}
async function saved() {
  const kind = modal.value!.kind
  message.value = `${labels[kind]}已${modal.value?.mode === 'delete' ? '删除' : '保存'}。`; modal.value = undefined
  void load(kind); if (kind === 'suppliers') void load('evaluations')
  await nextTick(); toast.value?.show()
}
async function output(kind: SupplierListKind, onlySelected: boolean) {
  const panel = panels[kind]
  if (panel.loading || panel.exporting || panel.error || onlySelected && !panel.selected.length || kind === 'evaluations' && !evaluationReady.value) return
  const token = ++exportEpochs[kind]; panel.exporting = true; panel.outputError = ''
  try { const blob = await registrationDemo.exportEquipmentSupplierRecords(kind, { ...requestQuery(kind), ...(onlySelected ? { ids: [...panel.selected] } : {}) }); if (token === exportEpochs[kind]) downloadBlob(blob, `${labels[kind]}列表.csv`) }
  catch (issue) { if (token === exportEpochs[kind]) panel.outputError = normalizeError(issue) }
  finally { if (token === exportEpochs[kind]) panel.exporting = false }
}
watch(() => JSON.stringify([linked.value, linked.value ? panels.suppliers.selected : []]), () => { panels.evaluations.query.page = 1; void load('evaluations') })
watch(() => currentActor.value.id, () => { modal.value = undefined; linked.value = true; Object.assign(panels, { suppliers: state<SupplierRecord>(5), evaluations: state<EvaluationRecord>(10) }); void load('suppliers'); void load('evaluations') })
void load('suppliers'); void load('evaluations')
onBeforeUnmount(() => { for (const kind of kinds) { epochs[kind]++; exportEpochs[kind]++; controllers[kind]?.abort() } })
</script>
<template>
  <PageHeading title="供应商及评价" />
  <section v-for="kind in kinds" :key="kind" class="card" :aria-label="`${labels[kind]}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex flex-wrap align-items-center gap-2"><h5 class="card-title mb-0">{{ labels[kind] }}</h5><span v-if="!panels[kind].loading && !panels[kind].error" class="badge bg-primary-subtle text-body">{{ panels[kind].data.total }}</span><button v-if="kind === 'suppliers'" type="button" class="btn btn-sm btn-light" :aria-expanded="!collapsed" aria-controls="equipment-supplier-body" @click="collapsed = !collapsed">{{ collapsed ? '展开供应商' : '收起供应商' }}</button></div>
      <TableToolbar :label="labels[kind]" :columns="allColumns(kind)" :selected="keys(kind)" :count="panels[kind].selected.length" :export-disabled="panels[kind].loading || !!panels[kind].error || panels[kind].exporting || kind === 'evaluations' && !evaluationReady" @column="(key, checked) => toggleColumn(kind, key, checked)" @reset="panels[kind].columns = undefined" @export="output(kind, $event)"><button v-if="canWrite" type="button" class="btn btn-primary text-nowrap" :disabled="panels[kind].loading || kind === 'evaluations' && !canAddEvaluation" :title="kind === 'evaluations' && !canAddEvaluation ? '请在上方选中一家供应商' : undefined" @click="add(kind)"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增{{ labels[kind] }}</button></TableToolbar>
    </div>
    <div v-if="kind === 'suppliers' && collapsed && selectionCaption" class="card-body"><p class="mb-0 text-break">{{ selectionCaption }}</p></div>
    <div v-if="kind === 'evaluations'" class="d-flex flex-wrap align-items-center gap-3 px-3 border-bottom">
      <div class="nav nav-tabs nav-tabs-custom border-bottom-0" role="tablist" aria-label="评价范围">
        <button id="evaluations-current-tab" class="nav-link" :class="{ active: linked }" role="tab" :aria-selected="linked" aria-controls="equipment-evaluation-body" @click="linked = true">当前供应商</button>
        <button id="evaluations-all-tab" class="nav-link" :class="{ active: !linked }" role="tab" :aria-selected="!linked" aria-controls="equipment-evaluation-body" @click="linked = false">全部评价</button>
      </div>
      <span v-if="linked && selectionCaption" class="text-muted small text-break py-2">{{ selectionCaption }}</span>
    </div>
    <div :id="kind === 'suppliers' ? 'equipment-supplier-body' : 'equipment-evaluation-body'" :role="kind === 'evaluations' ? 'tabpanel' : undefined" :aria-labelledby="kind === 'evaluations' ? linked ? 'evaluations-current-tab' : 'evaluations-all-tab' : undefined" class="collapse" :class="{ show: kind === 'evaluations' || !collapsed }">
      <form v-if="kind === 'suppliers' || evaluationReady" class="card-body border-bottom" :aria-label="`${labels[kind]}查询`" @submit.prevent="search(kind)"><QueryFormLayout>
        <div class="row g-3">
          <div class="col-12 col-sm-6"><label :for="`${kind}-field`" class="form-label">查询内容</label><select :id="`${kind}-field`" v-model="panels[kind].draft.field" class="form-select"><option value="">不限</option><option v-for="field in kind === 'suppliers' ? supplierSearchFields : evaluationSearchFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
          <div class="col-12 col-sm-6"><label :for="`${kind}-value`" class="form-label">包含</label><input :id="`${kind}-value`" v-model="panels[kind].draft.value" class="form-control" :disabled="!panels[kind].draft.field" maxlength="200" /></div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="panels[kind].loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout></form>
      <div v-if="panels[kind].outputError" class="px-3 pt-3"><ErrorNotice :error="panels[kind].outputError" /></div>
      <DataTable v-if="kind === 'suppliers'" label="供应商" :rows="panels.suppliers.data.items" :columns="supplierVisibleColumns" :row-key="row => row.id" :row-label="row => row.name" :selected="panels.suppliers.selected" @update:selected="selectSuppliers" @row-click="row => selectSupplierRow(row.id)" highlight-selected :loading="panels.suppliers.loading" :error="panels.suppliers.error" preserve-rows-on-loading :pagination="{ ...panels.suppliers.data, sizes: [5, 10, 20, 50] }" @retry="load(kind)" @page="paginate(kind, $event)" @size="paginate(kind, 1, $event)">
        <template #actions="{ row }"><button type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button><button :disabled="!canWrite" :title="!canWrite ? '当前身份无权操作' : undefined" type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button><button :disabled="!canWrite" :title="!canWrite ? '当前身份无权操作' : undefined" type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button><button :disabled="!canWrite" :title="!canWrite ? '当前身份无权操作' : undefined" type="button" class="dropdown-item" role="menuitem" @click="addEvaluation(row)"><i class="ti ti-circle-plus me-2 text-muted" aria-hidden="true"></i>新增评价</button></template>
      </DataTable>
      <div v-else-if="!evaluationReady" class="text-center py-5"><i class="ti ti-file-description display-5 text-muted" aria-hidden="true"></i><h5 class="mt-3">请选择供应商</h5><p class="text-muted">勾选上方供应商，查看关联评价。</p></div>
      <DataTable v-else label="评价" :rows="panels.evaluations.data.items" :columns="evaluationVisibleColumns" :row-key="row => row.id" :row-label="row => `${row.name} ${row.reviewDate}`" v-model:selected="panels.evaluations.selected" :loading="panels.evaluations.loading" :error="panels.evaluations.error" preserve-rows-on-loading :pagination="{ ...panels.evaluations.data, sizes: [10, 20, 50] }" @retry="load(kind)" @page="paginate(kind, $event)" @size="paginate(kind, 1, $event)">
        <template #actions="{ row }"><button type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button><button :disabled="!canWrite" :title="!canWrite ? '当前身份无权操作' : undefined" type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button><button :disabled="!canWrite" :title="!canWrite ? '当前身份无权操作' : undefined" type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button></template>
      </DataTable>
    </div>
  </section>
  <EquipmentSupplierModal v-if="modal" :kind="modal.kind" :mode="modal.mode" :row="modal.row" :selected-supplier="modal.selectedSupplier" @close="modal = undefined" @saved="saved" />
  <TemplateToast ref="toast" :message="message" />
</template>
