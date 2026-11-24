<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import TableToolbar from '../../components/common/table/TableToolbar.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { parseTableColumns } from '../../services/common/table'
import { downloadBlob } from '../../services/reports/reportPdf'
import TemplateToast from '../../components/common/TemplateToast.vue'
import CustomerAccountModal from '../../components/customers/CustomerAccountModal.vue'
import CustomerPasswordReset from '../../components/customers/CustomerPasswordReset.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { canManageCustomerAccounts, customerAccountColumns, type CustomerAccountPage, type CustomerAccount } from '../../types/customers/accounts'
const route = useRoute(), router = useRouter(), text = (key: string) => typeof route.query[key] === 'string' ? route.query[key] as string : ''
const query = computed(() => ({ code: text('code'), name: text('name'), page: Math.max(1, Number(text('page')) || 1), pageSize: [10, 20, 50].includes(Number(text('size'))) ? Number(text('size')) : 10 }))
const draft = reactive({ code: '', name: '' }), data = ref<CustomerAccountPage>({ items: [], total: 0, page: 1, pageSize: 10 }), selected = ref<string[]>([])
const loading = ref(false), error = ref<ErrorValue>(''), canWrite = computed(() => canManageCustomerAccounts(currentActor.value))
const exporting = ref(false), exportError = ref<ErrorValue>('')
const columnKeys = computed(() => parseTableColumns(customerAccountColumns, route.query.columns)), columns = computed(() => customerAccountColumns.filter(column => columnKeys.value.includes(column.key)))
const modal = ref<{ mode: 'new' | 'edit' | 'view'; row?: CustomerAccount }>(), resetRow = ref<CustomerAccount>(), toast = ref<InstanceType<typeof TemplateToast>>()
let controller: AbortController | undefined, epoch = 0, exportEpoch = 0
const patch = (values: Record<string, string | undefined>) => router.push({ path: route.path, query: { ...route.query, ...values } })
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; selected.value = []
  try { const result = await registrationDemo.customerAccounts(query.value, request.signal); if (token === epoch) data.value = result }
  catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); data.value.items = [] } }
  finally { if (token === epoch) loading.value = false }
}
async function search() { if (loading.value) return; const previous = route.fullPath; await patch({ code: draft.code.trim() || undefined, name: draft.name.trim() || undefined, page: '1' }); if (previous === route.fullPath) void load() }
async function saved() { modal.value = undefined; void load(); await nextTick(); toast.value?.show() }
function toggleColumn(key: string, checked: boolean) { const keys = new Set<string>(columnKeys.value); if (checked) keys.add(key); else keys.delete(key); void patch({ columns: [...keys].join(',') }) }
async function exportRows(onlySelected: boolean) {
  if (exporting.value || loading.value || error.value || onlySelected && !selected.value.length) return
  const token = ++exportEpoch; exporting.value = true; exportError.value = ''
  try { const blob = await registrationDemo.exportCustomerAccounts({ ...query.value, ...(onlySelected ? { ids: [...selected.value] } : {}) }); if (token === exportEpoch) downloadBlob(blob, '客户账号.csv') }
  catch (issue) { if (token === exportEpoch) exportError.value = normalizeError(issue) }
  finally { if (token === exportEpoch) exporting.value = false }
}
watch(query, value => Object.assign(draft, value), { immediate: true })
watch([() => JSON.stringify(query.value), () => currentActor.value.id], (value, old) => { exportEpoch++; exporting.value = false; exportError.value = ''; if (old && value[1] !== old[1]) { modal.value = undefined; resetRow.value = undefined; data.value.items = [] }; void load() }, { immediate: true })
onBeforeUnmount(() => { epoch++; exportEpoch++; controller?.abort() })
</script>
<template>
  <PageHeading title="账号管理" />
  <section class="card" aria-label="客户账号列表区域">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3"><div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">账号信息</h5><span v-if="!loading && !error" class="badge bg-primary-subtle text-body">{{ data.total }}</span></div><TableToolbar label="客户账号" :columns="customerAccountColumns" :selected="columnKeys" :count="selected.length" :export-disabled="loading || !!error || exporting" @column="toggleColumn" @reset="patch({ columns: undefined })" @export="exportRows"><button type="button" class="btn btn-primary text-nowrap" :disabled="!canWrite || loading" @click="modal = { mode: 'new' }"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增账号</button></TableToolbar></div>
    <form class="card-body border-bottom" aria-label="客户账号查询" @submit.prevent="search"><QueryFormLayout><div class="row g-3"><div class="col-12 col-md-6"><label for="customer-query-code" class="form-label">客户账号</label><input id="customer-query-code" v-model="draft.code" class="form-control" maxlength="200" /></div><div class="col-12 col-md-6"><label for="customer-query-name" class="form-label">客户名称</label><input id="customer-query-name" v-model="draft.name" class="form-control" maxlength="200" /></div></div><template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template></QueryFormLayout></form>
    <div v-if="exportError" class="px-3 pt-3"><ErrorNotice :error="exportError" /></div>
    <DataTable label="客户账号" :columns="columns" :rows="data.items" :row-key="row => row.id" :row-label="row => row.code" v-model:selected="selected" :pagination="{ ...data, sizes: [10, 20, 50] }" :loading="loading" :error="error" preserve-rows-on-loading @retry="load" @page="patch({ page: String($event) })" @size="patch({ size: String($event), page: '1' })">
      <template #actions="{ row }"><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="modal = { mode: 'edit', row }"><i class="ti ti-edit me-2 text-muted" aria-hidden="true"></i>修改账号</button><button type="button" class="dropdown-item" role="menuitem" @click="modal = { mode: 'view', row }"><i class="ti ti-eye me-2 text-muted" aria-hidden="true"></i>查看账号</button><button type="button" class="dropdown-item" role="menuitem" :disabled="!canWrite" @click="resetRow = row"><i class="ti ti-lock-password me-2 text-muted" aria-hidden="true"></i>密码重置</button></template>
    </DataTable>
  </section>
  <CustomerAccountModal v-if="modal" v-bind="modal" @close="modal = undefined" @saved="saved" />
  <CustomerPasswordReset v-if="resetRow" :row="resetRow" @close="resetRow = undefined" />
  <TemplateToast ref="toast" message="客户账号已保存。" />
</template>
