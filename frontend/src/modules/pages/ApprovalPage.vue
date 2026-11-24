<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :show-command="false" :show-content="false">
    <template #header-actions>
    <el-button type="primary" @click="startApproval">发起审批</el-button>
    <el-button @click="router.push('/inspection/system/approval_settings')">流程设置</el-button>
    <el-button type="primary" plain @click="router.push('/inspection/system/user')">角色设置</el-button>
    </template>

  <div class="row g-3">
    <el-card v-for="item in kpis" :key="item.name" shadow="never" class="col-12 col-md-6">
      <span>{{ item.name }}</span>
      <strong>{{ item.value }}</strong>
      <small>{{ item.note }}</small>
    </el-card>
  </div>

  <BusinessFilters
    :state="filter.state"
    :status-options="filter.statusOptions.value"
    :total="filter.result.value.length"
    keyword-placeholder="申请单号 / 关联单据 / 申请人"
    @reset="filter.reset"
  />

  <div class="row g-3">
    <el-card class="col-12 col-md-6" shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>审批事项</strong>
          <el-tag size="small">8 类</el-tag>
        </div>
      </template>
      <div class="list-group">
        <el-button v-for="item in approvalTypes" :key="item">
          <span>{{ item }}</span>
          <el-tag size="small" type="info">{{ typeCount(item) }}</el-tag>
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="col-12 col-md-6" data-ui="fill-card">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>统一审批列表</strong>
          <el-tag size="small">待办 / 申请 / 查询</el-tag>
        </div>
      </template>
      <el-table :data="filter.result.value" border height="100%">
        <el-table-column prop="no" label="申请单号" width="150" />
        <el-table-column prop="type" label="审批类型" min-width="130" />
        <el-table-column prop="target" label="关联单据" min-width="140" />
        <el-table-column prop="department" label="申请部门" width="120" />
        <el-table-column prop="person" label="申请人" width="100" />
        <el-table-column prop="status" label="审批状态" width="110" />
        <el-table-column prop="node" label="当前节点" width="130" />
        <el-table-column prop="date" label="提交时间" width="130" />
        <el-table-column label="操作" fixed="right" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="selectedNo = row.no">查看</el-button>
            <el-button size="small" type="primary">审批</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="col-12 col-md-6" shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>审批详情</strong>
          <el-tag type="warning" size="small">多级审批</el-tag>
        </div>
      </template>
      <div class="row g-3">
        <div class="col-12 col-md-6"><span class="form-label d-block">申请单号</span>{{ selectedRow.no }}</div>
        <div class="col-12 col-md-6"><span class="form-label d-block">审批类型</span>{{ selectedRow.type }}</div>
        <div class="col-12 col-md-6"><span class="form-label d-block">关联单据</span>{{ selectedRow.target }}</div>
        <div class="col-12 col-md-6"><span class="form-label d-block">当前节点</span>{{ selectedRow.node }}</div>
      </div>
      <el-input class="text-muted small" type="textarea" :model-value="selectedRow.reason" disabled />
      <div >
        <div v-for="node in flowNodes" :key="node.name" >
          <strong>{{ node.name }}</strong>
          <span>{{ node.status }}</span>
        </div>
      </div>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <el-button type="primary" @click="act('同意')">同意</el-button>
        <el-button @click="act('退回')">退回</el-button>
        <el-button @click="act('转办')">转办</el-button>
      </div>
    </el-card>
  </div>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { approvalRows, approvalTypes } from '@/data/mock'
import { useTableFilter } from '@/composables/tableFilter'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import BusinessFilters from '@/components/BusinessFilters.vue'

const route = useRoute()
const router = useRouter()

function startApproval() {
  ElMessage.info('发起审批：请在对应业务页面提交（如报告更改申请、收款登记），将进入此审批中心流转')
}
function act(action: string) {
  ElMessage.success(`${selectedRow.value.no} 已${action}（${selectedRow.value.type}）`)
}

// 审批列表的关键词 + 状态 + 提交时间筛选
const filter = useTableFilter(
  () => approvalRows as unknown as Record<string, unknown>[],
  { statusField: 'status', dateField: 'date', keywordFields: ['no', 'target', 'person', 'type'] },
)
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const selectedNo = ref(approvalRows[0].no)
const selectedRow = computed(() => approvalRows.find((row) => row.no === selectedNo.value) ?? approvalRows[0])

const kpis = [
  { name: '审批待办', value: 18, note: '报告更改/收款登记' },
  { name: '我发起的', value: 6, note: '2 条退回' },
  { name: '可撤回', value: 3, note: '未审批' },
  { name: '流程类型', value: 9, note: '系统配置' },
  { name: '平均耗时', value: '1.6天', note: '本月' },
]

const flowNodes = [
  { name: '申请人', status: '已提交' },
  { name: '科室负责人', status: '已同意' },
  { name: '部门负责人', status: '待审批' },
  { name: '分管领导', status: '未到达' },
]

function typeCount(type: string) {
  return approvalRows.filter((row) => row.type === type).length || 0
}
</script>
