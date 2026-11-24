<script setup lang="ts">
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from "../TemplateDataTable"
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {testingMode,mode,completionFieldMessages,emptyPlanSelection,canChangeData,registrationDemo,changesRoot,workspaceCanEdit,parseTableColumns,clientYearRange,normalizeError,downloadBlob,currentActor,sampleTypes,commissionChangeColumns,changeProblemSources,changeProcessingResults,title,root,allowed,route,router,dates,drawer,plans,planState,planBusy,planError,planFilter,dateInput,applyPlans,text,query,draft,rows,selected,loading,error,attachmentId,syncAttachmentVersion,columnKeys,columns,completing,actionLoading,actionError,exporting,completingBusy,completeError,missingOriginalWarning,completeValidation,completeFieldMessages,submitCompletion,request,actionRequest,exportRequest,controller,load,patch,search,sort,toggleColumn,edit,complete,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="commissionChangeColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button v-if="testingMode" class="btn btn-light text-body text-nowrap" type="button" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}</button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search">
      <QueryFormLayout>
      <div class="query-fields">
          <div class="query-field query-field--group"><label for="changelist-group" class="form-label">数据分组</label><select id="changelist-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
        <div class="query-field query-field--date"><label class="form-label" for="change-dates">问题提交日期</label><TemplateDateRange ref="dateInput" id="change-dates" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
        <div class="query-field query-field--status"><label class="form-label" for="change-source">问题来源</label><select id="change-source" v-model="draft.source" class="form-select"><option value="">全部</option><option v-for="source in changeProblemSources" :key="source">{{ source }}</option></select></div>
        <div class="query-field query-field--status"><label class="form-label" for="change-result">处理结果</label><select id="change-result" v-model="draft.result" class="form-select"><option v-for="result in changeProcessingResults" :key="result">{{ result }}</option></select></div>
        <div class="query-field query-field--type"><label class="form-label" for="change-type">样品类型</label><select id="change-type" v-model="draft.sampleType" class="form-select"><option value="">全部</option><option v-for="type in sampleTypes" :key="type">{{ type }}</option></select></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout>
      <div v-if="testingMode && planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" class="btn btn-link btn-sm" type="button" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected"
      :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading :actions-disabled="actionLoading"
      @sort="sort" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-dataStatus="{ row }"><span class="badge bg-info-subtle text-info">{{ row.dataStatus }}</span></template>
      <template #cell-processingResult="{ row }"><span class="badge bg-warning-subtle text-warning">{{ row.processingResult || '—' }}</span></template>
      <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
      <template #actions="{ row }">
        <button class="dropdown-item" type="button" role="menuitem" :disabled="!allowed(row)" @click="edit(row)"><i class="ti ti-edit align-bottom me-2 text-muted" aria-hidden="true"></i>更改</button>
        <button class="dropdown-item" type="button" role="menuitem" :disabled="!allowed(row)" @click="complete(row)"><i class="ti ti-circle-check align-bottom me-2 text-muted" aria-hidden="true"></i>完成</button>
        <button class="dropdown-item" type="button" role="menuitem" @click="attachmentId = row.id"><i class="ti ti-paperclip align-bottom me-2 text-muted" aria-hidden="true"></i>附件管理</button>
      </template>
    </DataTable>
  </section>
  <RegistrationActionModal v-if="!testingMode" kind="samples" workspace="changes" :record="completing" initial-action="complete-change" @close="completing = undefined" @saved="load" />
  <RegistrationAttachmentManager :id="undefined" kind="samples" @close="attachmentId = undefined" @changed="syncAttachmentVersion" />
  <BootstrapModal v-if="testingMode && completing" open title="完成" :busy="completingBusy" @close="!completingBusy && (completing = undefined)">
    <p class="text-break"><strong>{{ completing.code }}</strong> · {{ completing.name }}</p>
    <p>确认对这条样品执行“完成更改”？</p>
    <FeedbackNotice v-if="completeValidation" :message="completeValidation.message" :trigger="completeValidation">
      <div class="text-break">{{ completeValidation.message }}</div>
      <ul v-if="completeFieldMessages.length" class="mt-2 mb-0 ps-3"><li v-for="message in completeFieldMessages" :key="message" class="text-break">{{ message }}</li></ul>
    </FeedbackNotice>
    <ErrorNotice v-else :error="completeError" @reload="completing = undefined; load()" />
    <button v-if="completeValidation" type="button" class="btn btn-link p-0" :disabled="completingBusy" @click="edit(completing)">打开检测数据更改，检查并补充资料</button>
    <template #footer><button type="button" class="btn btn-light" :disabled="completingBusy" @click="completing = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="completingBusy || !allowed(completing)" @click="submitCompletion">{{ completingBusy ? '正在保存…' : missingOriginalWarning ? '继续完成' : '确认' }}</button></template>
  </BootstrapModal>
  <TestPlanFilterDrawer v-if="testingMode" ref="planFilter" sample-scope="data-changes" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
</template>
