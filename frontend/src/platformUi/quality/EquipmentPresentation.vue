<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import EquipmentModal from '../../components/quality/EquipmentModal.vue'
import EquipmentDeleteModal from '../../components/quality/EquipmentDeleteModal.vue'
import EquipmentBatchModal from '../../components/quality/EquipmentBatchModal.vue'
import EquipmentGroupsModal from '../../components/quality/EquipmentGroupsModal.vue'
import EquipmentImportModal from '../../components/quality/EquipmentImportModal.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import {toRefs, ref} from 'vue'
import EquipmentSchemeManager from '../testing/EquipmentSchemeManager.vue'
const schemeManagerOpen = ref(false)
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number;departments:{id:string;name:string}[]};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {departmentMode,canCreate,canUpdate,canDelete,emptyEquipment,registrationDemo,parseTableColumns,normalizeError,clientYearRange,downloadBlob,currentActor,equipmentLedgerColumns,equipmentStates,equipmentStatusClasses,equipmentDateFields,title,route,router,dates,text,appliedDateField,query,draft,more,dateInput,activeFilters,textFields,toolbarActions,rows,selected,loading,error,exportError,exporting,modal,modalKey,message,toast,canWrite,deleting,batchRecords,groupIds,importing,openBatch,imported,groupsSaved,batchSaved,refreshBatch,equipmentDeleted,equipmentSaved,columnKeys,columns,epoch,exportEpoch,controller,patch,load,search,toggleColumn,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <EquipmentSchemeManager v-if="schemeManagerOpen" @close="schemeManagerOpen = false" />
  <section class="card" aria-label="设备台账列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex flex-wrap align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar label="设备台账" :adaptive-actions="toolbarActions" :columns="equipmentLedgerColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows" @action="openBatch">
        <button type="button" class="btn btn-light text-nowrap" @click="schemeManagerOpen = true">仪器方案</button>
        <button v-if="!departmentMode" type="button" class="btn btn-primary text-nowrap" :disabled="!canCreate || loading" @click="modal = { key: ++modalKey }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button>
      </TableToolbar>
    </div>
    <p v-if="!departmentMode" class="px-3 pt-3 mb-0 text-body small">Excel 导入：记录ID留空为新增，同档案号可保留多条仪器；更新请先导出并保留记录ID。旧表没有记录ID列时全部作为新增。</p>
    <form class="card-body border-bottom" aria-label="设备台账查询" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-start"><div v-for="field in textFields" :key="field.key" class="col-12 col-sm-6 col-xl-4"><label class="form-label" :for="`ledger-${field.key}`">{{ field.label }}</label><input :id="`ledger-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" /></div></div>
        <div v-show="more" id="equipment-ledger-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-serial" class="form-label">仪器出厂号</label><input id="ledger-serial" v-model="draft.serial" disabled title="现平台设备查询接口暂未提供此筛选条件" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-department" class="form-label">所属部门</label><select id="ledger-department" v-model="draft.departmentId" :disabled="departmentMode" class="form-select"><option value="">全部</option><option v-for="department in rows.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-status" class="form-label">设备状态</label><select id="ledger-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in equipmentStates" :key="status" :value="status">{{ status }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-date-field" class="form-label">日期类型</label><select id="ledger-date-field" v-model="draft.dateField" disabled title="现平台设备查询接口暂未提供此筛选条件" class="form-select"><option value="">不限</option><option v-for="field in equipmentDateFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-4"><label for="ledger-dates" class="form-label">日期范围</label><TemplateDateRange id="ledger-dates" ref="dateInput" :from="draft.from" :to="draft.to" :disabled="!draft.dateField" @change="Object.assign(draft, $event)" /></div>
          <div class="col-12 col-xl-4">
            <span class="form-label d-none d-xl-block invisible" aria-hidden="true">筛选范围</span>
            <div class="d-flex flex-wrap align-items-center gap-3 py-2"><label class="form-check mb-0 text-nowrap"><input v-model="draft.ownDepartment" type="checkbox" class="form-check-input" :disabled="true" /><span class="form-check-label">本部门设备</span></label><label class="form-check mb-0 text-nowrap"><input v-model="draft.unassociated" disabled title="现平台设备查询接口暂未提供此筛选条件" type="checkbox" class="form-check-input" /><span class="form-check-label">未关联部门设备</span></label></div>
          </div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button type="button" class="btn btn-link text-nowrap" :aria-expanded="more" aria-controls="equipment-ledger-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="设备台账" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })">
      <template #cell-status="{ row }"><span class="badge" :class="equipmentStatusClasses[row.status]">{{ row.status }}</span></template>
      <template v-for="key in ['usageRecordCount', 'manualCount', 'certificateCount', 'acceptanceCount'] as const" :key="key" #[`cell-${key}`]="{ row }">{{ row[key] || '—' }}</template>
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { key: ++modalKey, mode: 'view', recordId: row.id }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canUpdate" @click="modal = { key: ++modalKey, mode: 'edit', recordId: row.id }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canDelete" @click="deleting = row"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <EquipmentModal v-if="modal" :key="modal.key" :mode="modal.mode" :record-id="modal.recordId" :initial="modal.initial" @close="modal = undefined" @saved="equipmentSaved" />
  <EquipmentDeleteModal v-if="deleting" :key="deleting.id" :row="deleting" @close="deleting = undefined" @deleted="equipmentDeleted" />
  <EquipmentBatchModal v-if="batchRecords?.length" :records="batchRecords" @close="batchRecords = undefined" @saved="batchSaved" @refresh="refreshBatch" />
  <EquipmentGroupsModal v-if="groupIds?.length" :ids="groupIds" @close="groupIds = undefined" @saved="groupsSaved" />
  <EquipmentImportModal v-if="importing" @close="importing = false" @saved="imported" />
  <TemplateToast ref="toast" :message="message" />
</template>
