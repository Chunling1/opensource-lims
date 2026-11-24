<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import BootstrapModal from '../common/BootstrapModal.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import TablePagination from '../common/table/TablePagination.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateToast from '../common/TemplateToast.vue'
import DataEntryEquipmentTable from './DataEntryEquipmentTable.vue'
import { useUnsavedChanges } from '../common/useUnsavedChanges'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import type { EntryDetail, EntryEquipment } from '../../types/testing/dataEntryDetail'

const props = defineProps<{ detail: EntryDetail; value: string[] }>()
const emit = defineEmits<{ close: []; select: [string[]]; refreshed: [EntryDetail] }>()
const selected = ref([...props.value]), leftChecked = ref<string[]>([]), rightChecked = ref<string[]>([]), candidates = ref<string[]>([])
const associating = ref(false), busy = ref(false), stale = ref(false), confirmDefaults = ref<false | 'set' | 'unset'>(false), error = ref<ErrorValue>(''), message = ref('')
const current = ref(props.detail), config = computed(() => current.value.equipmentConfig), options = computed(() => current.value.options.equipment)
const filters = ref({ code: '', name: '', serial: '' }), applied = ref({ ...filters.value })
const queryField = ref<'code' | 'name' | 'manufacturer' | 'inspectionOrganization' | 'storageOrganization'>('name'), keyword = ref(''), appliedKeyword = ref(''), appliedField = ref(queryField.value)
const department = ref(''), appliedDepartment = ref('')
const departments = computed(() => registrationDepartments.filter(row => currentActor.value.scope === 'all' || row.id === currentActor.value.departmentId))
const leftPage = ref(1), rightPage = ref(1), cataloguePage = ref(1), leftSize = ref(10), rightSize = ref(10), catalogueSize = ref(10)
const associated = computed(() => options.value.filter(row => config.value.associatedIds.includes(row.id)).filter(row => (['code', 'name', 'serial'] as const).every(key => !applied.value[key] || row[key].toLocaleLowerCase().includes(applied.value[key].toLocaleLowerCase()))))
const selectedRows = computed(() => selected.value.map(id => options.value.find(row => row.id === id) || { id, code: id, name: '设备已不可选', model: '', manufacturer: '', serial: '' }))
const catalogue = computed(() => options.value.filter(row => (!appliedDepartment.value || row.departmentId === appliedDepartment.value) && (!appliedKeyword.value || (row[appliedField.value] || '').toLocaleLowerCase().includes(appliedKeyword.value.toLocaleLowerCase()))))
const slice = (rows: EntryEquipment[], page: number, size: number) => rows.slice((page - 1) * size, page * size)
const movable = computed(() => leftChecked.value.filter(id => !selected.value.includes(id)))
const checkedDefaults = computed(() => leftChecked.value.filter(id => config.value.defaultIds.includes(id)))
const allCheckedDefault = computed(() => leftChecked.value.length > 0 && checkedDefaults.value.length === leftChecked.value.length)
const disabled = computed(() => busy.value || stale.value || !current.value.capabilities.canEdit)
useUnsavedChanges(busy)
let generation = 0
onBeforeRouteLeave(() => busy.value ? false : undefined)
onBeforeRouteUpdate(() => busy.value ? false : undefined)
onBeforeUnmount(() => { generation++ })
function search() { applied.value = Object.fromEntries(Object.entries(filters.value).map(([key, value]) => [key, value.trim()])) as typeof filters.value; leftPage.value = 1 }
function searchCatalogue() { appliedKeyword.value = keyword.value.trim(); appliedField.value = queryField.value; appliedDepartment.value = department.value; cataloguePage.value = 1 }
function moveIn() { selected.value = [...new Set([...selected.value, ...movable.value])]; leftChecked.value = []; message.value = '' }
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
  <BootstrapModal open :title="associating ? '新增关联设备' : '选择仪器设备'" size="xl" scrollable fullscreen-mobile fill-height :busy="busy" body-class="px-3 pt-0 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <div class="mx-3"><ErrorNotice :error="error" /><div v-if="stale" class="mb-3"><button type="button" class="btn btn-light btn-sm" :disabled="busy" @click="refresh">刷新核对</button></div><TemplateToast :message="message" tone="success" auto-show within-modal /></div>
      <form v-if="associating" class="mb-3" aria-label="新增关联设备查询" @submit.prevent="searchCatalogue">
        <fieldset :disabled="disabled"><div class="row gx-3 gy-2 align-items-center">
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-field" class="col-form-label text-nowrap">查询内容</label><select id="equipment-query-field" v-model="queryField" class="form-select"><option value="code">档案号</option><option value="name">设备名称</option><option value="manufacturer">生产厂家</option><option value="inspectionOrganization">检定单位</option><option value="storageOrganization">放置单位</option></select></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-keyword" class="col-form-label text-nowrap">包含</label><input id="equipment-query-keyword" v-model="keyword" class="form-control" size="1" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-group" class="col-form-label text-nowrap">设备分组</label><select id="equipment-query-group" class="form-select"><option value="">全部</option></select></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-query-department" class="col-form-label text-nowrap">所属部门</label><select id="equipment-query-department" v-model="department" class="form-select"><option value="">全部</option><option v-for="item in departments" :key="item.id" :value="item.id">{{ item.name }}</option></select></div>
          <div class="col-auto"><button class="btn btn-primary" type="submit">查询</button></div>
        </div></fieldset>
      </form>
      <form v-else class="mb-3" aria-label="关联设备查询" @submit.prevent="search">
        <fieldset :disabled="disabled"><div class="row gx-3 gy-2 align-items-center">
          <div v-for="([key, label]) in ([['code', '档案号'], ['serial', '出厂号'], ['name', '设备名称']] as const)" :key="key" class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label :for="'equipment-' + key" class="col-form-label text-nowrap">{{ label }}</label><input :id="'equipment-' + key" v-model="filters[key]" class="form-control" size="1" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl d-flex align-items-center gap-2"><label for="equipment-group" class="col-form-label text-nowrap">设备分组</label><select id="equipment-group" class="form-select"><option value="">全部</option></select></div>
          <div class="col-auto d-flex flex-wrap gap-2"><button type="submit" class="btn btn-primary">查询</button><button type="button" class="btn btn-light" @click="openAssociation"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增关联</button><button type="button" class="btn btn-light" :disabled="!leftChecked.length" @click="confirmDefaults = allCheckedDefault ? 'unset' : 'set'">{{ allCheckedDefault ? '取消默认' : '设为默认' }}</button></div>
        </div></fieldset>
      </form>

    </template>
    <fieldset :disabled="disabled" class="h-100">
      <template v-if="associating"><div class="overflow-auto h-100"><DataEntryEquipmentTable catalogue :disabled="disabled" label="可关联设备" :rows="slice(catalogue, cataloguePage, catalogueSize)" v-model:checked="candidates" :unavailable="config.associatedIds" /></div></template>
      <div v-else class="row g-2 h-100 flex-lg-nowrap">
        <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="关联设备">
          <div class="card border shadow-none h-100 mb-0">
            <div class="card-header py-2"><h6 class="mb-0">关联设备 <span class="badge bg-light text-body">{{ config.associatedIds.length }}</span></h6></div>
            <div class="overflow-auto flex-grow-1"><DataEntryEquipmentTable :disabled="disabled" label="关联设备" :rows="slice(associated, leftPage, leftSize)" v-model:checked="leftChecked" :defaults="config.defaultIds" /></div>
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
      <button class="btn btn-primary" type="button" :disabled="disabled || (associating && !candidates.length)" @click="associating ? configure('equipment-associate') : emit('select', [...selected])">确定</button>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="confirmDefaults" :title="confirmDefaults === 'unset' ? '取消默认设备' : '设置默认设备'" :busy="busy" @close="confirmDefaults = false">
    <p v-if="confirmDefaults === 'unset'" class="text-break">取消勾选的 {{ checkedDefaults.length }} 台设备的方案默认设置？后续新录入样品不再自动带入这些设备，当前已选设备不变。</p>
    <p v-else class="text-break">将勾选的 {{ leftChecked.length }} 台设备设为当前检测方案的默认设备？后续新录入样品将自动带入，其他默认设备和当前已选设备不变。</p>
    <ErrorNotice :error="error" /><button v-if="stale" class="btn btn-light" :disabled="busy" @click="refresh">刷新核对</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="confirmDefaults = false">取消</button><button type="button" class="btn btn-primary" :disabled="disabled || (confirmDefaults === 'unset' ? !checkedDefaults.length : !leftChecked.length)" @click="configure(confirmDefaults === 'unset' ? 'equipment-unset-defaults' : 'equipment-defaults')">{{ busy ? '正在保存…' : confirmDefaults === 'unset' ? '确认取消默认' : '确认设置' }}</button></template>
  </ConfirmationModal>
</template>

