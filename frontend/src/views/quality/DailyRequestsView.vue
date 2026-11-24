<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import TemplateDateRange from '../../components/common/TemplateDateRange.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import DailyRequestModal from '../../components/quality/DailyRequestModal.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { clientMonthRange } from '../../services/common/date'
import { parseTableColumns } from '../../services/common/table'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import { currentActor } from '../../stores/session'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { dailyRequestColumns, dailyRequestItems, dailyRequestStatuses, type DailyRequestPage, type DailyRequestQuery, type DailyRequestRow, type DailyRequestMode } from '../../types/quality/dailyRequests'
import { canApplyDailyRequests } from '../../types/quality/dailyRequests'
const route = useRoute(), router = useRouter(), dates = clientMonthRange()
const props = withDefaults(defineProps<{ approvalMode?: boolean }>(), { approvalMode: false })
const title = computed(() => props.approvalMode ? '日常事务审批' : '日常事务申请')
const text = (key: string, fallback = '') => typeof route.query[key] === 'string' ? route.query[key] as string : fallback
const query = computed<DailyRequestQuery>(() => ({ from: text('from', dates.from), to: text('to', dates.to), code: text('code'), departmentId: text('departmentId'), applicant: text('applicant'), reason: text('reason'), item: text('item'), status: text('status', props.approvalMode ? '待审批' : ''), page: Math.max(1, Number(text('page', '1')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ from: '', to: '', code: '', departmentId: '', applicant: '', reason: '', item: '', status: '' })
const more = ref(false)
const activeFilters = computed(() => Number(!!draft.applicant) + Number(!!draft.reason) + Number(!!draft.item) + Number(!!draft.status))
watch(query, q => Object.assign(draft, q), { immediate: true })
const rows = ref<DailyRequestPage>({ items: [], total: 0, page: 1, pageSize: 10 }), loading = ref(false), error = ref<ErrorValue>(''), actionError = ref<ErrorValue>(''), exporting = ref(false), selected = ref<string[]>([])
const dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const columnKeys = computed(() => parseTableColumns(dailyRequestColumns, route.query.columns)), columns = computed(() => dailyRequestColumns.filter(c => columnKeys.value.includes(c.key)))
const modal = ref<{ mode: DailyRequestMode; record?: DailyRequestRow }>()
const departments = computed(() => registrationDepartments.filter(d => currentActor.value.scope === 'all' || d.id === currentActor.value.departmentId))
const canCreate = computed(() => canApplyDailyRequests(currentActor.value))
let epoch = 0, exportEpoch = 0, controller: AbortController | undefined
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
async function load() {
  controller?.abort(); const active = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await (props.approvalMode ? registrationDemo.dailyApprovals : registrationDemo.dailyRequests)(query.value, active.signal); if (token === epoch) rows.value = result }
  catch (e) { if (token === epoch && !active.signal.aborted) { error.value = normalizeError(e); rows.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() {
  if (loading.value) return
  if (!dateInput.value?.validate()) { more.value = true; return }
  const previous = route.fullPath
  await patch({ from: draft.from, to: draft.to, code: draft.code || undefined, departmentId: draft.departmentId || undefined, applicant: draft.applicant || undefined, reason: draft.reason || undefined, item: draft.item || undefined, status: draft.status, page: '1' })
  if (previous === route.fullPath) void load()
}
function toggleColumn(key: string, checked: boolean) { const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key); void patch({ columns: [...keys].join(',') }) }
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportEpoch; exporting.value = true; actionError.value = ''
  try { const csv = await (props.approvalMode ? registrationDemo.exportDailyApprovals : registrationDemo.exportDailyRequests)({ ...query.value, ...(onlySelected ? { ids: selected.value } : {}) }); if (token === exportEpoch) downloadBlob(csv, `${title.value}.csv`) }
  catch (e) { if (token === exportEpoch) actionError.value = normalizeError(e) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch([() => JSON.stringify(query.value), () => currentActor.value.id, () => props.approvalMode], (values, old) => { modal.value = undefined; exportEpoch++; exporting.value = false; actionError.value = ''; if (old && values[1] !== old[1]) rows.value.items = []; void load() }, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading :title="title" />
  <section class="card" :aria-label="`${title}列表区域`">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ title }}</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ rows.total }}</span></div>
      <TableToolbar :label="title" :columns="dailyRequestColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button type="button" class="btn btn-primary text-nowrap" v-if="!approvalMode" :disabled="!canCreate || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></TableToolbar>
    </div>
    <form class="card-body border-bottom" :aria-label="`${title}查询`" @submit.prevent="search">
      <QueryFormLayout>
        <div class="row g-3 align-items-start">
          <div class="col-12 col-xl-6"><label for="daily-request-dates" class="form-label">申请时间</label><TemplateDateRange id="daily-request-dates" ref="dateInput" :from="draft.from" :to="draft.to" @change="Object.assign(draft, $event)" /></div>
          <div class="col-6 col-xl-3"><label for="daily-request-code" class="form-label">申请单号</label><input id="daily-request-code" v-model="draft.code" class="form-control" maxlength="200" /></div>
          <div class="col-6 col-xl-3"><label for="daily-request-department" class="form-label">申请部门</label><select id="daily-request-department" v-model="draft.departmentId" class="form-select"><option value="">全部</option><option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option></select></div>
        </div>
        <div v-show="more" id="daily-request-more-filters" class="row g-3 align-items-end mt-0">
          <div class="col-12 col-sm-6 col-xl-3"><label for="daily-request-applicant" class="form-label">申请人</label><input id="daily-request-applicant" v-model="draft.applicant" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl-3"><label for="daily-request-reason" class="form-label">办理事由</label><input id="daily-request-reason" v-model="draft.reason" class="form-control" maxlength="200" /></div>
          <div class="col-12 col-sm-6 col-xl-3"><label for="daily-request-item" class="form-label">办理事项</label><select id="daily-request-item" v-model="draft.item" class="form-select"><option value="">全部</option><option v-for="item in dailyRequestItems" :key="item">{{ item }}</option></select></div>
          <div class="col-12 col-sm-6 col-xl-3"><label for="daily-request-status" class="form-label">审批状态</label><select id="daily-request-status" v-model="draft.status" class="form-select"><option value="">全部</option><option v-for="s in dailyRequestStatuses" :key="s">{{ s }}</option></select></div>
        </div>
        <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button class="btn btn-link text-nowrap" type="button" :aria-expanded="more" aria-controls="daily-request-more-filters" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button></template>
      </QueryFormLayout>
    </form>
    <div v-if="actionError" class="px-3 pt-3"><ErrorNotice :error="actionError" /></div>
    <DataTable :label="title" :rows="rows.items" :columns="columns" :row-key="r => r.id" :row-label="r => r.code" v-model:selected="selected" :pagination="{ ...rows, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #cell-appliedAt="{ row }">{{ new Date(row.appliedAt).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }}</template>
      <template #cell-status="{ row }"><span class="badge bg-info-subtle text-info">{{ row.status }}</span></template>
      <template #actions="{ row }">
        <template v-if="approvalMode">
          <button class="dropdown-item" role="menuitem" :disabled="!row.canApprove" @click="modal = { mode: 'approve', record: row }"><i class="ti ti-check me-2 text-muted" aria-hidden="true"></i>审批</button>
          <button class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', record: row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
          <button class="dropdown-item" role="menuitem" :disabled="!row.canRevoke" @click="modal = { mode: 'revoke', record: row }"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>撤回</button>
          <button class="dropdown-item" role="menuitem" :disabled="!row.canVoid" @click="modal = { mode: 'void', record: row }"><i class="ti ti-circle-x me-2 text-muted" aria-hidden="true"></i>作废</button>
        </template>
        <template v-else>
          <button class="dropdown-item" role="menuitem" :disabled="!row.canEdit" @click="modal = { mode: 'edit', record: row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>修改</button>
          <button class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', record: row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看</button>
          <button class="dropdown-item" role="menuitem" :disabled="!row.canWithdraw" @click="modal = { mode: 'withdraw', record: row }"><i class="ti ti-arrow-back-up me-2 text-muted" aria-hidden="true"></i>撤销</button>
          <button class="dropdown-item" role="menuitem" :disabled="!row.canDelete" @click="modal = { mode: 'delete', record: row }"><i class="ti ti-trash me-2 text-muted" aria-hidden="true"></i>删除</button>
        </template>
      </template>
    </DataTable>
  </section>
  <DailyRequestModal :approval-page="approvalMode" v-if="modal" :key="`${modal.mode}:${modal.record?.id || ''}`" v-bind="modal" @close="modal = undefined" @saved="modal = undefined; load()" />
</template>
