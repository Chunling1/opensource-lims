<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import PersonnelModal from '../../components/quality/PersonnelModal.vue'
import PersonnelImportModal from '../../components/quality/PersonnelImportModal.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {canCreate,canUpdate,canDelete,queryMode,registrationDemo,parseTableColumns,normalizeError,downloadBlob,currentActor,personnelColumns,personnelOptions,title,queryLabel,route,router,text,fields,query,draft,more,primaryFields,extraFields,activeFilters,rows,loading,error,actionError,exporting,selected,message,successToast,columnKeys,columns,modal,importing,canWrite,toolbarActions,toolbarAction,epoch,actionEpoch,controller,patch,load,search,toggleColumn,download,saved}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :adaptive-actions="toolbarActions" :columns="personnelColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @action="toolbarAction" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="download(false, $event)">
        <button v-if="!queryMode" type="button" class="btn btn-primary text-nowrap" :disabled="!canCreate || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="queryLabel" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-end"><div v-for="f in primaryFields" :key="f.key" class="col-12 col-sm-6" :class="queryMode ? 'col-xl-4' : 'col-xl-3'">
          <label :for="`personnel-query-${f.key}`" class="form-label">{{ f.label }}</label>
          <select v-if="f.options" :id="`personnel-query-${f.key}`" v-model="draft[f.key]" class="form-select"><option value="">全部</option><option v-for="option in f.options" :key="option" :value="option">{{ option }}</option></select>
          <input v-else :id="`personnel-query-${f.key}`" v-model="draft[f.key]" class="form-control" maxlength="200" />
        </div></div>
        <div v-if="queryMode" v-show="more" id="personnel-query-more-filters" class="row g-3 align-items-end mt-0">
          <div v-for="f in extraFields" :key="f.key" class="col-12 col-sm-6 col-xl-4"><label :for="`personnel-query-${f.key}`" class="form-label">{{ f.label }}</label><input :id="`personnel-query-${f.key}`" v-model="draft[f.key]" class="form-control" maxlength="200" /></div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button v-if="queryMode" class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="personnel-query-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="r => r.id" :row-label="r => r.name" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })">
      <template #actions="{ row }">
        <button v-if="!queryMode" class="dropdown-item" role="menuitem" :disabled="!canUpdate" @click="modal = { mode: 'edit', record: row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', record: row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button v-if="!queryMode" class="dropdown-item" role="menuitem" :disabled="!canDelete" @click="modal = { mode: 'delete', record: row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <TemplateToast ref="successToast" :message="message" tone="success" />
  <PersonnelModal v-if="modal" :key="`${modal.mode}:${modal.record?.id || ''}`" v-bind="modal" @close="modal = undefined" @saved="saved(modal?.mode === 'delete' ? '人员已删除。' : '人员已保存。')" />
  <PersonnelImportModal v-if="importing" @close="importing = false" @saved="saved(`成功导入 ${$event} 条人员记录。`)" />
</template>
