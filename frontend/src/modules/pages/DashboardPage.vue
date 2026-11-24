<template>
  <ModuleWorkspace title="我的待办" :area-name="areaName" :module-name="moduleName" :path="route.path" :show-command="false" :show-content="false">
    <template #header-actions>
    <el-button v-if="session.can('entrust.registration.view') && !session.businessReadOnly" type="primary" @click="router.push({ path: '/inspection/entrust/registration', query: { action: 'create' } })">新增委托</el-button>
    <el-button @click="reload">刷新</el-button>
    </template>

  <div class="row g-3">
    <el-card
      v-for="b in buckets"
      :key="b.key"
      shadow="never"
      class="col-12 col-md-6"
      @click="b.first && goTo(b.first)"
    >
      <span>{{ b.name }}</span>
      <strong>{{ b.rows.length }}</strong>
      <small>{{ b.note }}</small>
    </el-card>
  </div>

  <div class="row g-3">
    <el-card shadow="never" class="col-12 col-md-6" data-ui="fill-card">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>我的待办</strong>
          <el-tag v-if="overdue" type="danger" size="small">{{ overdue }} 个超期/加急</el-tag>
          <el-tag v-else type="success" size="small">无超期</el-tag>
        </div>
      </template>
      <el-table :data="todoRows" border height="100%"  @row-click="goTo">
        <el-table-column prop="reportNo" label="报告编号" min-width="160" />
        <el-table-column prop="project" label="检测项目" min-width="120" />
        <el-table-column prop="client" label="委托单位" min-width="140" />
        <el-table-column label="当前节点" width="130">
          <template #default="{ row }"><el-tag size="small" :type="nodeTagType(row.status)">{{ row.dataStatus || row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="owner" label="责任人" width="100" />
        <el-table-column label="操作" fixed="right" width="100">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="goTo(row)">去处理</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无待办" :image-size="70" /></template>
      </el-table>
    </el-card>

    <el-card class="col-12 col-md-6" shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2"><strong>快捷入口</strong></div>
      </template>
      <div class="list-group">
        <el-button v-for="item in quickLinks" :key="item.path" @click="router.push(item.path)">
          {{ item.name }}
        </el-button>
      </div>
    </el-card>
  </div>

  <SampleDrawer v-model="drawerOpen" />
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { shallowRef, computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { reportWorkRows } from '@/data/mock'
import { fetchReportRows, type ReportRow } from '@/services/auth'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import SampleDrawer from '@/components/SampleDrawer.vue'
import { canOpenDashboardPath, dashboardRoutes, dashboardTarget } from '@/utils/dashboardAccess'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const drawerOpen = ref(false)
const areaName = computed(() => route.meta.areaName ?? '')
const moduleName = computed(() => route.meta.moduleName ?? '')

// 报告当前状态 → 处理该节点的页面
const canOpen = (path: string) => canOpenDashboardPath(path, session.can)
function nodeTagType(status: string) {
  if (status === '退回待重传' || status === '委托更改中') return 'danger'
  if (['待合同评审', '待样品入库', '待样品领取'].includes(status)) return 'warning'
  return 'primary'
}

const rows = shallowRef<ReportRow[]>([])
let reloadEpoch = 0
async function reload() {
  const epoch = ++reloadEpoch
  rows.value = []
  try {
    const result = await fetchReportRows(reportWorkRows, session.dataScope, session.userName, 'dashboard')
    if (epoch === reloadEpoch) rows.value = result
  } catch {
    if (epoch === reloadEpoch) ElMessage.error('待办加载失败，请刷新重试')
  }
}
onMounted(reload)

// 后端同时校验数据范围、功能、项目环节、当前状态；前端再次校验目的页面。
const todoRows = computed(() => rows.value.filter(r => dashboardTarget(r, session.can, session.businessReadOnly)))
const overdue = computed(() => todoRows.value.filter((r) => r.deadline === '超期' || r.deadline === '加急').length)

const buckets = computed(() => {
  const by = (sts: string[]) => todoRows.value.filter((r) => sts.includes(r.status))
  const mk = (key: string, name: string, sts: string[], note: string) => {
    const delivery = ['archive', 'release'].includes(key)
    const list = delivery ? todoRows.value.filter(r => r.todoView === key) : by(sts).filter(r => !['archive', 'release'].includes(r.todoView || ''))
    const visible = !session.businessReadOnly && (delivery ? canOpen(`/inspection/report/${key}`) : sts.some(status => {
      const target = dashboardRoutes[status]
      return target && canOpen(target.path)
    }))
    return { key, name, note, visible, rows: list, first: list[0] as ReportRow | undefined }
  }
  return [
    mk('review_contract', '待合同评审', ['待合同评审'], '委托/样品登记后'),
    mk('sample_flow', '待样品流转', ['待样品入库', '待样品领取'], '入库与出库领取'),
    mk('data_entry', '检测录入', ['检测录入中', '退回待重传', '检测更改中'], '录入检测数据'),
    mk('review', '待审核', ['待审核', '待校核'], '审核签名'),
    mk('approve', '待批准', ['待批准'], '批准签发'),
    mk('issue', '待签发', ['待打印'], '电子签署与签发'),
    mk('archive', '待归档', ['待发放', '已发放'], '盖章完成后归档'),
    mk('release', '待发放', ['待发放', '已发放'], '归档完成后发放'),
    mk('change', '委托更改', ['委托更改中'], '退回需更改'),
  ].filter(bucket => bucket.visible)
})

function goTo(row?: ReportRow) {
  if (!row) return
  const path = dashboardTarget(row, session.can, session.businessReadOnly)
  if (path) router.push({ path, query: { keyword: row.reportNo } })
}

const quickLinks = computed(() => [
  { name: '合同评审', path: '/inspection/report/contract_review' },
  { name: '报告审核', path: '/inspection/report/review' },
  { name: '报告批准', path: '/inspection/report/approval' },
  { name: '样品流转查询', path: '/inspection/sample/flow_query' },
].filter(item => canOpen(item.path)))
</script>
