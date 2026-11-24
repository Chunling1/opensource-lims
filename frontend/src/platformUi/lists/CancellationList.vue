<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import DataTable from "../TemplateDataTable"
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import CancellationApprovalModal from '../../components/commissions/CancellationApprovalModal.vue'
import type { RegistrationPage, RegistrationSample } from '../../types/commissions/registration'
import {toRefs} from 'vue'
const props=defineProps<{context:Record<string,any> & {rows:{items:Record<string,any>[];total:number;page:number;pageSize:number};columns:import('../../types/common/table').TableColumn<string>[]}}>()
const {mode,registrationDemo,parseTableColumns,clientYearRange,normalizeError,downloadBlob,currentActor,cancellationRoot,cancellationColumns,cancellationStates,cancellationDate,canApproveCancellation,route,router,dates,text,query,draft,rows,selected,loading,error,columnKeys,columns,approving,actionLoading,actionError,exporting,request,actionRequest,exportRequest,controller,load,patch,search,sort,toggleColumn,openApproval,exportRows}=toRefs(props.context)
</script>
<template>
  <PageHeading title="作废审批" />
  <section class="card" aria-label="作废审批列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">作废审批</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar label="作废审批" :columns="cancellationColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows" />
    </div>
    <form class="card-body border-bottom" aria-label="作废审批查询" @submit.prevent="search">
      <QueryFormLayout>
      <div class="query-fields">
          <div class="query-field query-field--group"><label for="cancellationlist-group" class="form-label">数据分组</label><select id="cancellationlist-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in context.reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
        <div class="query-field query-field--date"><label class="form-label" for="cancellation-dates">作废日期</label><TemplateDateRange id="cancellation-dates" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
        <div class="query-field query-field--status"><label class="form-label" for="cancellation-result">数据状态</label><select id="cancellation-result" v-model="draft.result" class="form-select"><option value="">全部</option><option v-for="result in cancellationStates" :key="result">{{ result }}</option></select></div>
      </div>
      <template #actions><button class="btn btn-primary text-nowrap" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
      </QueryFormLayout>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable label="作废审批" :rows="rows.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected"
      :sort-key="query.sort" :direction="query.direction" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading :actions-disabled="actionLoading"
      @sort="sort" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })" @retry="load">
      <template #cell-approvalResult="{ row }"><span class="badge" :class="row.approvalResult === '申请中' ? 'bg-warning-subtle text-warning' : row.approvalResult === '申请通过' ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'">{{ row.approvalResult }}</span></template>
      <template #cell-appliedAt="{ row }"><span :title="row.appliedAt">{{ cancellationDate(row.appliedAt) }}</span></template>
      <template #cell-approvedAt="{ row }"><span :title="row.approvedAt">{{ cancellationDate(row.approvedAt) }}</span></template>
      <template #actions="{ row }"><button class="dropdown-item" type="button" role="menuitem" :disabled="!context.canVoid(row)" @click="context.voidRow(row)"><i class="ti ti-trash align-bottom me-2 text-muted" aria-hidden="true"></i>作废样品</button>
        <button class="dropdown-item" type="button" role="menuitem" :disabled="true" @click="openApproval(row)"><i :class="row.approvalResult === '申请中' ? 'ti ti-circle-check' : 'ti ti-eye'" class="align-bottom me-2 text-muted" aria-hidden="true"></i>{{ row.approvalResult === '申请中' ? '审批' : '查看审批结果' }}</button>
      </template>
    </DataTable>
  </section>
  <CancellationApprovalModal :record="approving" @close="approving = undefined" @saved="load" />
</template>
