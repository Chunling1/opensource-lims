<template>
  <section class="card mb-3">
    <div class="card-header"><strong>本部门已发放报告</strong></div>
    <div class="card-body">
      <form class="d-flex gap-2 mb-3" @submit.prevent="page = 1; load()">
        <input v-model="keyword" class="form-control" aria-label="已发放报告编号" placeholder="按报告编号查询" maxlength="100" />
        <button class="btn btn-primary" :disabled="loading">查询</button>
      </form>
      <p v-if="error" class="text-danger">{{ error }}</p>
      <table class="table"><thead><tr><th>报告编号</th><th>样品编号</th><th>操作</th></tr></thead>
        <tbody><tr v-for="row in rows" :key="row.reportNo"><td>{{ row.reportNo }}</td><td>{{ row.sampleNo }}</td><td><button class="btn btn-light btn-sm" @click="selected = row.reportNo">查看</button></td></tr></tbody>
      </table>
      <p v-if="!loading && !rows.length" class="text-muted">暂无已发放报告</p>
      <div class="d-flex gap-2"><button class="btn btn-light" :disabled="loading || page <= 1" @click="page--; load()">上一页</button><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span><button class="btn btn-light" :disabled="loading || page * 20 >= total" @click="page++; load()">下一页</button></div>
    </div>
    <BootstrapModal :open="!!selected" title="报告文件" size="xl" @close="selected = ''"><ReportArtifactPanel v-if="selected" :report-no="selected" view="release" /></BootstrapModal>
  </section>
</template>
<script setup lang="ts">
import {onMounted, ref} from 'vue'
import {request} from '../services/http'
import ReportArtifactPanel from './ReportArtifactPanel.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
const rows = ref<{reportNo: string; sampleNo: string}[]>([]), total = ref(0), page = ref(1), keyword = ref('')
const loading = ref(false), selected = ref(''), error = ref('')
let generation = 0
async function load() {
  const id = ++generation; loading.value = true; error.value = ''
  try {
    const result = await request<{rows: typeof rows.value; total: number}>(`/api/report-assurance/released?page=${page.value}&keyword=${encodeURIComponent(keyword.value)}`)
    if (id === generation) { rows.value = result.rows; total.value = result.total }
  } catch (e) { if (id === generation) error.value = e instanceof Error ? e.message : '查询失败' }
  finally { if (id === generation) loading.value = false }
}
onMounted(load)
</script>
