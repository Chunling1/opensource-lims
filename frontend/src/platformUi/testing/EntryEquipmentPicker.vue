<script setup lang="ts">
import { inject, computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import EquipmentSchemeBar from './EquipmentSchemeBar.vue'
import { entryEquipment } from './entryEquipment'
import type { SchemeResolution } from './equipmentSchemes'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ConfirmationModal from '../../components/common/ConfirmationModal.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import DataEntryEquipmentTable from '../../components/testing/DataEntryEquipmentTable.vue'
import { useUnsavedChanges } from '../../components/common/useUnsavedChanges'
const registrationDemo=inject<any>('platform-entry-services')!
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { trialDatesText, type EntryDetail, type EntryEquipment } from '../../types/testing/dataEntryDetail'

const props = defineProps<{ detail: EntryDetail; value: string[] }>()
const emit = defineEmits<{ close: []; select: [string[]]; refreshed: [EntryDetail] }>()
const selected = ref([...props.value]), leftChecked = ref<string[]>([]), rightChecked = ref<string[]>([]), candidates = ref<string[]>([])
const associating = ref(false), busy = ref(false), stale = ref(false), confirmDefaults = ref<false | 'set' | 'unset'>(false), error = ref<ErrorValue>(''), message = ref('')
const schemeBusy = ref(false)
const current = ref(props.detail), config = computed(() => current.value.equipmentConfig), options = computed(() => current.value.options.equipment)
const filters = ref({ code: '', name: '', serial: '' }), applied = ref({ ...filters.value })
const queryField = ref<'code' | 'name' | 'manufacturer' | 'inspectionOrganization' | 'storageOrganization'>('name'), keyword = ref(''), appliedKeyword = ref(''), appliedField = ref(queryField.value)
const department = ref(''), appliedDepartment = ref('')
const departments = computed(() => [...new Set(options.value.map(row => row.departmentName).filter(Boolean))].sort())
const leftPage = ref(1), rightPage = ref(1), cataloguePage = ref(1), leftSize = ref(10), rightSize = ref(10), catalogueSize = ref(10)
const associated = computed(() => options.value.filter(row => config.value.associatedIds.includes(row.id)).filter(row => !appliedDepartment.value || row.departmentName === appliedDepartment.value).filter(row => (['code', 'name', 'serial'] as const).every(key => !applied.value[key] || row[key].toLocaleLowerCase().includes(applied.value[key].toLocaleLowerCase()))))
const selectedRows = computed(() => selected.value.map(id => options.value.find(row => row.id === id) || { id, code: id, name: '设备已不可选', model: '', manufacturer: '', serial: '' }))
const catalogue = computed(() => options.value.filter(row => (!appliedDepartment.value || row.departmentName === appliedDepartment.value) && (!appliedKeyword.value || (row[appliedField.value] || '').toLocaleLowerCase().includes(appliedKeyword.value.toLocaleLowerCase()))))
const slice = (rows: EntryEquipment[], page: number, size: number) => rows.slice((page - 1) * size, page * size)
const movable = computed(() => leftChecked.value.filter(id => !selected.value.includes(id) && options.value.some(row => row.id === id && row.selectable !== false)))
const pendingSelection = ref<{ mode: 'move' | 'select'; ids: string[] }>()
const blockedEquipment = ref<EntryEquipment>()
const acknowledged = ref<string[]>([])
const warningRows = computed(() => options.value.filter(row => pendingSelection.value?.ids.includes(row.id) && row.expiredNow && row.selectable !== false && !acknowledged.value.includes(row.id)))
const trialPeriod = computed(() => trialDatesText(current.value.form.testDates))
// A confirmation applies only to this report, these test dates and these live records.
watch(() => JSON.stringify([current.value.sample.id, current.value.form.testDates, options.value]), () => {
  pendingSelection.value = undefined
  blockedEquipment.value = undefined
  acknowledged.value = []
})
const checkedDefaults = computed(() => leftChecked.value.filter(id => config.value.defaultIds.includes(id)))
const allCheckedDefault = computed(() => leftChecked.value.length > 0 && checkedDefaults.value.length === leftChecked.value.length)
const disabled = computed(() => busy.value || stale.value || !current.value.capabilities.canEdit)
useUnsavedChanges(busy)
let generation = 0
onBeforeRouteLeave(() => busy.value ? false : undefined)
onBeforeRouteUpdate(() => busy.value ? false : undefined)
onBeforeUnmount(() => { generation++ })
function search() { applied.value = Object.fromEntries(Object.entries(filters.value).map(([key, value]) => [key, value.trim()])) as typeof filters.value; appliedDepartment.value = department.value; leftPage.value = 1 }
function searchCatalogue() { appliedKeyword.value = keyword.value.trim(); appliedField.value = queryField.value; appliedDepartment.value = department.value; cataloguePage.value = 1 }
function applySelection(mode: 'move' | 'select', ids: string[]) {
  if (mode === 'select') { emit('select', [...ids]); return }
  selected.value = [...new Set([...selected.value, ...ids])]; leftChecked.value = []; message.value = ''
}
function requestSelection(mode: 'move' | 'select', ids: string[]) {
  if (disabled.value) return
  const invalid = ids.filter(id => !options.value.some(row => row.id === id && row.selectable !== false))
  if (invalid.length) { error.value = normalizeError(new AppError('BUSINESS_RULE', '所选仪器已停用、校准资料不完整或有效期不能覆盖全部试验区间，请核对并移出不可用设备。')); return }
  error.value = ''
  if (options.value.some(row => ids.includes(row.id) && row.expiredNow && !acknowledged.value.includes(row.id))) {
    pendingSelection.value = { mode, ids: [...ids] }
    return
  }
  applySelection(mode, ids)
}
async function applyScheme(result: SchemeResolution) {
  const intervals = current.value.form.testDates.map(d => ({ start: d.from, end: d.kind === 'single' ? d.from : d.to }))
  const rows = result.rows.map(row => entryEquipment(row, intervals))
  const byId = new Map(options.value.map(row => [row.id, row]))
  rows.forEach(row => byId.set(row.id, row))
  result.skipped.forEach(row => {
    const existing = byId.get(row.id)
    if (existing) byId.set(row.id, { ...existing, selectable: false, validityNote: row.reason })
  })
  current.value = { ...current.value, options: { ...current.value.options, equipment: [...byId.values()] } }
  registrationDemo.entrySchemeEquipment?.(result.rows, result.skipped)
  selected.value = [...new Set([...selected.value, ...rows.map(row => row.id)])]
  await nextTick()
  acknowledged.value = [...new Set([...acknowledged.value, ...rows.filter(row => row.expiredNow).map(row => row.id)])]
}
function moveIn() { requestSelection('move', movable.value) }
function confirmSelection() { if (schemeBusy.value) return; requestSelection('select', selected.value) }
function continueSelection() {
  if (disabled.value || !pendingSelection.value) return
  const { mode, ids } = pendingSelection.value
  acknowledged.value = [...new Set([...acknowledged.value, ...warningRows.value.map(row => row.id)])]
  pendingSelection.value = undefined
  requestSelection(mode, ids)
}
function moveOut() { selected.value = selected.value.filter(id => !rightChecked.value.includes(id)); rightChecked.value = []; rightPage.value = Math.min(rightPage.value, Math.max(1, Math.ceil(selected.value.length / rightSize.value))) }
function openAssociation() { associating.value = true; candidates.value = []; keyword.value = ''; appliedKeyword.value = ''; department.value = ''; appliedDepartment.value = ''; cataloguePage.value = 1; error.value = ''; message.value = ''; confirmDefaults.value = false }
async function configure(action: 'equipment-associate' | 'equipment-defaults' | 'equipment-unset-defaults') {
  if (disabled.value) return
  const ids = action === 'equipment-associate' ? [...candidates.value] : action === 'equipment-unset-defaults' ? [...checkedDefaults.value] : [...leftChecked.value]
  if (!ids.length) return
  const token = generation
  busy.value = true; error.value = ''; message.value = ''
  try {
    const result = await registrationDemo.entryAction(current.value.sample.id, action, { ids, equipmentVersion: config.value.version, version: current.value.version, sampleVersion: current.value.sample.version, requestId: crypto.randomUUID() })
    if (token !== generation) return
    current.value = result; emit('refreshed', result); confirmDefaults.value = false
    if (action === 'equipment-associate') { associating.value = false; leftChecked.value = ids; filters.value = { code: '', name: '', serial: '' }; search(); candidates.value = [] }
    message.value = action === 'equipment-associate' ? '关联设备已保存到当前检测方案。' : action === 'equipment-unset-defaults' ? '已取消所选设备的方案默认设置。' : '默认设备已保存到当前检测方案，后续新录入样品将自动带入。'
  } catch (issue) { if (token === generation) { error.value = normalizeError(issue); stale.value = ['NETWORK', 'UNAVAILABLE', 'FORBIDDEN', 'NOT_FOUND'].includes(error.value.code) } }
  finally { if (token === generation) busy.value = false }
}
async function refresh() {
  if (busy.value) return
  const token = generation
  busy.value = true; error.value = ''
  try { const result = await registrationDemo.entryDetail(current.value.sample.id); if (token !== generation) return; current.value = result; emit('refreshed', result); stale.value = false; candidates.value = []; leftChecked.value = []; confirmDefaults.value = false }
  catch (issue) { if (token === generation) error.value = normalizeError(issue) }
  finally { if (token === generation) busy.value = false }
}
watch(() => props.detail, value => { current.value = value })
watch(leftChecked, () => { confirmDefaults.value = false })
watch(currentActor, () => { generation++; emit('close') })
</script>
<template>
  <BootstrapModal open :title="associating ? '新增关联设备' : '选择仪器设备'" size="xl" scrollable fullscreen-mobile fill-height :busy="busy || schemeBusy" body-class="px-3 pt-0 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <div class="mx-3"><ErrorNotice :error="error" /><div v-if="stale" class="mb-3"><button type="button" class="btn btn-light btn-sm" :disabled="busy" @click="refresh">刷新核对</button></div><TemplateToast :message="message" tone="success" auto-show within-modal /></div>
      <EquipmentSchemeBar v-if="!associating" :report-no="current.sample.id" :dates="current.form.testDates" :selected="selected" :disabled="disabled" @applied="applyScheme" @busy="schemeBusy = $event" />
      <p class="text-muted mb-2">显示当前授权范围内全部状态的仪器。是否可用于本次试验，按完整试验区间判断。</p>
      <form v-if="associating" class="mb-3" aria-label="新增关联设备查询" @submit.prevent="searchCatalogue">
        <fieldset :disabled="disabled"><div class="row gx-3 gy-2 align-items-center">
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-field" class="col-form-label text-nowrap">查询内容</label><select id="equipment-query-field" v-model="queryField" class="form-select"><option value="code">档案号</option><option value="name">设备名称</option><option value="manufacturer">生产厂家</option><option value="inspectionOrganization">检定单位</option><option value="storageOrganization">放置单位</option></select></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-keyword" class="col-form-label text-nowrap">包含</label><input id="equipment-query-keyword" v-model="keyword" class="form-control" size="1" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-group" class="col-form-label text-nowrap">设备分组</label><select id="equipment-query-group" class="form-select"><option value="">全部</option></select></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-department" class="col-form-label text-nowrap">所属部门</label><select id="equipment-query-department" v-model="department" class="form-select"><option value="">全部</option><option v-for="item in departments" :key="item" :value="item">{{ item }}</option></select></div>
          <div class="col-auto"><button class="btn btn-primary" type="submit">查询</button></div>
        </div></fieldset>
      </form>
      <form v-else class="mb-3" aria-label="关联设备查询" @submit.prevent="search">
        <fieldset :disabled="disabled"><div class="row gx-3 gy-2 align-items-center">
          <div v-for="([key, label]) in ([['code', '档案号'], ['serial', '出厂号'], ['name', '设备名称']] as const)" :key="key" class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label :for="'equipment-' + key" class="col-form-label text-nowrap">{{ label }}</label><input :id="'equipment-' + key" v-model="filters[key]" class="form-control" size="1" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-group" class="col-form-label text-nowrap">所属部门</label><select id="equipment-group" v-model="department" class="form-select"><option value="">全部</option><option v-for="item in departments" :key="item" :value="item">{{ item }}</option></select></div>
          <div class="col-auto d-flex flex-wrap gap-2"><button type="submit" class="btn btn-primary">查询</button><button type="button" class="btn btn-light" :disabled="true" title="请在方案管理中配置关联设备" @click="openAssociation"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增关联</button><button type="button" class="btn btn-light" :disabled="true" title="请在方案管理中配置默认设备" @click="confirmDefaults = allCheckedDefault ? 'unset' : 'set'">{{ allCheckedDefault ? '取消默认' : '设为默认' }}</button></div>
        </div></fieldset>
      </form>

    </template>
    <fieldset :disabled="disabled" class="h-100">
      <template v-if="associating"><div class="overflow-auto h-100"><DataEntryEquipmentTable catalogue :disabled="disabled" label="可关联设备" :rows="slice(catalogue, cataloguePage, catalogueSize)" v-model:checked="candidates" :unavailable="config.associatedIds" /></div></template>
      <div v-else class="row g-2 h-100 flex-lg-nowrap">
        <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="关联设备">
          <div class="card border shadow-none h-100 mb-0">
            <div class="card-header py-2"><h6 class="mb-0">关联设备 <span class="badge bg-light text-body">{{ config.associatedIds.length }}</span></h6></div>
            <div class="overflow-auto flex-grow-1"><DataEntryEquipmentTable enforce-eligibility :disabled="disabled" label="关联设备" :rows="slice(associated, leftPage, leftSize)" v-model:checked="leftChecked" :defaults="config.defaultIds" @unavailable="blockedEquipment = $event" /></div>
            <TablePagination label="关联设备" :total="associated.length" :page="leftPage" :page-size="leftSize" :sizes="[10, 20, 50]" @page="leftPage = $event" @size="leftSize = $event; leftPage = 1" />
          </div>
        </section>
        <div class="col-12 col-lg-auto flex-shrink-0 d-flex flex-lg-column align-items-center justify-content-center gap-2">
          <button type="button" class="btn btn-primary btn-sm btn-icon" aria-label="移入" title="移入" :disabled="!movable.length" @click="moveIn"><i class="ti ti-arrow-right d-none d-lg-inline" aria-hidden="true"></i><i class="ti ti-arrow-down d-lg-none" aria-hidden="true"></i></button>
          <button type="button" class="btn btn-light btn-sm btn-icon" aria-label="移出" title="移出" :disabled="!rightChecked.length" @click="moveOut"><i class="ti ti-arrow-left d-none d-lg-inline" aria-hidden="true"></i><i class="ti ti-arrow-up d-lg-none" aria-hidden="true"></i></button>
        </div>
        <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="已选设备"><div class="card border shadow-none h-100 mb-0">
          <div class="card-header py-2"><h6 class="mb-0">已选设备 <span class="badge bg-light text-body">{{ selected.length }}</span></h6></div>
          <div class="overflow-auto flex-grow-1"><DataEntryEquipmentTable :disabled="disabled" label="已选设备" :rows="slice(selectedRows, rightPage, rightSize)" v-model:checked="rightChecked" :defaults="config.defaultIds" /></div>
          <TablePagination label="已选设备" :total="selected.length" :page="rightPage" :page-size="rightSize" :sizes="[10, 20, 50]" @page="rightPage = $event" @size="rightSize = $event; rightPage = 1" />
        </div></section>
      </div>
    </fieldset>
    <template #pagination><fieldset v-if="associating" :disabled="disabled"><TablePagination label="可关联设备" :total="catalogue.length" :page="cataloguePage" :page-size="catalogueSize" :sizes="[10, 20, 50]" extended @page="cataloguePage = $event" @size="catalogueSize = $event; cataloguePage = 1" /></fieldset></template>
    <template #footer>
      <span class="me-auto text-muted">{{ associating ? '勾选 ' + candidates.length + ' 台设备' : '已选 ' + selected.length + ' 台设备' }}</span>
      <button class="btn btn-light" type="button" :disabled="busy" @click="associating ? associating = false : emit('close')">{{ associating ? '返回' : '取消' }}</button>
      <button class="btn btn-primary" type="button" :disabled="disabled || schemeBusy || (associating && !candidates.length)" @click="associating ? configure('equipment-associate') : confirmSelection()">确定</button>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="blockedEquipment" title="该仪器不能用于本次试验" @close="blockedEquipment = undefined"><p class="text-break">{{ blockedEquipment.code }} {{ blockedEquipment.name }}：{{ blockedEquipment.validityNote }}。该仪器不能加入已选列表。</p><p class="text-break">本次试验时间：{{ trialPeriod }}</p><p>最近校准日期：{{ blockedEquipment.lastCalibrationDate || '未登记' }}；有效期至：{{ blockedEquipment.validUntil || '未登记' }}。</p><template #footer><button type="button" class="btn btn-primary" @click="blockedEquipment = undefined">知道了</button></template></ConfirmationModal>
  <ConfirmationModal v-if="pendingSelection" title="仪器当前已过期" @close="pendingSelection = undefined"> <p>以下仪器目前已过期，但校准有效期覆盖本次全部试验区间。是否继续选择？</p> <p class="text-break">本次试验时间：{{ trialPeriod }}</p> <ul class="mb-0 ps-3"> <li v-for="item in warningRows" :key="item.id" class="mb-2 text-break">{{ item.code }} {{ item.name }}：最近校准日期 {{ item.lastCalibrationDate || '未登记' }}，有效期至 {{ item.validUntil }}。</li> </ul> <template #footer><button type="button" class="btn btn-light" @click="pendingSelection = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="disabled" @click="continueSelection">继续选择</button></template> </ConfirmationModal>
  <ConfirmationModal v-if="confirmDefaults" :title="confirmDefaults === 'unset' ? '取消默认设备' : '设置默认设备'" :busy="busy" @close="confirmDefaults = false">
    <p v-if="confirmDefaults === 'unset'" class="text-break">取消勾选的 {{ checkedDefaults.length }} 台设备的方案默认设置？后续新录入样品不再自动带入这些设备，当前已选设备不变。</p>
    <p v-else class="text-break">将勾选的 {{ leftChecked.length }} 台设备设为当前检测方案的默认设备？后续新录入样品将自动带入，其他默认设备和当前已选设备不变。</p>
    <ErrorNotice :error="error" /><button v-if="stale" class="btn btn-light" :disabled="busy" @click="refresh">刷新核对</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="confirmDefaults = false">取消</button><button type="button" class="btn btn-primary" :disabled="disabled || (confirmDefaults === 'unset' ? !checkedDefaults.length : !leftChecked.length)" @click="configure(confirmDefaults === 'unset' ? 'equipment-unset-defaults' : 'equipment-defaults')">{{ busy ? '正在保存…' : confirmDefaults === 'unset' ? '确认取消默认' : '确认设置' }}</button></template>
  </ConfirmationModal>
</template>

