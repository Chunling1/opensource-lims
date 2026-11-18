<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IconInbox } from '@tabler/icons-vue'
import { api, ApiError, taskLabels, type TaskList, type TaskKind } from './api'
import TaskPager from './TaskPager.vue'
import DateInput from './DateInput.vue'
const emit = defineEmits<{ expired: []; counts: [TaskList['counts']] }>()
const allowedKinds = () => (Object.keys(taskLabels) as TaskKind[]).filter(k => data.value && k in data.value.counts)
const route = useRoute(),
  router = useRouter()
const kind = ref(String(route.query.kind ?? '')),
  start = ref(String(route.query.start ?? '')),
  end = ref(String(route.query.end ?? ''))
const data = ref<TaskList>(),
  error = ref(''),
  loading = ref(false)
function filter(k = kind.value) {
  return router.push({
    name: 'tasks',
    query: {
      kind: k || undefined,
      start: start.value || undefined,
      end: end.value || undefined,
      pageSize: route.query.pageSize,
    },
  })
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(route.query)) if (typeof v === 'string') q.set(k, v)
    data.value = await api<TaskList>('tasks?' + q)
    emit('counts', data.value.counts)
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
    <div class="page-pretitle">工作台</div>
    <h1 class="page-title">我的待办</h1>
  </div>
  <div class="row g-2 mb-3">
    <div v-for="key in allowedKinds()" :key="key" class="col-6 col-lg-3">
      <button
        class="card card-link w-100 text-start"
        :class="{ 'border-primary': kind === key }"
        @click="filter(String(key))"
      >
        <span class="card-body"
          ><span class="subheader">{{ taskLabels[key] }}</span
          ><strong class="h1 d-block mb-0 mt-1">{{
            data?.counts[key as TaskKind] ?? '—'
          }}</strong></span
        >
      </button>
    </div>
  </div>
  <section class="card">
    <form class="card-body border-bottom" @submit.prevent="filter()">
      <div class="row g-2 align-items-end">
        <label class="col-auto form-label mb-0"
          >待办类型<select class="form-select" v-model="kind">
            <option value="">全部</option>
            <option v-for="k in allowedKinds()" :value="k" :key="k">{{ taskLabels[k] }}</option>
          </select></label
        >
        <label class="col-auto form-label mb-0"
          >到达起日<DateInput v-model="start" :max="end || undefined" /></label
        ><label class="col-auto form-label mb-0"
          >到达止日<DateInput v-model="end" :min="start || undefined"
        /></label>
        <div class="col-auto"><button class="btn btn-primary">查询</button></div>
      </div>
    </form>
    <div v-if="error" class="alert alert-danger m-3" role="alert">{{ error }}</div>
    <div class="table-responsive">
      <table class="table table-vcenter card-table">
        <thead>
          <tr>
            <th>待办类型</th>
            <th>对象编号 / 名称</th>
            <th class="d-none d-md-table-cell">来源节点</th>
            <th class="d-none d-md-table-cell">到达时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in data?.rows" :key="t.kind + '-' + t.sampleId + '-' + t.reportId">
            <td class="text-nowrap">{{ taskLabels[t.kind] }}</td>
            <td>
              {{ t.number }}<small class="d-block text-secondary">{{ t.name }}</small>
            </td>
            <td class="d-none d-md-table-cell">{{ t.source }}</td>
            <td class="d-none d-md-table-cell">
              {{ t.arrived ? new Date(t.arrived).toLocaleString() : '历史时间未记录' }}
            </td>
            <td>
              <RouterLink
                class="btn btn-sm text-nowrap"
                :to="{
                  name: t.reportId ? 'report' : 'sample',
                  params: t.reportId ? { sid: t.sampleId, rid: t.reportId } : { sid: t.sampleId },
                  query: { ...route.query, from: 'tasks' },
                }"
                >{{ t.kind === 'review1' ? '查看送审资料' : '打开办理' }}</RouterLink
              >
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="loading" class="card-body">正在读取待办…</div>
    <div v-else-if="!error && !data?.total" class="empty py-4">
      <div class="empty-icon"><IconInbox /></div>
      <p class="empty-title">当前没有符合条件的待办</p>
      <button class="btn btn-sm" @click="load">刷新</button>
    </div>
    <TaskPager v-if="data" :page="data.page" :size="data.pageSize" :total="data.total" />
  </section>
</template>
