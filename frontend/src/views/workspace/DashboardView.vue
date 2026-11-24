<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import DataTable from '../../components/common/table/DataTable.vue'
import ScrollableTabs from '../../components/common/ScrollableTabs.vue'
import type { TableColumn } from '../../types/common/table'
import LoadState from '../../components/common/LoadState.vue'
import { authenticated, currentActor, sessionLocked, canRead, roleLabels } from '../../stores/session'
import { platformRequest } from '../../services/platform/http'
import { profile } from '../../services/platform/auth'
import { defaultWorkbench } from '../../types/dashboard'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { allowedWorkbench, type Workbench, type DashboardData, type DashboardFilter, type DashboardTask } from '../../types/dashboard'
import { moduleMap } from '../../services/business/modules'
import { navigation, flattenNavigation } from '../../router/navigation/navigation'

const route = useRoute(), workbench = computed(() => (route.meta.workbench || defaultWorkbench(currentActor.value).split('/').pop()) as Workbench)
const data = ref<DashboardData>(), loading = ref(false), error = ref<ErrorValue>('')
const queue = ref(''), filter = ref<DashboardFilter>('all'), page = ref(1), pageSize = ref(10)
let controller: AbortController | undefined, epoch = 0
const general = computed(() => workbench.value === 'general')
const admin = computed(() => workbench.value === 'admin')
const title = computed(() => String(route.meta.title))
const shortcuts = computed(() => navigation.filter(group => group.id !== 'overview').flatMap(group => flattenNavigation(group.children))
  .filter(item => item.permission && profile.value?.permissions.includes(item.permission))
  
  .slice(0, 8))
const metrics = computed(() => [
  { label: admin.value ? '待处理任务' : workbench.value === 'analyst' ? '我的待录入' : '岗位待处理', value: data.value?.pending || 0, icon: 'ti ti-file-description', tone: 'primary' },
  { label: '已超期任务', value: data.value?.overdue || 0, icon: 'ti ti-clock', tone: 'primary' },
  { label: '今日完成', value: data.value?.completedToday || 0, icon: 'ti ti-circle-check', tone: 'primary' },
])
const queueTabs = computed(() => data.value?.queues.map(item => ({ key: item.id, label: `${item.title}（${item.total}）`, panelId: 'dashboard-tasks-panel' })) || [])
const taskLabel = computed(() => workbench.value === 'analyst' ? '我的检测任务' : admin.value ? '流程待办' : '岗位待办')
const columns: TableColumn<keyof DashboardTask>[] = [
  { key: 'code', label: '样品 / 报告编号' },
  { key: 'name', label: '样品 / 工程名称', wrap: true },
  { key: 'due', label: '检测期限' },
  { key: 'status', label: '当前数据状态' },
]
const maxTrend = computed(() => Math.max(1, ...data.value?.trend.map(row => row.count) || []))
const dateTime = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
async function load() {
  const token = ++epoch
  controller?.abort()
  if (!authenticated.value || sessionLocked.value || !allowedWorkbench(currentActor.value, workbench.value)) { loading.value = false; return }
  const active = controller = new AbortController()
  loading.value = true; error.value = ''
  try {
    const result = await platformRequest<DashboardData>('/api/auth/workbench', { method: 'POST', body: { workbench: workbench.value, queue: queue.value || undefined, filter: filter.value, page: page.value, pageSize: pageSize.value }, signal: active.signal })
    if (token !== epoch) return
    data.value = result; queue.value = result.queue; page.value = result.page
  } catch (cause) { if (token === epoch && !active.signal.aborted) error.value = normalizeError(cause) }
  finally { if (token === epoch) loading.value = false }
}
function selectQueue(id: string) { queue.value = id; page.value = 1; void load() }
function selectFilter(value: DashboardFilter) { filter.value = value; page.value = 1; void load() }
function changeSize(value: number) { pageSize.value = value; page.value = 1; void load() }
function changePage(value: number) { page.value = value; void load() }
watch([workbench, () => JSON.stringify(currentActor.value)], () => { data.value = undefined; queue.value = ''; page.value = 1; pageSize.value = 10; filter.value = 'all'; void load() }, { immediate: true })
watch(sessionLocked, () => { void load() })
function refreshVisible() { if (document.visibilityState === 'visible') void load() }
window.addEventListener('focus', refreshVisible)
onBeforeUnmount(() => { epoch++; controller?.abort(); window.removeEventListener('focus', refreshVisible) })
</script>

