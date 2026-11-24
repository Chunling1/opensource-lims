<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import RegistrationFilters from '../../components/commissions/RegistrationFilters.vue'
import CommissionAdvancedQueryModal from '../../components/commissions/CommissionAdvancedQueryModal.vue'
import SampleAdvancedQueryModal from '../../components/commissions/SampleAdvancedQueryModal.vue'
import DataTable from '../../platformUi/TemplateDataTable'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import RegistrationReviewModal from '../../components/commissions/RegistrationReviewModal.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import {toRefs,defineComponent,h} from 'vue'
import type {CommissionColumnKey,SampleColumnKey} from '../../services/commissions/registrationColumns'
type WorkspaceSampleColumnKey=SampleColumnKey
const props=defineProps<{model:Record<string,any> & {commissions:{items:Record<string,any>[];total:number;page:number;pageSize:number};samples:{items:Record<string,any>[];total:number;page:number;pageSize:number};visibleColumns:import("../../types/common/table").TableColumn<string>[];visibleSampleColumns:import("../../types/common/table").TableColumn<string>[]}}>()
const RouterLink=defineComponent({props:['to'],setup(p,{slots,attrs}){return()=>h('a',{...attrs,href:'#',onClick:(e:MouseEvent)=>{e.preventDefault();if(attrs['aria-disabled']!=='true')props.model.navigate(p.to)}},slots.default?.())}})
const {commissionAdvancedFields,sampleWorkflowDateFields,sampleConclusions,workflowDateDraft,sampleAdvancedFields,registrationDemo,clearRegistrationListState,isRegistrationChild,restoreRegistrationListState,saveRegistrationListState,commissionColumns,parseCommissionColumns,sampleColumns,inquirySampleColumns,parseTableColumns,sampleReadOnlyReason,registrationContext,registrationCanWrite,registrationCanLink,registrationCanAddSample,registrationCanReadSamples,workspaceActions,workspaceCanEdit,TableColumn,clientYearRange,currentActor,normalizeError,downloadBlob,RegistrationQuery,RegistrationKind,RegistrationCommission,RegistrationSample,RegistrationSampleRow,RegistrationCommissionRow,inquirySampleDataStatusOptions,commissionSearchFields,sampleSearchFields,inquirySampleSearchFields,advancedSearchKind,advancedBusy,advancedError,advancedRequest,advancedController,advancedCommitPath,advancedActor,prefetchedCommissions,prefetchedSamples,closeAdvanced,context,registrationDataStatusOptions,reviewDataStatusOptions,registrationRoot,route,router,attachmentId,attachmentKind,openAttachments,defaultDates,value,query,basicCommissionQuery,usingAdvancedCommission,advancedCommissionDraft,commissionAdvancedConditions,commissionQuery,searchAdvancedCommission,selectedCommissions,currentId,scope,sampleCommissionId,sampleReady,currentCaption,basicSampleQuery,usingAdvancedSample,advancedSampleDraft,sampleAdvancedConditions,sampleQuery,searchAdvancedSample,submitAdvanced,collapsed,columnKeys,visibleColumns,toggleColumn,resetColumns,availableSampleColumns,sampleColumnKeys,visibleSampleColumns,toggleSampleColumn,resetSampleColumns,commissions,samples,current,currentError,cError,sError,operationError,cLoading,sLoading,exporting,selectedSamples,notice,actionKind,actionRecord,actionSelection,cRequest,sRequest,currentRequest,actionRequest,cController,sController,currentController,actionLoading,restored,quickReviewRecord,quickReviewLoading,quickReviewRecords,quickReviewRequest,canQuickReview,openQuickReview,closeQuickReview,canReadSamples,canAddSample,bulkSelectionError,openBulk,sampleToolbarActions,patch,search,sort,selectCommissions,showSamples,selectCommissionRow,changeScope,link,addSampleLink,openActions,loadCurrent,loadCommissions,loadSamples,syncAttachmentVersion,refresh,exportData,inquiry,review}=toRefs(props.model)
</script>
<template>
  <PageHeading :title="context.title" />
  <ErrorNotice :error="operationError" />
  <section v-if="!model.samplesOnly" class="card" aria-label="委托列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">委托</h5><span class="badge bg-primary-subtle text-body">{{ commissions.total }}</span><button class="btn btn-sm btn-light" :aria-expanded="!collapsed" aria-controls="commission-body" @click="patch({ collapsed: collapsed ? undefined : '1' })">{{ collapsed ? '展开委托' : '收起委托' }}</button></div>
      <TableToolbar label="委托" :columns="commissionColumns" :selected="columnKeys" :count="selectedCommissions.length" :export-disabled="exporting || cLoading || !!cError" @column="(key, checked) => toggleColumn(key as CommissionColumnKey, checked)" @reset="resetColumns" @export="exportData('commissions', $event)">
        <RouterLink v-if="!inquiry && !review && registrationCanWrite(currentActor, 'commissions')" class="btn btn-primary text-nowrap px-2" :to="link('commissions', 'new')"><i class="ti ti-plus me-1 d-none d-sm-inline-block" aria-hidden="true"></i>新增委托</RouterLink>
      </TableToolbar>
    </div>
    <div v-if="collapsed && currentCaption" class="card-body"><p class="mb-0 text-break">{{ currentCaption }}</p></div>
    <div id="commission-body" class="collapse" :class="{ show: !collapsed }">
      <RegistrationFilters kind="commissions" :show-advanced-search="inquiry" @advanced-search="advancedSearchKind = 'commissions'" :query="basicCommissionQuery" :advanced-active="usingAdvancedCommission" @search="search('c', $event)" />
      <DataTable label="委托" :rows="commissions.items" :columns="visibleColumns" :row-key="row => row.id" :row-label="row => row.code"
        :selected="selectedCommissions" highlight-selected :sort-key="commissionQuery.sort" :direction="commissionQuery.direction"
        :pagination="{ ...commissions, sizes: [5, 10, 20] }" :loading="cLoading" :error="cError" preserve-rows-on-loading :actions-disabled="actionLoading"
        @update:selected="selectCommissions" @row-click="row => selectCommissionRow(row.id)" @sort="sort('c', $event)" @retry="loadCommissions"
        @page="patch({ cPage: String($event) })" @size="patch({ cSize: String($event), cPage: '1' })">
        <template #cell-code="{ row }"><RouterLink class="fw-medium" :to="link('commissions', row.id)">{{ row.code }}</RouterLink></template>
        <template #cell-status="{ text }"><span class="badge bg-primary-subtle text-body">{{ text }}</span></template>
        <template #actions="{ row }">
            <RouterLink class="dropdown-item" role="menuitem" :to="link('commissions', row.id)"><i class="ti ti-eye align-bottom me-2 text-muted" aria-hidden="true"></i>查看</RouterLink>
            <template v-if="!review">
            <button v-if="!row.sampleCount" class="dropdown-item" role="menuitem" disabled title="该委托下暂无样品，无法打印"><i class="ti ti-printer align-bottom me-2 text-muted" aria-hidden="true"></i>打印</button>
            <RouterLink v-else class="dropdown-item" role="menuitem" :to="{ path: `${registrationRoot}/commissions/${row.id}/print`, query: { returnTo: route.fullPath } }"><i class="ti ti-printer align-bottom me-2 text-muted" aria-hidden="true"></i>打印</RouterLink>
            </template>
            <RouterLink v-if="workspaceCanEdit(currentActor, 'commissions', row, context.workspace)" class="dropdown-item" role="menuitem" :to="link('commissions', row.id, true)"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>{{ review ? '编辑' : '修改' }}</RouterLink>
            <button v-if="!inquiry && !workspaceCanEdit(currentActor, 'commissions', row, context.workspace)" class="dropdown-item" role="menuitem" disabled :title="!registrationCanWrite(currentActor, 'commissions') ? '当前身份无权操作' : '请先取消完成再编辑'"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>{{ review ? '编辑' : '修改' }}</button>
            <RouterLink v-if="!inquiry && !review && registrationCanAddSample(currentActor, row.status)" class="dropdown-item" role="menuitem" :to="addSampleLink(row.id)"><i class="ti ti-circle-plus align-bottom me-2 text-muted" aria-hidden="true"></i>新增样品</RouterLink>
            <button v-if="!inquiry && !review && !registrationCanAddSample(currentActor, row.status)" class="dropdown-item" role="menuitem" disabled :title="!registrationCanLink(currentActor) ? '当前身份无权新增样品' : '请先取消完成再新增样品'"><i class="ti ti-circle-plus align-bottom me-2 text-muted" aria-hidden="true"></i>新增样品</button>
            <template v-if="workspaceActions(currentActor, 'commissions', row, context.workspace).length"><div class="dropdown-divider" role="separator"></div><button v-for="item in workspaceActions(currentActor, 'commissions', row, context.workspace)" :key="item.id" class="dropdown-item" :class="{ 'text-danger': item.id === 'cancel' }" role="menuitem" :disabled="item.disabled" :title="item.disabledReason" @click="openActions('commissions', row, item.id)"><i class="align-bottom me-2 text-muted" :class="item.id === 'complete' ? 'ti ti-circle-check' : 'ti ti-arrow-back-up'" aria-hidden="true"></i>{{ item.label }}</button></template>
            <button class="dropdown-item" role="menuitem" disabled @click="openAttachments('commissions', row.id)"><i class="ti ti-paperclip align-bottom me-2 text-muted" aria-hidden="true"></i>附件管理</button>
                  </template>
        <template #empty><p class="mt-2 mb-0">暂无符合条件的委托</p><button class="btn btn-link" @click="search('c', {})">清空筛选条件</button></template>
      </DataTable>
    </div>
  </section>
  <section class="card" aria-label="样品列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">样品</h5><span v-if="canReadSamples && sampleReady && !sLoading && !sError" class="badge bg-primary-subtle text-body">{{ samples.total }}</span><span v-if="canReadSamples" class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !sLoading }" :aria-hidden="!sLoading" role="status" aria-label="正在加载样品"></span></div>
      <TableToolbar v-if="canReadSamples" label="样品" :adaptive-actions="sampleToolbarActions" @action="openBulk" :columns="availableSampleColumns" :selected="sampleColumnKeys" :count="selectedSamples.length" :export-disabled="exporting || sLoading || !!sError || !sampleReady || scope === 'current' && selectedCommissions.length === 1 && !current" @column="(key, checked) => toggleSampleColumn(key as WorkspaceSampleColumnKey, checked)" @reset="resetSampleColumns" @export="exportData('samples', $event)">
        <slot name="sample-finance" />
        <button v-if="review && registrationCanWrite(currentActor, 'samples')" class="btn btn-primary text-nowrap px-2" :disabled="!canQuickReview" :aria-busy="quickReviewLoading" :title="!selectedSamples.length ? '请勾选样品（最多 50 个）' : '快速评审所选样品'" @click="openQuickReview"><span v-if="quickReviewLoading" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span><i v-else class="ti ti-clipboard-list align-bottom me-1" aria-hidden="true"></i>快速评审</button>
        <button v-if="!inquiry && !review" type="button" class="btn btn-primary text-nowrap px-2" :disabled="!canAddSample" @click="canAddSample && router.push(link('samples', 'new'))"><i class="ti ti-plus me-1 d-none d-sm-inline-block" aria-hidden="true"></i>新增样品</button>
      </TableToolbar>
    </div>
    <div v-if="!canReadSamples" class="card-body text-muted">当前身份没有查看样品的权限。</div>
    <template v-else>
      <div v-if="!model.samplesOnly" class="d-flex flex-wrap align-items-center gap-3 px-3 border-bottom">
        <div class="nav nav-tabs nav-tabs-custom border-bottom-0" role="tablist" aria-label="样品范围">
          <button id="samples-current-tab" class="nav-link" :class="{ active: scope === 'current' }" role="tab" :aria-selected="scope === 'current'" aria-controls="samples-panel" @click="changeScope('current')">当前委托</button>
          <button id="samples-all-tab" class="nav-link" :class="{ active: scope === 'all' }" role="tab" :aria-selected="scope === 'all'" aria-controls="samples-panel" @click="changeScope('all')">全部样品</button>
        </div>
        <span v-if="scope === 'current' && currentCaption" class="text-muted small text-break py-2">{{ currentCaption }}</span>
      </div>
      <div id="samples-panel" role="tabpanel" :aria-labelledby="scope === 'all' ? 'samples-all-tab' : 'samples-current-tab'">
        <div v-if="!sampleReady" class="text-center py-5"><i class="ti ti-file-description display-5 text-muted" aria-hidden="true"></i><h5 class="mt-3">请选择委托</h5><p class="text-muted">勾选上方委托，查看关联样品。</p></div>
        <template v-else>
          <div v-if="scope === 'current' && currentError" class="px-3 pt-3"><ErrorNotice :error="currentError" retry @retry="loadCurrent" /></div>
        <RegistrationFilters :report-group-options="model.reportGroupOptions" kind="samples" :sample-search-fields="inquiry ? inquirySampleSearchFields : sampleSearchFields" :show-advanced-search="inquiry" @advanced-search="advancedSearchKind = 'samples'" :data-status-options="inquiry ? inquirySampleDataStatusOptions : review ? reviewDataStatusOptions : registrationDataStatusOptions" :query="basicSampleQuery" :advanced-active="usingAdvancedSample" @search="search('s', $event)" />
          <div v-if="notice" class="alert alert-info m-3" role="status">{{ notice }}</div>
          <DataTable label="样品" :rows="samples.items" :columns="visibleSampleColumns" :row-key="row => row.id" :row-label="row => row.code"
            v-model:selected="selectedSamples" :selectable="row => !sampleReadOnlyReason(row.status)" :selection-disabled-reason="row => sampleReadOnlyReason(row.status)"
            :sort-key="sampleQuery.sort" :direction="sampleQuery.direction" :pagination="{ ...samples, sizes: [10, 20, 50] }"
            :loading="sLoading" :error="sError" preserve-rows-on-loading :actions-disabled="actionLoading"
            @sort="sort('s', $event)" @retry="loadSamples" @page="patch({ sPage: String($event) })" @size="patch({ sSize: String($event), sPage: '1' })">
            <template #cell-code="{ row }"><RouterLink class="fw-medium" :to="link('samples', row.id)">{{ row.code }}</RouterLink></template>
            <template #cell-commissionCode="{ row }"><button v-if="row.commissionCode" class="btn btn-link p-0 text-nowrap" @click="showSamples(row.commissionId)">{{ row.commissionCode }}</button><span v-else>—</span></template>
            <template #cell-dataStatus="{ text }"><span class="badge bg-primary-subtle text-body">{{ text }}</span></template>
            <template #cell-attachmentCount="{ row }">{{ row.attachmentCount > 0 ? '有' : '' }}</template>
            <template #actions="{ row }">
                <RouterLink class="dropdown-item" role="menuitem" :to="link('samples', row.id)"><i class="ti ti-eye align-bottom me-2 text-muted" aria-hidden="true"></i>查看</RouterLink>
                <template v-if="!sampleReadOnlyReason(row.status)">
                <RouterLink v-if="workspaceCanEdit(currentActor, 'samples', row, context.workspace)" class="dropdown-item" role="menuitem" :to="link('samples', row.id, true)"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>编辑</RouterLink>
                <button v-else-if="!inquiry && registrationCanWrite(currentActor, 'samples')" class="dropdown-item" role="menuitem" disabled :title="review ? '请先撤销评审再编辑' : row.status === 'completed' ? '请先取消完成再编辑' : '已作废样品不可编辑'"><i class="ti ti-pencil align-bottom me-2 text-muted" aria-hidden="true"></i>编辑</button>
                <RouterLink class="dropdown-item" role="menuitem" :to="{ path: `${registrationRoot}/samples/${row.id}/print`, query: { returnTo: route.fullPath } }"><i class="ti ti-printer align-bottom me-2 text-muted" aria-hidden="true"></i>打印</RouterLink>
                <template v-if="workspaceActions(currentActor, 'samples', row, context.workspace).length"><div class="dropdown-divider" role="separator"></div><template v-for="item in workspaceActions(currentActor, 'samples', row, context.workspace)" :key="item.id"><RouterLink v-if="review && item.id === 'review' && !item.disabled" class="dropdown-item" role="menuitem" :to="{ path: `${registrationRoot}/samples/${row.id}/assess`, query: { returnTo: route.fullPath } }"><i class="ti ti-clipboard-list align-bottom me-2 text-muted" aria-hidden="true"></i>{{ item.label }}</RouterLink><button v-else class="dropdown-item" :class="{ 'text-danger': item.id === 'void' }" role="menuitem" :disabled="item.disabled" :title="item.disabledReason" @click="openActions('samples', row, item.id)"><i class="align-bottom me-2" :class="item.id === 'void' ? 'ti ti-ban' : ['complete', 'review'].includes(item.id) ? 'ti ti-circle-check text-muted' : 'ti ti-arrow-back-up text-muted'" aria-hidden="true"></i>{{ item.label }}</button></template>
                </template>
                </template>
                <button class="dropdown-item" role="menuitem" @click="openAttachments('samples', row.id)"><i class="ti ti-paperclip align-bottom me-2 text-muted" aria-hidden="true"></i>附件管理</button>
            </template>
            <template #empty><p class="mt-2 mb-0">暂无符合条件的样品</p><button class="btn btn-link" @click="search('s', {})">清空样品筛选</button></template>
          </DataTable>
        </template>
      </div>
    </template>
  </section>

  <CommissionAdvancedQueryModal v-if="inquiry && advancedSearchKind === 'commissions'" :initial="advancedCommissionDraft" :busy="advancedBusy" :error="advancedError" @close="closeAdvanced" @search="searchAdvancedCommission" />
  <SampleAdvancedQueryModal v-if="inquiry && advancedSearchKind === 'samples'" :initial="advancedSampleDraft" :busy="advancedBusy" :error="advancedError" @close="closeAdvanced" @search="searchAdvancedSample" />

  <RegistrationAttachmentManager :id="attachmentId" :kind="attachmentKind" @close="attachmentId = undefined" @changed="syncAttachmentVersion" />
  <RegistrationReviewModal :record="quickReviewRecord" :records="quickReviewRecords" @close="closeQuickReview" />
  <RegistrationActionModal :workspace="context.workspace" :kind="actionKind" :record="actionRecord" :initial-action="actionSelection" @close="actionRecord = undefined" @saved="refresh" />
</template>
