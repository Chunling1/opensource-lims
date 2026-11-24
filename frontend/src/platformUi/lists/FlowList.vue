<script setup lang="ts">
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from "../TemplateDataTable"
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TestPlanFilterDrawer from '../../components/samples/TestPlanFilterDrawer.vue'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {mode,flowColumns,flowStates,flowDateFields,flowDateEnabled,emptyPlanSelection,registrationDemo,clientYearRange,normalizeError,parseTableColumns,downloadBlob,currentActor,title,root,route,router,dates,text,ids,routeDates,dateDraft,dateInputs,query,draft,plans,planState,more,activeFilters,drawer,planFilter,planBusy,planError,emptyPage,rows,selected,loading,error,exporting,exportError,columnKeys,columns,sequence,exportSequence,controller,load,patch,search,applyPlans,toggleColumn,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="flowColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows">
        <button type="button" class="btn btn-light text-body text-nowrap" :disabled="loading" :aria-expanded="drawer" :aria-busy="planBusy" aria-haspopup="dialog" aria-label="检测方案" @click="drawer = true"><i class="ti ti-filter me-1" aria-hidden="true"></i>{{ planState?.count ? `已选 ${planState.count} 项` : '检测方案' }}<span v-if="planBusy" class="spinner-border spinner-border-sm ms-1" aria-label="正在更新方案选择"></span></button>
      </TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}条件`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="query-fields">
          <div class="query-field query-field--group"><label for="flowlist-group" class="form-label">数据分组</label><select id="flowlist-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
          <div class="query-field query-field--keyword"><label for="flow-code" class="form-label">样品编号</label><input id="flow-code" v-model="draft.code" class="form-control" maxlength="200" /></div>
          <div class="query-field query-field--status"><label for="flow-status" class="form-label">流转状态</label><select id="flow-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="status in flowStates" :key="status">{{ status }}</option></select></div>
        </div>
      <div v-show="more" id="flow-more-filters" class="row g-3 align-items-start mt-0">
          <div v-for="field in flowDateFields" :key="field.key" class="col-12 col-md-6 col-xxl-3"><label :for="`flow-${field.key}-dates`" class="form-label">{{ field.label }}</label><TemplateDateRange :id="`flow-${field.key}-dates`" ref="dateInputs" :from="dateDraft[field.key].from" :to="dateDraft[field.key].to" :disabled="!flowDateEnabled(field.key, draft.status)" @change="dateDraft[field.key] = $event" /></div>
      </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading || planBusy"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="flow-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
      <div v-if="planState?.count" class="d-flex flex-wrap align-items-center gap-2 mt-3" aria-label="已选检测方案"><span class="text-muted">检测方案：</span><button v-for="plan in planState.previews.slice(0, 2)" :key="plan.id" type="button" class="btn btn-primary-lt btn-sm text-break" @click="drawer = true">{{ plan.name }}</button><button v-if="planState.count > 2" type="button" class="btn btn-link btn-sm p-0" @click="drawer = true">另 {{ planState.count - 2 }} 项</button></div>
      <div v-if="planError && !drawer" class="mt-3"><ErrorNotice :error="planError" retry :busy="planBusy" @retry="planFilter?.retry()" /></div>
    </form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @sort="patch({ sort: $event, direction: query.sort === $event && query.direction === 'asc' ? 'desc' : 'asc', page: '1' })" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-retentionTime="{ row }">{{ row.retentionTime ? new Date(row.retentionTime).toLocaleString('zh-CN', { hour12: false }) : '—' }}</template>
    </DataTable>
  </section>
  <TestPlanFilterDrawer ref="planFilter" sample-scope="flow" :open="drawer" :value="plans" @close="drawer = false" @change="applyPlans" @busy="planBusy = $event" @error="planError = $event" />
</template>
