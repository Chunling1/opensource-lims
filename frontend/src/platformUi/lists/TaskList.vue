<script setup lang="ts">
import SampleDisposalActionModal from "./DisposalActionModal.vue"
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TaskReturnModal from '../../components/testing/TaskReturnModal.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from "../TemplateDataTable"
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import type { OutboundReturn } from '../../types/samples/outbound'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {mode,normalizeConclusion,emptyPlanSelection,assignmentConclusions,assignmentSearchFields,assignmentDateFields,taskQueryColumns,taskQueryStates,sampleTypes,registrationDemo,clientYearRange,normalizeError,parseTableColumns,downloadBlob,currentActor,title,root,route,router,dates,text,ids,plans,planState,drawer,planFilter,planBusy,planError,applyPlans,query,draft,more,activeFilters,dateInput,emptyPage,rows,selected,loading,error,exporting,exportError,returnTarget,returnBusy,returnError,actionSequence,resetReturn,printTask,openReturn,submitReturn,columnKeys,columns,sequence,exportSequence,controller,load,patch,search,toggleColumn,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="taskQueryColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="query-fields">
          <div class="query-field query-field--group"><label for="tasklist-group" class="form-label">数据分组</label><select id="tasklist-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
          <div class="query-field query-field--search"><label for="task-query-field" class="form-label">查询内容</label><select id="task-query-field" v-model="draft.searchField" class="form-select"><option v-for="field in assignmentSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
          <div class="query-field query-field--keyword"><label for="task-query-contains" class="form-label">包含</label><input id="task-query-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
          <div class="query-field query-field--status"><label for="task-query-status" class="form-label">数据状态</label><select id="task-query-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in taskQueryStates" :key="status">{{ status }}</option></select></div>
          <div class="query-field query-field--type"><label for="task-query-type" class="form-label">样品类型</label><select id="task-query-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
        </div>
      <div v-show="more" id="task-query-more-filters" class="row g-3 align-items-start mt-0">
          <div class="col-12 col-md-4 col-xl-3"><label for="task-query-conclusion" class="form-label">结论状态</label><select id="task-query-conclusion" v-model="draft.conclusion" class="form-select"><option value="">全部</option><option v-for="conclusion in assignmentConclusions" :key="conclusion">{{ conclusion }}</option></select></div>
          <div class="col-12 col-md-8 col-xl-9">
            <label for="task-query-dates" class="form-label">日期</label>
            <div class="row g-2"><div class="col-12 col-sm-4"><select v-model="draft.dateField" class="form-select" aria-label="日期字段"><option v-for="field in assignmentDateFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div><div class="col-12 col-sm-8"><TemplateDateRange id="task-query-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div></div>
          </div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="task-query-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load()">
      <template #actions="{ row }"><button type="button" role="menuitem" class="dropdown-item" @click="context.taskView(row)"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button><button type="button" role="menuitem" class="dropdown-item" @click="context.taskEnter(row)"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>进入检测录入</button><button type="button" role="menuitem" class="dropdown-item" :disabled="!context.canRestock(row)" @click="context.taskRestock(row)"><i class="ti ti-arrow-back me-2 text-muted" aria-hidden="true"></i>撤销领取</button><button type="button" role="menuitem" class="dropdown-item" :disabled="!context.canDispose(row, 'dispose')" @click="context.taskDispose(row)"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>样品处置</button><button type="button" role="menuitem" class="dropdown-item" :disabled="loading || returnBusy || !row.canReturn" @click="openReturn(row)"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>退回委托</button><button type="button" role="menuitem" class="dropdown-item" :disabled="loading || returnBusy || !row.canPrintTask" @click="printTask(row)"><i class="ti ti-printer me-2 text-muted" aria-hidden="true"></i>打印任务单</button></template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="task-query" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
  <SampleDisposalActionModal :operation="context.disposalOperation" :busy="context.operationBusy" :error="context.operationError" @close="context.disposalOperation=undefined" @submit="context.submitDisposal" />
  <TaskReturnModal :row="returnTarget" :busy="returnBusy" :error="returnError" @close="!returnBusy && resetReturn()" @submit="submitReturn" @refresh="load()" />
</template>
