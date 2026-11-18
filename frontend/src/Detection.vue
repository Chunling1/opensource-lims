<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TaskPager from './TaskPager.vue'
import { IconSearch, IconInbox } from '@tabler/icons-vue'
import { api, ApiError, reportStates, type Listing, type ReportRow } from './api'

const emit = defineEmits<{ expired: [] }>()
const route = useRoute(),
  router = useRouter()
const isReport = route.name === 'reports'
const page = Number(route.query.page) || 1,
  view = route.query.view === 'mine' ? 'mine' : 'pool'
const filters = reactive({
  commission: String(route.query.commission ?? ''),
  project: String(route.query.project ?? ''),
  number: String(route.query.number ?? ''),
  sample: String(route.query.sample ?? ''),
  state: String(route.query.state ?? ''),
})
const samples = ref<Listing['rows']>([]),
  reports = ref<ReportRow[]>([]),
  total = ref(0),
  pageSize = ref(10),
  loading = ref(true),
  error = ref('')
const cols = computed(() =>
  isReport
    ? ['报告编号', '样品', '委托编号', '负责人', '报告状态', '操作']
    : ['样品编号', '样品名称', '委托编号', '样品状态', '操作'],
)
function search() {
  const query = Object.fromEntries(Object.entries(filters).filter(([, v]) => v))
  return router.push({
    name: route.name!,
    query: { ...query, pageSize: route.query.pageSize, ...(isReport ? {} : { view }) },
  })
}
async function load() {
  loading.value = true
  error.value = ''
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(route.query)) if (typeof v === 'string') q.set(k, v)
  try {
    if (isReport) {
      const data = await api<Omit<Listing, 'rows'> & { rows: ReportRow[] }>('reports?' + q)
      reports.value = data.rows
      total.value = data.total
      pageSize.value = data.pageSize
    } else {
      const data = await api<Listing>('samples?' + q)
      samples.value = data.rows
      total.value = data.total
      pageSize.value = data.pageSize
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
    if (e instanceof ApiError && e.status === 401) emit('expired')
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <div class="page-header mt-0 mb-3">
    <div class="page-pretitle">检测工作</div>
    <h1 class="page-title">{{ isReport ? '检测报告' : '检测样品' }}</h1>
  </div>
  <section class="card">
    <div v-if="!isReport" class="card-header">
      <ul class="nav nav-tabs card-header-tabs">
        <li v-for="v in ['pool', 'mine'] as const" :key="v" class="nav-item">
          <RouterLink
            class="nav-link"
            :class="{ active: view === v }"
            :to="{
              name: 'samples',
              query: { ...route.query, view: v, page: undefined, state: undefined },
            }"
            >{{ v === 'pool' ? '待领取池' : '我负责的样品' }}</RouterLink
          >
        </li>
      </ul>
    </div>
    <form class="card-body border-bottom" @submit.prevent="search">
      <div class="row g-2 align-items-end">
        <template v-if="isReport"
          ><label class="col-md-3 form-label mb-0"
            >报告编号<input v-model="filters.number" class="form-control" /></label
          ><label class="col-md-3 form-label mb-0"
            >样品名称或编号<input v-model="filters.sample" class="form-control" /></label
        ></template>
        <template v-else
          ><label class="col-md-3 form-label mb-0"
            >委托编号<input v-model="filters.commission" class="form-control" /></label
          ><label class="col-md-3 form-label mb-0"
            >项目或方法<input v-model="filters.project" class="form-control" /></label
        ></template>
        <label class="col-md-3 form-label mb-0"
          >状态<select v-model="filters.state" class="form-select">
            <option value="">全部</option>
            <template v-if="isReport"
              ><option v-for="(label, key) in reportStates" :key="key" :value="key">
                {{ label }}
              </option></template
            ><template v-else
              ><option value="pool">待领取</option>
              <option value="mine">检测中</option>
              <option value="frozen">冻结</option></template
            >
          </select></label
        >
        <div class="col-md-auto">
          <button class="btn btn-primary"><IconSearch class="icon" />查询</button>
        </div>
      </div>
    </form>
    <div v-if="error" class="alert alert-danger m-3" role="alert">{{ error }}</div>
    <div class="table-responsive">
      <table class="table table-vcenter table-hover card-table">
        <thead>
          <tr>
            <th
              class="fw-bold text-nowrap"
              v-for="c in cols"
              :key="c"
              :class="{
                'd-none d-md-table-cell': ['委托编号', '负责人', '样品名称', '样品'].includes(c),
              }"
            >
              {{ c }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in samples" :key="s.id">
            <td>
              <RouterLink :to="{ name: 'sample', params: { sid: s.id }, query: route.query }">{{
                s.number
              }}</RouterLink
              ><small class="d-md-none d-block text-secondary">{{ s.name }}</small>
            </td>
            <td class="d-none d-md-table-cell">{{ s.name }}</td>
            <td class="d-none d-md-table-cell">{{ s.commission }}</td>
            <td>
              <span
                class="status text-nowrap"
                :class="
                  s.frozen ? 'status-orange' : view === 'pool' ? 'status-blue' : 'status-teal'
                "
                ><span class="status-dot"></span
                >{{ s.frozen ? '冻结' : view === 'pool' ? '待领取' : '检测中' }}</span
              >
            </td>
            <td>
              <RouterLink
                class="btn btn-sm text-nowrap"
                :to="{ name: 'sample', params: { sid: s.id }, query: route.query }"
                >打开工作表</RouterLink
              >
            </td>
          </tr>
          <tr v-for="r in reports" :key="r.id">
            <td>
              <RouterLink
                :to="{ name: 'report', params: { sid: r.sampleId, rid: r.id }, query: route.query }"
                >{{ r.number }}</RouterLink
              >
            </td>
            <td class="d-none d-md-table-cell">
              {{ r.sampleName }}<small class="d-block text-secondary">{{ r.sampleNumber }}</small>
            </td>
            <td class="d-none d-md-table-cell">{{ r.commission }}</td>
            <td class="d-none d-md-table-cell">{{ r.owner ?? '—' }}</td>
            <td>
              <span
                class="status text-nowrap"
                :class="
                  r.state === 'draft'
                    ? 'status-blue'
                    : r.state === 'review'
                      ? 'status-teal'
                      : 'status-secondary'
                "
                ><span class="status-dot"></span>{{ reportStates[r.state] }}</span
              >
            </td>
            <td>
              <RouterLink
                class="btn btn-sm text-nowrap"
                :to="{ name: 'report', params: { sid: r.sampleId, rid: r.id }, query: route.query }"
                >打开工作表</RouterLink
              >
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p v-if="loading" class="card-body">正在读取列表…</p>
    <div v-else-if="!total && !error" class="empty py-4">
      <div class="empty-icon"><IconInbox /></div>
      <p class="empty-title">没有符合条件的{{ isReport ? '报告' : '样品' }}。</p>
      <button class="btn btn-sm" @click="load">刷新</button>
    </div>
    <TaskPager :page="page" :size="pageSize" :total="total" />
  </section>
</template>