<template>
  <PageHeading :title="title" />
  <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-4">
    <div><h5 class="mb-1">{{ currentActor.name }}，欢迎回来</h5><p class="text-muted mb-0">{{ currentActor.roles.map(role => roleLabels[role] || role).join(' / ') }}</p></div>
    <div class="d-flex align-items-center gap-3"><span v-if="data" class="text-muted small">更新于 {{ dateTime(data.updatedAt) }}</span><button class="btn btn-light text-body text-nowrap" :disabled="loading" @click="load"><i class="ti ti-refresh align-middle me-1" aria-hidden="true"></i>{{ loading ? '刷新中' : '刷新' }}</button></div>
  </div>
  <LoadState :loading="loading && !data" :error="error" :has-data="!!data" @retry="load" />
  <template v-if="data">
    <p class="text-muted">待办按当前工作台、业务权限和数据授权显示；不同岗位的数量可能不同。</p>
    <div v-if="general" class="card"><div class="card-header"><h5 class="card-title mb-0">常用业务</h5></div><div class="card-body"><div class="row g-3"><div v-for="item in shortcuts" :key="item.to" class="col-sm-6 col-xl-3"><RouterLink :to="item.to" class="d-flex align-items-center gap-3 p-3 border rounded text-body"><span class="avatar-sm flex-shrink-0"><span class="avatar bg-primary-subtle text-primary rounded"><i :class="item.icon" class="fs-2" aria-hidden="true"></i></span></span><span>{{ item.label }}</span><i class="ti ti-chevron-right ms-auto" aria-hidden="true"></i></RouterLink></div></div><p v-if="!shortcuts.length" class="text-muted mb-0">暂无可用业务入口。</p></div></div>
    <div class="row project-wrapper">
      <div class="col-xl-8">
        <div class="row">
          <div v-for="metric in metrics" :key="metric.label" class="col-md-4"><div class="card"><div class="card-body"><div class="d-flex align-items-center"><div class="avatar-sm flex-shrink-0"><span class="avatar rounded-2 fs-2" :class="[`bg-${metric.tone}-subtle`, `text-${metric.tone}`]"><i :class="metric.icon" aria-hidden="true"></i></span></div><div class="flex-grow-1 overflow-hidden ms-3"><p class="fw-medium text-muted text-truncate mb-2">{{ metric.label }}</p><h4 class="fs-4 mb-0">{{ metric.value }}<span class="text-muted small fw-normal ms-2">项</span></h4></div></div></div></div></div>
        </div>
        <section class="card" aria-label="工作台待办区域" :aria-busy="loading">
          <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
            <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0">{{ taskLabel }}</h5><span class="badge bg-primary-subtle text-body">{{ data.pending }}</span></div>
            <span v-if="data.returned" class="text-muted">退回处理中 {{ data.returned }}</span>
          </div>
          <div class="px-3 pt-2 border-bottom">
            <ScrollableTabs :tabs="queueTabs" :model-value="queue" label="待办环节" id-prefix="dashboard-queue" variant="underline" :disabled="loading" @update:model-value="selectQueue" />
          </div>
          <div id="dashboard-tasks-panel" role="tabpanel" :aria-labelledby="`dashboard-queue-tab-${queue}`">
            <div class="p-3 border-bottom d-flex flex-wrap align-items-center gap-3">
              <div class="d-flex align-items-center gap-2"><label for="dashboard-filter" class="form-label mb-0 text-nowrap">待办范围</label><select id="dashboard-filter" class="form-select w-auto" :value="filter" :disabled="loading" @change="selectFilter(($event.target as HTMLSelectElement).value as DashboardFilter)"><option value="all">全部</option><option value="overdue">已超期</option><option value="returned">退回处理中</option></select></div>
              <span class="text-muted ms-sm-auto">超期及退回任务优先排列</span>
            </div>
            <DataTable :label="taskLabel" :rows="data.items" :columns="columns" :row-key="row => row.id" :row-label="row => row.code"
              :pagination="{ ...data, sizes: [10, 20, 50] }" :loading="loading" preserve-rows-on-loading @page="changePage" @size="changeSize">
              <template #cell-code="{ row }"><RouterLink :to="row.to" class="fw-medium">{{ row.code }}</RouterLink><div class="text-muted mt-1">{{ row.reportCode || '—' }}</div></template>
              <template #cell-name="{ row }"><span>{{ row.name }}</span><div class="text-muted mt-1">{{ row.plan || '—' }}</div></template>
              <template #cell-due="{ row }"><span :class="{ 'text-danger': row.overdue }">{{ row.due || '—' }}</span><i v-if="row.overdue" class="ti ti-clock text-danger ms-1" aria-label="已超期"></i></template>
              <template #cell-status="{ row }"><span class="badge bg-primary-subtle text-body">{{ row.status }}</span><span v-if="row.returned" class="badge bg-danger-subtle text-danger ms-1">退回</span></template>
              <template #actions="{ row }"><RouterLink :to="row.to" class="dropdown-item" role="menuitem"><i class="ti ti-edit align-bottom me-2 text-muted" aria-hidden="true"></i>{{ row.action }}</RouterLink></template>
              <template #empty><p class="mt-2 mb-0">暂无符合条件的待办</p></template>
            </DataTable>
          </div>
        </section>
        <div v-if="admin" class="row"><div class="col-lg-7"><div class="card"><div class="card-header"><h5 class="card-title mb-0">近七日完成情况</h5></div><div class="card-body"><svg viewBox="0 0 560 170" class="w-100" role="img" aria-label="近七日各检测处理环节完成数量"><line x1="15" x2="545" y1="135" y2="135" stroke="var(--vz-border-color)" /><g v-for="(point, index) in data.trend" :key="point.date"><rect :x="index * 76 + 28" :y="135 - point.count / maxTrend * 100" width="32" :height="point.count / maxTrend * 100" rx="3" fill="var(--vz-primary)" /><text :x="index * 76 + 44" :y="125 - point.count / maxTrend * 100" text-anchor="middle" fill="var(--vz-body-color)" font-size="16">{{ point.count }}</text><text :x="index * 76 + 44" y="158" text-anchor="middle" fill="var(--vz-secondary-color)" font-size="16">{{ point.date.slice(5) }}</text></g></svg></div></div></div><div class="col-lg-5"><div class="card"><div class="card-header"><h5 class="card-title mb-0">在办任务主检分布</h5></div><div class="card-body"><div v-for="person in data.workload" :key="person.name" class="d-flex justify-content-between border-bottom py-2"><span>{{ person.name }}</span><span class="badge bg-primary-subtle text-body">{{ person.count }}</span></div><p v-if="!data.workload.length" class="text-muted mb-0">暂无在办任务。</p></div></div></div></div>
      </div>
      <div class="col-xl-4">
        <div class="card"><div class="card-header"><h5 class="card-title mb-0">优先处理</h5></div><div class="card-body"><div v-for="task in data.urgent" :key="task.to" class="d-flex gap-3 mb-3 pb-3 border-bottom"><div class="avatar-xs flex-shrink-0"><span class="avatar rounded" :class="task.overdue ? 'bg-danger-subtle text-danger' : 'bg-primary-subtle text-primary'"><i class="ti ti-clock" aria-hidden="true"></i></span></div><div class="flex-grow-1 overflow-hidden"><RouterLink :to="task.to" class="fw-medium text-body d-block text-truncate">{{ task.name }}</RouterLink><div class="text-muted small mt-1">{{ task.code }}</div><div class="d-flex justify-content-between flex-wrap gap-1 mt-2 small"><span class="text-muted">{{ task.status }}</span><span :class="task.overdue ? 'text-danger' : 'text-muted'">{{ task.due || '未设置检测期限' }}</span></div></div></div><p v-if="!data.urgent.length" class="text-muted mb-0">暂无待处理任务。</p></div></div>
        <div class="card"><div class="card-header"><h5 class="card-title mb-0">最近完成</h5></div><div class="card-body"><div v-for="activity in data.recent" :key="activity.id" class="d-flex gap-3 mb-3"><div class="avatar-xs flex-shrink-0"><span class="avatar bg-primary-subtle text-primary rounded-circle"><i class="ti ti-check" aria-hidden="true"></i></span></div><div class="flex-grow-1 overflow-hidden"><RouterLink :to="activity.to" class="text-body fw-medium d-block text-truncate">{{ activity.code }}</RouterLink><div class="small mt-1">{{ activity.action }}</div><div class="small text-muted mt-1">{{ activity.actor }} · {{ dateTime(activity.at) }}</div></div></div><p v-if="!data.recent.length" class="text-muted mb-0">暂无完成记录。</p></div></div>
      </div>
    </div>
  </template>
</template>
