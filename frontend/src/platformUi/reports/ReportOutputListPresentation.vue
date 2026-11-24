<script setup lang="ts">
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {toolbarActions,toolbarAction,busy,reportPrintColumns,reportPrintStates,reportPrintStatuses,reportPrintDateFields,reportPrintSearchFields,reportSigningColumns,reportSigningStates,reportSigningStatuses,reportDistributionSearchFields,reportDistributionDateFields,reportDistributionStatusLabels,reportCollectionMethods,reportDistributionColumns,reportDistributionStates,reportDistributionStatuses,reportArchiveColumns,reportArchiveStatuses,reportArchiveStatusLabels,reportArchiveDateFields,reportOperationIcons,emptyPlanSelection,normalizeConclusion,assignmentConclusions,sampleTypes,registrationDemo,clientYearRange,normalizeError,parseTableColumns,downloadBlob,currentActor,emit,archive,signing,distribution,title,root,prefix,defaultDateField,metadata,states,statuses,searchFields,dateFields,statusKey,defaultStatus,defaultState,route,router,dates,text,ids,plans,planState,drawer,planFilter,planBusy,planError,applyPlans,query,draft,more,activeFilters,dateInput,emptyPage,rows,selected,loading,error,exporting,exportError,columnKeys,columns,sequence,exportSequence,controller,timer,scheduleRefresh,load,patch,search,toggleColumn,exportRows}=toRefs(props.context)
</script>
<template>
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span>
        <button v-if="context.canBatch" type="button" class="btn btn-primary text-nowrap"
          :disabled="loading || !!error || context.batchBusy || !context.batchCount"
          :aria-busy="context.batchBusy" @click="context.completeSelected()">
          批量{{ context.batchLabel }}<span v-if="context.batchCount">（{{ context.batchCount }}）</span>
        </button>
      </div>
      <TableToolbar :adaptive-actions="toolbarActions" @action="toolbarAction" :label="title" :columns="metadata" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><slot name="finance" />
        <div v-if="distribution" class="d-flex flex-column flex-sm-row gap-2">
          <button v-for="option in [{kind:'product',label:'产品类发放表'},{kind:'engineering',label:'工程类发放表'}]" :key="option.kind" type="button" class="btn btn-light text-nowrap" :disabled="loading || !selected.length || context.issuanceExportBusy" :aria-busy="context.issuanceExportBusy" @click="context.exportIssuanceRecord(option.kind)">{{ option.label }}</button>
        </div>
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="query-fields">
          <div class="query-field query-field--group"><label for="reportoutputlistpresentation-group" class="form-label">数据分组</label><select id="reportoutputlistpresentation-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
          <div class="query-field query-field--search"><label :for="`${prefix}-field`" class="form-label">查询内容</label><select :id="`${prefix}-field`" v-model="draft.searchField" class="form-select"><option v-for="field in searchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
          <div class="query-field query-field--keyword"><label :for="`${prefix}-contains`" class="form-label">包含</label><input :id="`${prefix}-contains`" v-model="draft.contains" class="form-control" maxlength="200" /></div>
          <div v-if="archive" class="query-field query-field--status"><label :for="`${prefix}-state`" class="form-label">数据状态</label><select :id="`${prefix}-state`" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="state in statuses" :key="state" :value="state">{{ reportArchiveStatusLabels[state] }}</option></select></div>
          <div v-else class="query-field query-field--status"><label :for="`${prefix}-status`" class="form-label">数据状态</label><select :id="`${prefix}-status`" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in states" :key="status">{{ status }}</option></select></div>
          <div class="query-field query-field--type"><label :for="`${prefix}-type`" class="form-label">样品类型</label><select :id="`${prefix}-type`" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" :id="`${prefix}-more-filters`" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4" :class="distribution ? 'col-xl-2' : 'col-xl-3'"><label :for="`${prefix}-conclusion`" class="form-label">结论状态</label><select :id="`${prefix}-conclusion`" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8" :class="archive ? 'col-xl-9' : 'col-xl-6'">
            <label :for="`${prefix}-dates`" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in dateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange :id="`${prefix}-dates`" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
          <div v-if="!archive" class="col-12 col-md-4" :class="distribution ? 'col-xl-2' : 'col-xl-3'"><label :for="`${prefix}-state`" class="form-label">{{ distribution ? '发放状态' : '状态' }}</label><select :id="`${prefix}-state`" v-model="draft.state" class="form-select"><option value="">全部</option><option v-for="state in statuses" :key="state" :value="state">{{ distribution ? reportDistributionStatusLabels[state] : state }}</option></select></div>
          <div v-if="distribution" class="col-12 col-md-4 col-xl-2"><label :for="`${prefix}-collection-method`" class="form-label">报告交付方式</label><select :id="`${prefix}-collection-method`" v-model="draft.collectionMethod" class="form-select"><option value="">全部</option><option v-for="method in reportCollectionMethods" :key="method">{{ method }}</option></select></div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" :aria-controls="`${prefix}-more-filters`" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <div v-if="distribution && context.issuanceExportError" class="px-3 pt-3"><ErrorNotice :error="context.issuanceExportError" /></div>
    <p v-if="context.canBatch && context.batchProgress?.total" class="px-3 pt-3 mb-2" role="status">
      正在批量{{ context.batchLabel }}，已处理 {{ context.batchProgress.done }} / {{ context.batchProgress.total }} 份
    </p>
    <div v-if="context.batchResult" class="mx-3 mt-3 alert"
      :class="context.batchResult.failures.length ? 'alert-warning' : 'alert-success'" role="status">
      批量{{ context.batchResult.label }}完成，成功 {{ context.batchResult.succeeded }} 份，未确认成功 {{ context.batchResult.failures.length }} 份
      <ul v-if="context.batchResult.failures.length" class="mt-2 mb-0">
        <li v-for="failure in context.batchResult.failures" :key="failure.reportNo">{{ failure.reportNo }} · {{ failure.reason }}</li>
      </ul>
    </div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-archiveStatus="{ row }">{{ archive ? reportArchiveStatusLabels[row.archiveStatus] || row.archiveStatus : row.archiveStatus }}</template>
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button v-for="action in row.actions" :key="action.id" type="button" role="menuitem" class="dropdown-item" :disabled="loading || busy || !action.enabled" :title="action.reason" @click="emit('action', row, action.id)"><i :class="reportOperationIcons[action.id]" class="me-2 text-muted" aria-hidden="true"></i>{{ action.label }}</button>
      </template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" :sample-scope="archive ? 'report-archive' : distribution ? 'report-distribution' : signing ? 'report-signing' : 'report-print'" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
</template>
