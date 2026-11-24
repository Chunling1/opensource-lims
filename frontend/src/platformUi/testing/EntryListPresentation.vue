<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TaskReturnModal from '../../components/testing/TaskReturnModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import { toRefs } from "vue"
const props=defineProps<{context: Record<string, any> & { rows: import("../../types/testing/dataEntry").DataEntryPage; columns: import("../../types/common/table").TableColumn<any>[] }}>()
const {title,root,route,router,dates,text,ids,plans,planState,drawer,planFilter,planBusy,planError,applyPlans,query,draft,more,activeFilters,dateInput,emptyPage,rows,selected,loading,error,exporting,exportError,returnTarget,returnBusy,returnError,attachmentId,voidRecord,voidLoading,voidError,voidSequence,resetVoid,openVoid,syncAttachment,statusAction,actionBusy,statusError,statusValidation,missingOriginalWarning,repairTarget,statusFieldMessages,actionAllowed,openEntry,runStatusAction,rowAction,actionSequence,resetReturn,openReturn,submitReturn,columnKeys,columns,sequence,exportSequence,controller,load,patch,search,toggleColumn,exportRows,reportOnly,checkMode,reportCheckMode,queryMode,reportQueryMode,changeMode,dataEntryColumns,dataEntrySearchFields,dataEntryStates,sampleTypes,assignmentConclusions,dataEntryDateFields,dataEntryActions}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="dataEntryColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="query-fields">
          <div class="query-field query-field--group"><label for="entrylistpresentation-group" class="form-label">数据分组</label><select id="entrylistpresentation-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
          <div class="query-field query-field--search"><label for="data-entry-field" class="form-label">查询内容</label><select id="data-entry-field" v-model="draft.searchField" class="form-select"><option v-for="field in dataEntrySearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
          <div class="query-field query-field--keyword"><label for="data-entry-contains" class="form-label">包含</label><input id="data-entry-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
          <div class="query-field query-field--status"><label for="data-entry-status" class="form-label">数据状态</label><select id="data-entry-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in dataEntryStates" :key="status">{{ status }}</option></select></div>
          <div class="query-field query-field--type"><label for="data-entry-type" class="form-label">报告类别</label><select id="data-entry-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" id="data-entry-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4 col-xl-3"><label for="data-entry-conclusion" class="form-label">结论状态</label><select id="data-entry-conclusion" v-model="draft.conclusion" class="form-select" disabled title="当前列表接口未提供结论状态筛选"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8 col-xl-9">
            <label for="data-entry-dates" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in dataEntryDateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange id="data-entry-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="data-entry-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <div v-if="voidError" class="px-3 pt-3"><ErrorNotice :error="voidError" /></div>
    <div v-if="voidLoading" class="px-3 py-2 text-muted" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载样品…</div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button v-for="action in dataEntryActions" :key="action.label" type="button" role="menuitem" class="dropdown-item" :title="action.label === '作废' ? '请在委托管理的作废审批中办理' : undefined" :disabled="loading || returnBusy || actionBusy || voidLoading || !actionAllowed(row, action.label)" @click="rowAction(row, action.label)">
          <i :class="action.icon" class="me-2 text-muted" aria-hidden="true"></i>{{ action.label }}
        </button>
      </template>
    </DataTable>
  </section>
  <BootstrapModal v-if="statusAction" open :title="statusAction.action === 'complete' ? '录入完成' : '撤销完成'" :busy="actionBusy" scrollable @close="!actionBusy && (statusAction = undefined)">
    <p class="text-break"><strong>{{ statusAction.row.code }}</strong> · {{ statusAction.row.name }}</p>
    <FeedbackNotice v-if="statusValidation" :message="statusValidation.message" :trigger="statusValidation">
      <div class="text-break">{{ statusValidation.message }}</div>
      <ul v-if="statusFieldMessages.length" class="mt-2 mb-0 ps-3"><li v-for="message in statusFieldMessages" :key="message" class="text-break">{{ message }}</li></ul>
    </FeedbackNotice>
    <ErrorNotice v-else :error="statusError" />
    <p v-if="!statusValidation">{{ statusAction.action === 'complete' ? '请确认试验信息及最终报告内容无误。完成录入后将进入后续流程，是否继续？' : '确认对这条样品执行“撤销完成”？' }}</p>
    <button v-if="statusValidation && statusAction.action === 'complete'" type="button" class="btn btn-link p-0" :disabled="actionBusy" @click="openEntry(statusAction.row, repairTarget.action)">{{ repairTarget.label }}</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="actionBusy" @click="statusAction = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="actionBusy" @click="runStatusAction">{{ actionBusy ? '正在保存…' : missingOriginalWarning ? '继续完成' : '确认' }}</button></template>
  </BootstrapModal>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="data-entry" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <RegistrationAttachmentManager v-if="attachmentId" :id="attachmentId" kind="samples" @close="attachmentId = undefined" @changed="syncAttachment" />
  <RegistrationActionModal kind="samples" :record="voidRecord" initial-action="void" @close="resetVoid()" @saved="load()" />
  <TaskReturnModal :row="returnTarget" :busy="returnBusy" :error="returnError" @close="!returnBusy && resetReturn()" @submit="submitReturn" @refresh="load()" />
</template>
