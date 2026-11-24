<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :show-command="false" :show-content="false">
    <template #header-actions>
    <el-button type="primary">保存设置</el-button>
    <el-button>查看记录</el-button>
    <el-button v-if="pageType === 'integration'">立即推送</el-button>
    <el-button v-if="pageType === 'template'">上传模板</el-button>
    <el-button v-if="pageType === 'notification'">发送测试</el-button>
    </template>

  <div class="row g-3">
    <el-card class="col-12 col-md-6" shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>{{ pageName }}</strong>
          <el-tag type="warning" size="small">横切能力</el-tag>
        </div>
      </template>
      <el-form label-position="top" >
        <el-row :gutter="12">
          <el-col v-for="field in fields" :key="field[0]" :span="12">
            <el-form-item :label="field[0]">
              <el-input :model-value="field[1]" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="说明">
              <el-input
                type="textarea"
                :model-value="`${pageName} 是跨模块能力，需要被委托、检测、报告、财务和系统管理复用。`"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card class="col-12 col-md-6" shadow="never">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>{{ sideTitle }}</strong>
          <el-tag size="small">{{ sideTag }}</el-tag>
        </div>
      </template>

      <el-table v-if="pageType === 'template'" :data="templateRows" border>
        <el-table-column prop="code" label="模板标识" min-width="180" />
        <el-table-column prop="name" label="模板名称" min-width="150" />
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column prop="sign" label="签名位置" width="140" />
        <el-table-column prop="print" label="展现方式" width="110" />
        <el-table-column prop="status" label="状态" width="90" />
      </el-table>

      <el-table v-else-if="pageType === 'auth'" :data="authRows" border>
        <el-table-column prop="name" label="姓名" width="100" />
        <el-table-column prop="department" label="部门" min-width="130" />
        <el-table-column prop="password" label="账号密码" width="100" />
        <el-table-column prop="dongle" label="加密狗" width="100" />
        <el-table-column prop="fingerprint" label="指纹" width="100" />
        <el-table-column prop="sign" label="电子签名" width="100" />
      </el-table>

      <div v-else-if="pageType === 'notification'" class="row g-3">
        <div v-for="[code, name] in notificationVariables" :key="code" class="col-12 col-md-6">
          <span class="form-label d-block">{{ name }}</span>{{ code }}
        </div>
      </div>

      <div v-else >
        <div v-for="field in fields" :key="field[0]" class="col-12 col-md-6">
          <span class="form-label d-block">{{ field[0] }}</span>{{ field[1] }}
        </div>
      </div>
    </el-card>
  </div>

  <el-card shadow="never" >
    <template #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
        <strong>{{ pageName }}记录</strong>
        <el-button size="small">导出</el-button>
      </div>
    </template>
    <el-table :data="logs" border>
      <el-table-column prop="time" label="时间" width="170" />
      <el-table-column prop="object" label="对象" min-width="180" />
      <el-table-column prop="action" label="动作" min-width="160" />
      <el-table-column prop="result" label="结果" min-width="150" />
      <el-table-column prop="operator" label="操作人" width="120" />
    </el-table>
  </el-card>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { authRows, capabilityFields, capabilityLogs, notificationVariables, templateRows } from '@/data/mock'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'

const route = useRoute()
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageType = computed(() => String(route.meta.pageType ?? 'integration') as keyof typeof capabilityFields)
const fields = computed(() => capabilityFields[pageType.value] ?? capabilityFields.integration)
const logs = computed(() => capabilityLogs[pageType.value] ?? capabilityLogs.integration)
const sideTitle = computed(() => {
  if (pageType.value === 'template') return '报告模板版本'
  if (pageType.value === 'notification') return '通知变量'
  if (pageType.value === 'auth') return '登录与签名方式'
  if (pageType.value === 'collection') return '采集状态摘要'
  return '接口摘要'
})
const sideTag = computed(() => {
  if (pageType.value === 'template') return 'Word / 套打'
  if (pageType.value === 'notification') return '短信 / 邮件'
  if (pageType.value === 'auth') return '账号 / 加密狗 / 指纹'
  if (pageType.value === 'collection') return '仪器数据'
  return '外部ERP'
})
</script>
