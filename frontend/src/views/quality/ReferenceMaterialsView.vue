<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import ReferenceMaterialModal from '../../components/quality/ReferenceMaterialModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { materialColumns, acceptanceColumns, canWriteMaterials, type MaterialKind, type MaterialQuery, type MaterialPage, type MaterialRecord, type AcceptanceRecord } from '../../types/quality/referenceMaterials'

const kinds = ['materials', 'acceptances'] as const, labels = { materials: '标准物质登记', acceptances: '验收记录' }
function state<Row>(pageSize: number) { return { draft: { name: '', manufacturer: '', useDepartment: '' }, query: { name: '', manufacturer: '', useDepartment: '', page: 1, pageSize } as MaterialQuery, data: { items: [], total: 0, page: 1, pageSize } as MaterialPage<Row>, selected: [] as string[], columns: undefined as string | undefined, loading: false, exporting: false, error: '' as ErrorValue, outputError: '' as ErrorValue } }
const panels = reactive({ materials: state<MaterialRecord>(5), acceptances: state<AcceptanceRecord>(10) })
const collapsed = ref(false), linked = ref(true), canWrite = computed(() => canWriteMaterials(currentActor.value))
const allColumns = (kind: MaterialKind) => kind === 'materials' ? materialColumns : acceptanceColumns
const keys = (kind: MaterialKind) => parseTableColumns(allColumns(kind), panels[kind].columns)
const materialVisibleColumns = computed(() => materialColumns.filter(column => keys('materials').includes(column.key)))
const acceptanceVisibleColumns = computed(() => acceptanceColumns.filter(column => keys('acceptances').includes(column.key)))
const selectionCaption = computed(() => {
  const selected = panels.materials.selected
  if (selected.length > 1) return `已选 ${selected.length} 条登记`
  const row = panels.materials.data.items.find(row => row.id === selected[0])
  return row ? [row.name, row.specification].filter(Boolean).join(' · ') : ''
})
const canAddAcceptance = computed(() => canWrite.value && !panels.materials.loading && !panels.materials.error && panels.materials.selected.length === 1 && panels.materials.data.items.some(row => row.id === panels.materials.selected[0] && !row.accepted))
const addAcceptanceHint = computed(() => panels.materials.selected.length !== 1 ? '请在上方选中一条未验收登记' : panels.materials.data.items.find(row => row.id === panels.materials.selected[0])?.accepted ? '所选登记已验收，请查看或编辑验收记录' : '正在加载登记记录')
const acceptanceReady = computed(() => !linked.value || !!panels.materials.selected.length)
const modal = ref<{ kind: MaterialKind; mode: 'new' | 'edit' | 'view' | 'delete'; row?: MaterialRecord | AcceptanceRecord; selectedMaterial?: MaterialRecord }>()
const toast = ref<InstanceType<typeof TemplateToast>>(), message = ref('')
const epochs = { materials: 0, acceptances: 0 }, exportEpochs = { materials: 0, acceptances: 0 }, controllers: Partial<Record<MaterialKind, AbortController>> = {}
const requestQuery = (kind: MaterialKind): MaterialQuery => ({ ...panels[kind].query, ...(kind === 'acceptances' && linked.value ? { materialIds: [...panels.materials.selected] } : {}) })
async function load(kind: MaterialKind, preserveSelection = false) {
  controllers[kind]?.abort(); const request = controllers[kind] = new AbortController(), token = ++epochs[kind], panel = panels[kind]
  if (!preserveSelection) panel.selected = []; panel.error = ''; panel.outputError = ''; exportEpochs[kind]++; panel.exporting = false
  if (kind === 'acceptances' && !acceptanceReady.value) { panel.data.items = []; panel.data.total = 0; panel.loading = false; return }
  panel.loading = true
  try {
    if (kind === 'materials') { const data = await registrationDemo.referenceMaterials(requestQuery(kind), request.signal); if (token === epochs[kind]) { panels.materials.data = data; panels.materials.selected = panels.materials.selected.filter(id => data.items.some(row => row.id === id)); panels.materials.query.page = data.page } }
    else { const data = await registrationDemo.materialAcceptances(requestQuery(kind), request.signal); if (token === epochs[kind]) { panels.acceptances.data = data; panels.acceptances.query.page = data.page } }
  } catch (issue) { if (token === epochs[kind] && !request.signal.aborted) { panel.error = normalizeError(issue); panel.data.items = [] } }
  finally { if (token === epochs[kind]) panel.loading = false }
}
function search(kind: MaterialKind) { Object.assign(panels[kind].query, panels[kind].draft, { page: 1 }); void load(kind) }
function paginate(kind: MaterialKind, page: number, size?: number) { panels[kind].query.page = page; if (size) panels[kind].query.pageSize = size; void load(kind) }
function toggleColumn(kind: MaterialKind, key: string, checked: boolean) { const selected = new Set<string>(keys(kind)); if (checked) selected.add(key); else selected.delete(key); panels[kind].columns = [...selected].join(',') }
function selectMaterials(ids: string[]) { panels.materials.selected = ids; linked.value = true }
function selectMaterialRow(id: string) { if (!panels.materials.selected.includes(id)) selectMaterials([id]) }
function add(kind: MaterialKind) {
  if (!canWrite.value || kind === 'acceptances' && !canAddAcceptance.value) return
  modal.value = { kind, mode: 'new', selectedMaterial: kind === 'acceptances' ? panels.materials.data.items.find(row => row.id === panels.materials.selected[0]) : undefined }
}
function addAcceptance(row: MaterialRecord) {
  if (!canWrite.value || panels.materials.loading || row.accepted) return
  selectMaterials([row.id]); add('acceptances')
}
async function saved() {
  const kind = modal.value!.kind
  message.value = `${labels[kind]}已${modal.value?.mode === 'delete' ? '删除' : '保存'}。`; modal.value = undefined
  await load('materials', true); await load('acceptances')
  await nextTick(); toast.value?.show()
}
async function output(kind: MaterialKind, onlySelected: boolean) {
  const panel = panels[kind]
  if (panel.loading || panel.exporting || panel.error || onlySelected && !panel.selected.length || kind === 'acceptances' && !acceptanceReady.value) return
  const token = ++exportEpochs[kind]; panel.exporting = true; panel.outputError = ''
  try { const blob = await registrationDemo.exportMaterialRecords(kind, { ...requestQuery(kind), ...(onlySelected ? { ids: [...panel.selected] } : {}) }); if (token === exportEpochs[kind]) downloadBlob(blob, `${labels[kind]}列表.csv`) }
  catch (issue) { if (token === exportEpochs[kind]) panel.outputError = normalizeError(issue) }
  finally { if (token === exportEpochs[kind]) panel.exporting = false }
}
watch(() => JSON.stringify([linked.value, linked.value ? panels.materials.selected : []]), () => { panels.acceptances.query.page = 1; void load('acceptances') })
watch(() => currentActor.value.id, () => { modal.value = undefined; linked.value = true; Object.assign(panels, { materials: state<MaterialRecord>(5), acceptances: state<AcceptanceRecord>(10) }); void load('materials'); void load('acceptances') })
void load('materials'); void load('acceptances')
onBeforeUnmount(() => { for (const kind of kinds) { epochs[kind]++; exportEpochs[kind]++; controllers[kind]?.abort() } })
</script>
<template>
  <PageHeading title="标准物质登记" />
  <section v-for="kind in kinds" :key="kind" class="card" :aria-label="`${labels[kind]}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex flex-wrap align-items-center gap-2"><h5 class="card-title mb-0">{{ labels[kind] }}</h5><span v-if="!panels[kind].loading && !panels[kind].error" class="badge bg-primary-subtle text-body">{{ panels[kind].data.total }}</span><button v-if="kind === 'materials'" type="button" class="btn btn-sm btn-light" :aria-expanded="!collapsed" aria-controls="reference-material-body" @click="collapsed = !collapsed">{{ collapsed ? '展开登记' : '收起登记' }}</button></div>
      <TableToolbar :label="labels[kind]" :columns="allColumns(kind)" :selected="keys(kind)" :count="panels[kind].selected.length" :export-disabled="panels[kind].loading || !!panels[kind].error || panels[kind].exporting || kind === 'acceptances' && !acceptanceReady" @column="(key, checked) => toggleColumn(kind, key, checked)" @reset="panels[kind].columns = undefined" @export="output(kind, $event)"><button v-if="canWrite" type="button" class="btn btn-primary text-nowrap" :disabled="panels[kind].loading || kind === 'acceptances' && !canAddAcceptance" :title="kind === 'acceptances' && !canAddAcceptance ? addAcceptanceHint : undefined" @click="add(kind)"><i class="ti ti-plus me-1" aria-hidden="true"></i>{{ kind === 'materials' ? '新增登记' : '新增验收' }}</button></TableToolbar>
    </div>
    <div v-if="kind === 'materials' && collapsed && selectionCaption" class="card-body"><p class="mb-0 text-break">{{ selectionCaption }}</p></div>
    <div v-if="kind === 'acceptances'" class="d-flex flex-wrap align-items-center gap-3 px-3 border-bottom">
      <div class="nav nav-tabs nav-tabs-custom border-bottom-0" role="tablist" aria-label="验收范围">
        <button id="acceptances-current-tab" class="nav-link" :class="{ active: linked }" role="tab" :aria-selected="linked" aria-controls="material-acceptance-body" @click="linked = true">当前登记</button>
        <button id="acceptances-all-tab" class="nav-link" :class="{ active: !linked }" role="tab" :aria-selected="!linked" aria-controls="material-acceptance-body" @click="linked = false">全部验收</button>
      </div>
      <span v-if="linked && selectionCaption" class="text-muted small text-break py-2">{{ selectionCaption }}</span>
    </div>
    <div :id="kind === 'materials' ? 'reference-material-body' : 'material-acceptance-body'" :role="kind === 'acceptances' ? 'tabpanel' : undefined" :aria-labelledby="kind === 'acceptances' ? linked ? 'acceptances-current-tab' : 'acceptances-all-tab' : undefined" class="collapse" :class="{ show: kind === 'acceptances' || !collapsed }">
      <form v-if="kind === 'materials' || acceptanceReady" class="card-body border-bottom" :aria-label="`${labels[kind]}查询`" @submit.prevent="search(kind)"><QueryFormLayout>
        <div class="row g-3">
          <div class="col-12 col-sm-6"><label :for="`${kind}-name`" class="form-label">{{ kind === 'materials' ? '品名' : '物质名称' }}</label><input :id="`${kind}-name`" v-model="panels[kind].draft.name" class="form-control" maxlength="200" /></div>
          <div v-if="kind === 'materials'" class="col-12 col-sm-6"><label for="material-filter-manufacturer" class="form-label">生产厂家</label><input id="material-filter-manufacturer" v-model="panels.materials.draft.manufacturer" class="form-control" maxlength="200" /></div>
          <div v-else class="col-12 col-sm-6"><label for="acceptance-filter-department" class="form-label">使用部门</label><input id="acceptance-filter-department" v-model="panels.acceptances.draft.useDepartment" class="form-control" maxlength="200" /></div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="panels[kind].loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout></form>
      <div v-if="panels[kind].outputError" class="px-3 pt-3"><ErrorNotice :error="panels[kind].outputError" /></div>
      <DataTable v-if="kind === 'materials'" label="标准物质登记" :rows="panels.materials.data.items" :columns="materialVisibleColumns" :row-key="row => row.id" :row-label="row => row.name" :selected="panels.materials.selected" @update:selected="selectMaterials" @row-click="row => selectMaterialRow(row.id)" highlight-selected :loading="panels.materials.loading" :error="panels.materials.error" preserve-rows-on-loading :pagination="{ ...panels.materials.data, sizes: [5, 10, 20, 50] }" @retry="load(kind)" @page="paginate(kind, $event)" @size="paginate(kind, 1, $event)">
        <template #actions="{ row }"><button type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" :title="!canWrite ? '当前身份仅支持查看' : undefined" @click="modal = { kind, mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite || row.accepted" :title="!canWrite ? '当前身份仅支持查看' : row.accepted ? '请先删除关联验收记录' : undefined" @click="modal = { kind, mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite || row.accepted" :title="!canWrite ? '当前身份仅支持查看' : row.accepted ? '所选登记已验收' : undefined" @click="addAcceptance(row)"><i class="ti ti-circle-plus me-2 text-muted" aria-hidden="true"></i>新增验收</button></template>
      </DataTable>
      <div v-else-if="!acceptanceReady" class="text-center py-5"><i class="ti ti-file-description display-5 text-muted" aria-hidden="true"></i><h5 class="mt-3">请选择登记</h5><p class="text-muted">勾选上方登记，查看关联验收记录。</p></div>
      <DataTable v-else label="验收记录" :rows="panels.acceptances.data.items" :columns="acceptanceVisibleColumns" :row-key="row => row.id" :row-label="row => `${row.name} ${row.acceptedAt}`" v-model:selected="panels.acceptances.selected" :loading="panels.acceptances.loading" :error="panels.acceptances.error" preserve-rows-on-loading :pagination="{ ...panels.acceptances.data, sizes: [10, 20, 50] }" @retry="load(kind)" @page="paginate(kind, $event)" @size="paginate(kind, 1, $event)">
        <template #actions="{ row }"><button type="button" class="dropdown-item" role="menuitem" @click="modal = { kind, mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" :title="!canWrite ? '当前身份仅支持查看' : undefined" @click="modal = { kind, mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" :title="!canWrite ? '当前身份仅支持查看' : undefined" @click="modal = { kind, mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button></template>
      </DataTable>
    </div>
  </section>
  <ReferenceMaterialModal v-if="modal" :kind="modal.kind" :mode="modal.mode" :row="modal.row" :selected-material="modal.selectedMaterial" @close="modal = undefined" @saved="saved" @invalidated="load('materials', true); load('acceptances')" />
  <TemplateToast ref="toast" :message="message" />
</template>
