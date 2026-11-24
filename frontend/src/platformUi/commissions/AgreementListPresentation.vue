<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import ProjectImportModal from '../../components/customers/ProjectImportModal.vue'
import CustomerProjectModal from '../../components/customers/CustomerProjectModal.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {data:{items:Record<string,any>[];total:number;page:number;pageSize:number};rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {canDelete,registrationDemo,parseTableColumns,normalizeError,downloadBlob,currentActor,canManageProjects,projectColumns,route,router,text,query,draft,fields,canWrite,canCreate,data,selected,loading,exporting,error,exportError,columnKeys,columns,modal,toast,message,importing,modalKey,toolbarActions,toolbarAction,patch,epoch,exportEpoch,controller,load,search,toggleColumn,saved,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading title="合同登记" />
  <section class="card" aria-label="合同项目列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">合同项目</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div>
      <TableToolbar label="合同项目" :adaptive-actions="toolbarActions" @action="toolbarAction" :columns="projectColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button v-if="canCreate" type="button" class="btn btn-primary text-nowrap" :disabled="loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" aria-label="合同查询" @submit.prevent="search"><QueryFormLayout>
      <div class="row g-3"><div v-for="field in fields" :key="field.key" class="col-12 col-md-4"><label :for="`project-filter-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`project-filter-${field.key}`" v-model="draft[field.key]" class="form-control" :type="field.type || 'text'" :placeholder="field.placeholder" maxlength="200" /></div></div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
    </QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="合同项目" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.name || row.code" v-model:selected="selected" :loading="loading" :error="error" preserve-rows-on-loading :pagination="{ ...data, sizes: [10, 20, 50] }" @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }">
        <button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>编辑</button>
        <button type="button" class="dropdown-item" role="menuitem" :disabled="!canDelete(row)" @click="modal = { mode: 'delete', row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
      </template>
    </DataTable>
  </section>
  <CustomerProjectModal v-if="modal" :key="modal.key" :mode="modal.mode" :row="modal.row" :ids="modal.ids" @close="modal = undefined" @saved="saved" />
  <ProjectImportModal v-if="importing" @close="importing = false" @saved="saved(false, $event)" />
  <TemplateToast ref="toast" :message="message" />
</template>
