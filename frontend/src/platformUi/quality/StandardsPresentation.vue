<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import StandardModal from '../../components/quality/StandardModal.vue'
import StandardGroupsModal from '../../components/quality/StandardGroupsModal.vue'
import StandardImportModal from '../../components/quality/StandardImportModal.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {data:{items:Record<string,any>[];total:number;page:number;pageSize:number;locations:string[];departments:{id:string;name:string}[]};rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {departmentMode,canCreate,canDelete,masterMode,registrationDemo,parseTableColumns,normalizeError,downloadBlob,currentActor,canManageStandards,canEditStandard,standardColumns,standardQualifications,title,route,router,text,query,draft,more,groupIds,importing,textFields,activeFilters,canWrite,data,selected,toolbarActions,action,relatedSaved,loading,exporting,error,exportError,columnKeys,columns,modal,toast,message,patch,epoch,exportEpoch,controller,load,search,toggleColumn,saved,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar :label="title" :adaptive-actions="toolbarActions" @action="action" :columns="standardColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button v-if="!departmentMode" type="button" class="btn btn-primary text-nowrap" :disabled="!canCreate || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div v-for="field in textFields" :key="field.key" class="col-12 col-sm-6 col-xl-3"><label :for="`standard-query-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`standard-query-${field.key}`" v-model="draft[field.key]" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-qualification" class="form-label">标准资质类别</label><select id="standard-query-qualification" v-model="draft.qualification" :disabled="masterMode" class="form-select"><option value="">全部</option><option v-for="value in standardQualifications" :key="value" :value="value">{{ value }}</option></select></div>
      </div>
      <div v-show="more" id="standard-more-filters" class="row g-3 mt-0">
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-controlNumber" class="form-label">受控号</label><input id="standard-query-controlNumber" v-model="draft.controlNumber" disabled title="现平台查询接口暂未提供此独立筛选条件，可使用关键词查询" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-location" class="form-label">存放地点</label><select id="standard-query-location" v-model="draft.location" disabled title="现平台查询接口暂未提供此独立筛选条件，可使用关键词查询" class="form-select"><option value="">全部</option><option v-for="value in data.locations" :key="value" :value="value">{{ value }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-3"><label for="standard-query-department" class="form-label">使用部门</label><select id="standard-query-department" v-model="draft.departmentId" :disabled="departmentMode || masterMode" class="form-select"><option value="">全部</option><option v-for="department in data.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select></div>
        <div class="col-12 col-sm-6 col-xl-3 d-flex align-items-end"><label class="form-check mb-2"><input v-model="draft.ownDepartment" type="checkbox" class="form-check-input" :disabled="true" /><span class="form-check-label">本部门标准</span></label></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button type="button" class="btn btn-link text-nowrap" :aria-expanded="more" aria-controls="standard-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #cell-outsideScope="{ row }">{{ row.outsideScope ? '是' : '否' }}</template><template #cell-english="{ row }">{{ row.english ? '是' : '否' }}</template>
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canEditStandard(currentActor, row)" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button v-if="!departmentMode" type="button" class="dropdown-item" role="menuitem" :disabled="!canDelete" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <StandardModal v-if="modal" :mode="modal.mode" :row="modal.row" @close="modal = undefined" @saved="saved" />
  <StandardGroupsModal v-if="groupIds?.length" :ids="groupIds" @close="groupIds = undefined" @saved="relatedSaved()" />
  <StandardImportModal v-if="importing" @close="importing = false" @saved="relatedSaved" />
  <TemplateToast ref="toast" :message="message" />
</template>
