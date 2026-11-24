<script setup lang="ts">
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TaskProcessingModal from '../../components/testing/TaskProcessingModal.vue'
import ReportQuickReviewModal from '../../components/reports/ReportQuickReviewModal.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import type { RegistrationSample } from '../../types/commissions/registration'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {stage:"review"|"approval";rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {stage,emptyPlanSelection,normalizeConclusion,assignmentConclusions,reportStages,reportStageColumns,reportStageActions,reportStageDates,reportCheckSearchFields,sampleTypes,registrationDemo,clientYearRange,normalizeError,parseTableColumns,downloadBlob,currentActor,config,title,root,defaultDateField,reportCheckColumns,reportCheckActions,reportCheckDateFields,reportCheckStates,reportCheckStatuses,route,router,dates,text,ids,plans,planState,drawer,planFilter,planBusy,planError,applyPlans,query,draft,more,activeFilters,dateInput,emptyPage,rows,selected,loading,error,quickIds,canQuickReview,toolbarActions,openQuickReview,closeQuickReview,exporting,exportError,attachmentId,processingTarget,statusAction,actionBusy,statusError,voidRecord,voidRequest,openVoid,undoCheck,actionAllowed,rowAction,columnKeys,columns,sequence,exportSequence,controller,load,patch,search,toggleColumn,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :adaptive-actions="toolbarActions" @action="drawer = true" :columns="reportCheckColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-primary text-nowrap" :disabled="!canQuickReview" :title="'现平台按报告逐项确认合规，请使用行菜单处理'" @click="openQuickReview"><i class="ti ti-clipboard-list me-1" aria-hidden="true"></i>快速{{ config.label }}</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="query-fields">
          <div class="query-field query-field--group"><label for="reportstagepresentation-group" class="form-label">数据分组</label><select id="reportstagepresentation-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
          <div class="query-field query-field--search"><label for="report-check-field" class="form-label">查询内容</label><select id="report-check-field" v-model="draft.searchField" class="form-select"><option v-for="field in reportCheckSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
          <div class="query-field query-field--keyword"><label for="report-check-contains" class="form-label">包含</label><input id="report-check-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
          <div class="query-field query-field--status"><label for="report-check-status" class="form-label">数据状态</label><select id="report-check-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in reportCheckStates" :key="status">{{ status }}</option></select></div>
          <div class="query-field query-field--type"><label for="report-check-type" class="form-label">样品类型</label><select id="report-check-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" id="report-check-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4 col-xl-3"><label for="report-check-conclusion" class="form-label">结论状态</label><select id="report-check-conclusion" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8 col-xl-6">
            <label for="report-check-dates" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in reportCheckDateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange id="report-check-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
          <div class="col-12 col-md-4 col-xl-3"><label for="report-check-state" class="form-label">状态</label><select id="report-check-state" v-model="draft.checkStatus" class="form-select"><option value="">全部</option><option v-for="state in reportCheckStatuses" :key="state">{{ state }}</option></select></div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="report-check-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button v-for="action in reportCheckActions" :key="action.label" type="button" role="menuitem" class="dropdown-item" :disabled="loading || actionBusy || !actionAllowed(row, action.label)" @click="rowAction(row, action.label)">
          <i :class="action.icon" class="me-2 text-muted" aria-hidden="true"></i>{{ action.label }}
        </button>
      </template>
    </DataTable>
  </section>
  <BootstrapModal v-if="statusAction" open :title="`撤销${config.label}`" :busy="actionBusy" @close="!actionBusy && (statusAction = undefined)">
    <p class="text-break"><strong>{{ statusAction.row.code }}</strong> · {{ statusAction.row.name }}</p>
    <ErrorNotice :error="statusError" />
    <p class="mb-0">确认撤销此条{{ title }}？撤销后恢复为{{ config.pending }}，并清除本次{{ config.label }}人和{{ config.label }}日期。</p>
    <template #footer><button type="button" class="btn btn-light" :disabled="actionBusy" @click="statusAction = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="actionBusy" @click="undoCheck">{{ actionBusy ? '正在保存…' : '确认' }}</button></template>
  </BootstrapModal>
  <TaskProcessingModal v-if="processingTarget" :row="processingTarget" @close="processingTarget = undefined" />
  <RegistrationActionModal kind="samples" :record="voidRecord" initial-action="void" :report-stage="stage" @close="voidRecord = undefined" @saved="load" />
  <ReportQuickReviewModal v-if="quickIds" :ids="quickIds" :stage="stage" @close="closeQuickReview" />
  <TestPlanFilterDrawer ref="planFilter" :sample-scope="`report-${stage}`" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <RegistrationAttachmentManager v-if="attachmentId" :id="attachmentId" kind="samples" @close="attachmentId = undefined" readonly title="查看附件" />
</template>
