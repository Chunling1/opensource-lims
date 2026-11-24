<template>
  <ModuleWorkspace
    title="检测项目自定义"
    :area-name="areaName"
    :module-name="moduleName"
    
    :pages="pages"
    :active-key="pageKey"
    :show-command="false"
    :show-content="false"
  >
    <template #header-actions><button type="button" class="btn btn-light" @click="schemeManagerOpen = true">仪器方案</button><AdaptiveTableActions label="检测项目" :table-controls="false" :actions="projectActions" @action="runProjectAction" /></template>

  <EquipmentSchemeManager v-if="schemeManagerOpen" @close="schemeManagerOpen = false" />
  <SchemaForm :model="projectQueryModel" :schema="projectQuerySchema">
    <template #project-query-actions><el-button type="primary" :loading="loading" @click="load">搜索</el-button><span>共 {{ rows.length }} 个项目</span></template>
  </SchemaForm>

  <el-card shadow="never" >
    <template #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
        <strong>检测项目库</strong>
        <span class="text-muted small">单击项目后可修改；删除只停用业务选择，历史报告保持不变。</span>
      </div>
    </template>
    <el-table
      v-loading="loading"
      :data="rows"
      border
      height="calc(100vh - 390px)"
      highlight-current-row
      row-key="id"
      @current-change="selected = $event"
      @row-dblclick="openEdit"
    >
      <el-table-column width="48">
        <template #default="{ row }">
          <el-radio :model-value="selected?.id" :value="row.id" @change="selected = row">
            <span class="visually-hidden">选择</span>
          </el-radio>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="项目编号" width="150" />
      <el-table-column prop="name" label="项目名称" min-width="210" show-overflow-tooltip />
      <el-table-column prop="department" label="所属部门" min-width="180" show-overflow-tooltip />
      <el-table-column label="外部展示" width="112" align="center">
        <template #default="{ row }">
          <el-tag :type="row.externalPublished ? 'success' : 'info'" effect="light">
            {{ row.externalPublished ? '已发布' : '未发布' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="外部预估价" min-width="170" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="{ 'text-muted': !row.externalPublished }">{{ externalPriceText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="项目流程" min-width="420">
        <template #default="{ row }">
          <div class="d-flex flex-wrap gap-2">
            <el-tag
              v-for="step in row.workflowSteps"
              :key="step.code"
              size="small"
              :type="step.skipped ? 'info' : 'success'"
              :effect="step.skipped ? 'plain' : 'light'"
            >
              {{ step.name }}：{{ step.skipped ? '跳过' : '执行' }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.active ? 'success' : 'info'">
            {{ row.active ? '启用' : '已删除' }}
          </el-tag>
        </template>
      </el-table-column>
      <template #empty><el-empty description="没有匹配的检测项目" /></template>
    </el-table>
  </el-card>

  <el-dialog
    v-model="dialogOpen"
    :title="editingId ? '修改检测项目' : '新增检测项目'"
    width="min(1080px, 94vw)"
    destroy-on-close
  >
    <el-form label-width="92px">
      <div class="row g-3">
        <el-form-item class="col-12 col-md-6" label="项目编号" required>
          <el-input v-model="form.code" maxlength="40" placeholder="例如：SYHR" />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="项目名称" required>
          <el-input v-model="form.name" maxlength="80" placeholder="填写检测项目名称" />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="检测部门" required>
          <el-select v-model="form.departmentId" filterable placeholder="选择检测部门">
            <el-option
              v-for="department in departments"
              :key="department.id"
              :label="department.name"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="检测地点">
          <el-input v-model="form.testLocation" maxlength="120" placeholder="选择方案后自动带入，可不填" />
        </el-form-item>
      </div>

      <div class="h5 mb-3">
        <strong>方案默认填写内容</strong>
        <span>委托单选择本检测方案后，下列内容会自动填写，仍可按业务需要修改。</span>
      </div>
      <div class="row g-3">
        <el-form-item class="col-12 col-md-6" label="报告标题">
          <el-select
            v-model="form.centerPrefix"
            clearable
            filterable
            placeholder="选择报告标题"
            @change="onReportTitleChange"
          >
            <el-option
              v-for="item in reportTitleOptions"
              :key="item.prefix"
              :label="`${item.name}（${item.prefix}）`"
              :value="item.prefix"
            />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="检测类别">
          <el-select v-model="form.testCategory" clearable allow-create filterable placeholder="选择或填写检测类别">
            <el-option v-for="item in testCategoryOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="报告格式">
          <el-select v-model="form.reportType" clearable allow-create filterable placeholder="选择或填写报告格式">
            <el-option v-for="item in reportTypeOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="样品数量">
          <el-input v-model="form.sampleAmount" maxlength="40" placeholder="例如：2台、3件" />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="样品状态">
          <el-select v-model="form.sampleStatus" clearable allow-create filterable placeholder="选择或填写样品状态">
            <el-option label="正常" value="正常" />
            <el-option label="异常" value="异常" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测参数" class="col-12">
          <el-input
            v-model="form.detectionParameters"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="填写检测参数；多个参数可用逗号、顿号或换行分隔"
          />
        </el-form-item>
      </div>

      <div class="h5 mb-3 h6">
        <div>
          <strong>外部方案展示</strong>
          <span>开启后自动同步到外部检测服务平台，客户可查看方案、预估价格并发起网上委托。</span>
        </div>
        <el-switch
          v-model="form.externalPublished"
          inline-prompt
          active-text="展示"
          inactive-text="关闭"
        />
      </div>
      <div class="row g-3">
        <el-form-item class="col-12 col-md-6" label="外部标题">
          <el-input
            v-model="form.title"
            maxlength="100"
            placeholder="不填时使用检测项目名称"
          />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="服务分类">
          <el-select
            v-model="form.category"
            clearable
            allow-create
            filterable
            placeholder="选择或填写服务分类"
          >
            <el-option v-for="item in externalCategoryOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="方案摘要" class="col-12">
          <el-input
            v-model="form.summary"
            type="textarea"
            :rows="2"
            maxlength="240"
            show-word-limit
            placeholder="用一两句话说明适用对象、核心能力和客户价值"
          />
        </el-form-item>
        <el-form-item label="展示标签" class="col-12">
          <el-select
            v-model="form.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入标签后回车，例如：CNAS、加急、热门"
          >
            <el-option v-for="item in externalTagOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="价格方式">
          <el-select v-model="form.priceType" placeholder="选择价格方式">
            <el-option label="固定预估价" value="fixed" />
            <el-option label="预估价格区间" value="range" />
            <el-option label="面议" value="negotiable" />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="计价单位">
          <el-select v-model="form.priceUnit" clearable allow-create filterable placeholder="例如：元/项">
            <el-option v-for="item in priceUnitOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="最低/固定价">
          <el-input-number
            v-model="form.priceMin"
            :min="0"
            :precision="2"
            :disabled="form.priceType === 'negotiable'"
            controls-position="right"
            placeholder="输入预估价"
          />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="最高预估价">
          <el-input-number
            v-model="form.priceMax"
            :min="0"
            :precision="2"
            :disabled="form.priceType !== 'range'"
            controls-position="right"
            placeholder="区间价格时填写"
          />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="市场原价">
          <el-input-number
            v-model="form.originalPrice"
            :min="0"
            :precision="2"
            controls-position="right"
            placeholder="可不填"
          />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="预计周期">
          <el-input-number
            v-model="form.turnaroundDays"
            :min="1"
            :max="3650"
            controls-position="right"
            placeholder="工作日"
          />
          <span >工作日</span>
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="优惠说明">
          <el-input v-model="form.promotion" maxlength="100" placeholder="例如：组合项目享九折" />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="咨询电话">
          <el-input v-model="form.contactPhone" maxlength="40" placeholder="外部客户咨询电话" />
        </el-form-item>
        <el-form-item class="col-12 col-md-6" label="展示设置">
          <div >
            <el-checkbox v-model="form.featured">首页推荐</el-checkbox>
            <span>排序</span>
            <el-input-number v-model="form.sort" :min="0" :max="9999" controls-position="right" />
          </div>
        </el-form-item>
        <el-form-item label="方案详情" class="col-12">
          <el-input
            v-model="form.detail"
            type="textarea"
            :rows="4"
            maxlength="4000"
            show-word-limit
            placeholder="填写服务范围、检测内容、交付成果等外部展示详情"
          />
        </el-form-item>
        <el-form-item label="送样要求" class="col-12">
          <el-input
            v-model="form.sampleRequirements"
            type="textarea"
            :rows="3"
            maxlength="2000"
            show-word-limit
            placeholder="填写样品数量、尺寸、包装、资料及送达要求"
          />
        </el-form-item>
      </div>

      <div class="h6 mb-3">
        <div>
          <strong>项目流程设置</strong>
          <p>选择“跳过”后，该项目的报告到达该环节时会自动进入下一环节。</p>
        </div>
        <div>
          <el-button size="small" @click="form.skippedSteps = []">全部执行</el-button>
          <el-button
            size="small"
            type="warning"
            plain
            @click="form.skippedSteps = workflowSteps.map((item) => item.code)"
          >全部跳过</el-button>
        </div>
      </div>
      <div class="row g-3">
        <div v-for="(step, index) in workflowSteps" :key="step.code" class="col-12 col-md-6">
          <span >{{ index + 1 }}</span>
          <span >{{ step.name }}</span>
          <el-radio-group v-model="stepModes[step.code]" size="small">
            <el-radio-button value="execute">执行</el-radio-button>
            <el-radio-button value="skip">跳过</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <hr class="my-3" />
      <div class="row g-3">
        <div class="col-12 col-md-6">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="fw-semibold">多级审核配置（留空默认单级审核）</span>
            <el-button size="small" type="primary" plain @click="addStage('review')">+ 增加审核级</el-button>
          </div>
          <div v-for="(st, idx) in (form.reviewStages || [])" :key="`rev-${idx}`" class="d-flex gap-2 align-items-center mb-2">
            <input v-model="st.name" type="text" class="form-control form-control-sm" placeholder="级次名称（如：一级审核）" />
            <input :value="st.userAccounts.join(',')" type="text" class="form-control form-control-sm" placeholder="指定账号（逗号分隔，空则角色池）" @input="st.userAccounts = ($event.target as HTMLInputElement).value.split(',').map(s => s.trim()).filter(Boolean)" />
            <el-button size="small" type="danger" plain @click="form.reviewStages?.splice(idx, 1)">删</el-button>
          </div>
        </div>
        <div class="col-12 col-md-6">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <span class="fw-semibold">多级批准配置（留空默认单级批准）</span>
            <el-button size="small" type="primary" plain @click="addStage('approval')">+ 增加批准级</el-button>
          </div>
          <div v-for="(st, idx) in (form.approvalStages || [])" :key="`app-${idx}`" class="d-flex gap-2 align-items-center mb-2">
            <input v-model="st.name" type="text" class="form-control form-control-sm" placeholder="级次名称（如：一级批准）" />
            <input :value="st.userAccounts.join(',')" type="text" class="form-control form-control-sm" placeholder="指定账号（逗号分隔，空则角色池）" @input="st.userAccounts = ($event.target as HTMLInputElement).value.split(',').map(s => s.trim()).filter(Boolean)" />
            <el-button size="small" type="danger" plain @click="form.approvalStages?.splice(idx, 1)">删</el-button>
          </div>
        </div>
      </div>
    </el-form>
    <template #footer>
      <el-button @click="dialogOpen = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存项目</el-button>
    </template>
  </el-dialog>

  <el-drawer v-model="catalogDrawerOpen" title="门户检测对象目录诊断" size="min(860px, 94vw)">
    <div v-loading="catalogLoading" >
      <el-alert
        title="仅精确对象或已确认别名可进入候选；缺少现行标准、两个检测项目或合规本地图片时不会自动发布。"
        type="info"
        :closable="false"
        show-icon
      />
      <div v-if="catalogDiagnostics" >
        <el-statistic title="候选项目" :value="catalogDiagnostics.candidates.length" />
        <el-statistic title="本轮选中" :value="catalogDiagnostics.candidates.filter(item => item.selected).length" />
        <el-statistic title="未通过门禁" :value="catalogDiagnostics.candidates.filter(item => !item.eligible).length + catalogDiagnostics.rejected.length" />
      </div>
      <el-table v-if="catalogDiagnostics" :data="catalogDiagnostics.candidates" border max-height="520">
        <el-table-column prop="department" label="检测部门" min-width="160" show-overflow-tooltip />
        <el-table-column prop="objectName" label="检测对象" min-width="150" show-overflow-tooltip />
        <el-table-column prop="projectName" label="内部项目" min-width="170" show-overflow-tooltip />
        <el-table-column prop="score" label="分数" width="70" />
        <el-table-column label="结果" width="116">
          <template #default="{ row }"><el-tag :type="row.selected ? 'success' : row.eligible ? 'warning' : 'info'">{{ row.selected ? '拟发布' : row.eligible ? '候选未入选' : row.reason }}</el-tag></template>
        </el-table-column>
      </el-table>
    </div>
    <template #footer>
      <el-button :loading="catalogLoading" @click="previewCatalogSync">生成差异预览</el-button>
      <el-button type="primary" :loading="catalogLoading" @click="applyCatalogSync">确认同步能力快照</el-button>
    </template>
  </el-drawer>
  </ModuleWorkspace>
  <SubprojectCatalogDialog v-model="subprojectOpen" />
  <TechnicalSubprojectConfig v-model="technicalOpen" />
</template>

<script setup lang="ts">
import EquipmentSchemeManager from '../../platformUi/testing/EquipmentSchemeManager.vue'
const schemeManagerOpen = ref(false)
// BEGIN TEMPLATE PROJECTS IMPORTS
import AdaptiveTableActions from '../../components/common/table/AdaptiveTableActions.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import type { FormSchema } from '../../types/forms'
// END TEMPLATE PROJECTS IMPORTS

import SubprojectCatalogDialog from '@/components/SubprojectCatalogDialog.vue'
import TechnicalSubprojectConfig from '@/components/TechnicalSubprojectConfig.vue'
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import { computed, reactive, ref, watch } from 'vue'
const subprojectOpen = ref(false)
const technicalOpen = ref(false)
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import { modules } from '@/data/modules'
import {
  createProjectMaster,
  deleteProjectMaster,
  getProjectMasters,
  getPortalCatalogDiagnostics,
  syncPortalCatalog,
  updateProjectMaster,
  type ProjectMaster,
  type ProjectMasterPayload,
  type ProjectWorkflowStep,
  type PortalCatalogDiagnostics,
} from '@/services/projectConfig'

const route = useRoute()
const systemModule = modules.find((item) => item.key === 'system')!
const pages = systemModule.pages
const pageKey = computed(() => String(route.meta.pageKey || 'custom_project'))
const areaName = computed(() => String(route.meta.areaName || systemModule.areaName))
const moduleName = computed(() => String(route.meta.moduleName || systemModule.name))

const loading = ref(false)
const catalogLoading = ref(false)
const catalogDrawerOpen = ref(false)
const catalogDiagnostics = ref<PortalCatalogDiagnostics | null>(null)
const saving = ref(false)
const keyword = ref('')
const includeInactive = ref(false)
const rows = ref<ProjectMaster[]>([])
const selected = ref<ProjectMaster | null>(null)
const departments = ref<{ id: number; name: string }[]>([])
const workflowSteps = ref<ProjectWorkflowStep[]>([])
const dialogOpen = ref(false)
const editingId = ref<number | null>(null)
const reportTitleOptions = [
  { name: '空调中心', prefix: 'NCSA' },
  
  
  
  
  { name: '示例中心', prefix: 'LAB' },
]
const testCategoryOptions = ['委托', '校准', '抽样']
const reportTypeOptions = ['产品报告', '工程报告', '抽样报告', '检验（检查）报告', '校准报告']
const externalCategoryOptions = ['环境热工', '热工系统', '围护结构', '空调与净化', '智能电气', '综合检测']
const externalTagOptions = ['CNAS', 'CMA', '热门', '推荐', '可加急', '上门检测']
const priceUnitOptions = ['元/项', '元/组', '元/件', '元/台', '元/批', '元/平方米']
const form = reactive<ProjectMasterPayload>({
  code: '',
  name: '',
  departmentId: null,
  location: '',
  reportTitle: '',
  centerPrefix: '',
  testCategory: '',
  reportType: '',
  detectionParameters: '',
  sampleAmount: '',
  sampleStatus: '',
  testLocation: '',
  skippedSteps: [],
  reviewStages: [],
  approvalStages: [],
  active: true,
  externalPublished: false,
  title: '',
  summary: '',
  category: '',
  tags: [],
  priceType: 'negotiable',
  priceMin: null,
  priceMax: null,
  priceUnit: '元/项',
  originalPrice: null,
  turnaroundDays: null,
  promotion: '',
  featured: false,
  sort: 0,
  detail: '',
  sampleRequirements: '',
  contactPhone: '',
})
const stepModes = reactive<Record<string, 'execute' | 'skip'>>({})

async function openCatalogDiagnostics() {
  catalogDrawerOpen.value = true
  catalogLoading.value = true
  try {
    catalogDiagnostics.value = await getPortalCatalogDiagnostics()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '能力目录诊断失败')
  } finally {
    catalogLoading.value = false
  }
}

async function previewCatalogSync() {
  catalogLoading.value = true
  try {
    const result = await syncPortalCatalog(false)
    ElMessage.success(`差异预览完成：新增 ${result.created}，更新 ${result.updated}，不变 ${result.unchanged}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '差异预览失败')
  } finally {
    catalogLoading.value = false
  }
}

async function applyCatalogSync() {
  try {
    await ElMessageBox.confirm('同步将新增或更新能力快照，但不会删除方案或覆盖人工价格、标题和介绍。是否继续？', '确认同步门户目录', { type: 'warning' })
  } catch {
    return
  }
  catalogLoading.value = true
  try {
    const result = await syncPortalCatalog(true)
    ElMessage.success(`同步完成：新增 ${result.created}，更新 ${result.updated}，不变 ${result.unchanged}`)
    await openCatalogDiagnostics()
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '能力目录同步失败')
  } finally {
    catalogLoading.value = false
  }
}

watch(stepModes, (modes) => {
  form.skippedSteps = workflowSteps.value
    .filter((item) => modes[item.code] === 'skip')
    .map((item) => item.code)
}, { deep: true })
watch(() => form.skippedSteps, (steps) => {
  const skipped = new Set(steps)
  for (const item of workflowSteps.value) {
    stepModes[item.code] = skipped.has(item.code) ? 'skip' : 'execute'
  }
}, { deep: true })

const beginListSearch = useSearchRequest(() => [keyword.value, includeInactive.value])
async function load() {
  const current = beginListSearch()
  loading.value = true
  try {
    const result = await getProjectMasters(keyword.value, includeInactive.value)
    if (!current()) return
    rows.value = result.rows
    departments.value = result.departments
    workflowSteps.value = result.workflowSteps
    selected.value = rows.value.find((item) => item.id === selected.value?.id) ?? null
  } catch (error) {
    if (current()) ElMessage.error(error instanceof Error ? error.message : '检测项目加载失败')
  } finally {
    if (current()) loading.value = false
  }
}

function resetForm(row?: ProjectMaster) {
  editingId.value = row?.id ?? null
  form.code = row?.code ?? ''
  form.name = row?.name ?? ''
  form.departmentId = row?.departmentId ?? null
  form.location = row?.location ?? ''
  form.reportTitle = row?.reportTitle ?? ''
  form.centerPrefix = row?.centerPrefix ?? ''
  form.testCategory = row?.testCategory ?? ''
  form.reportType = row?.reportType ?? ''
  form.detectionParameters = row?.detectionParameters ?? row?.name ?? ''
  form.sampleAmount = row?.sampleAmount ?? ''
  form.sampleStatus = row?.sampleStatus ?? ''
  form.testLocation = row?.testLocation ?? row?.location ?? ''
  form.skippedSteps = [...(row?.skippedSteps ?? [])]
  form.reviewStages = (row?.reviewStages ?? []).map((item) => ({ ...item, userAccounts: [...(item.userAccounts || [])] }))
  form.approvalStages = (row?.approvalStages ?? []).map((item) => ({ ...item, userAccounts: [...(item.userAccounts || [])] }))
  form.active = row?.active ?? true
  form.externalPublished = Boolean(row?.externalPublished)
  form.title = row?.title ?? row?.externalTitle ?? ''
  form.summary = row?.summary ?? ''
  form.category = row?.category ?? ''
  form.tags = Array.isArray(row?.tags)
    ? row.tags.map((item) => String(item).trim()).filter(Boolean)
    : []
  form.priceType = row?.priceType === 'fixed' || row?.priceType === 'range'
    ? row.priceType
    : 'negotiable'
  form.priceMin = row?.priceMin ?? null
  form.priceMax = row?.priceMax ?? null
  form.priceUnit = row?.priceUnit ?? '元/项'
  form.originalPrice = row?.originalPrice ?? null
  form.turnaroundDays = row?.turnaroundDays ?? null
  form.promotion = row?.promotion ?? ''
  form.featured = Boolean(row?.featured)
  form.sort = row?.sort ?? 0
  form.detail = row?.detail ?? ''
  form.sampleRequirements = row?.sampleRequirements ?? ''
  form.contactPhone = row?.contactPhone ?? ''
  const skipped = new Set(form.skippedSteps)
  for (const item of workflowSteps.value) {
    stepModes[item.code] = skipped.has(item.code) ? 'skip' : 'execute'
  }
}
function externalPriceText(row: ProjectMaster) {
  if (row.priceType === 'negotiable' || row.priceMin == null) return '面议'
  const unit = row.priceUnit ? ` ${row.priceUnit}` : ''
  const minimum = Number(row.priceMin).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  if (row.priceType === 'range' && row.priceMax != null) {
    const maximum = Number(row.priceMax).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
    return `${minimum}–${maximum}${unit}`
  }
  return `${minimum}${unit}`
}
function addStage(kind: 'review' | 'approval') {
  if (kind === 'review') {
    form.reviewStages = form.reviewStages || []
    form.reviewStages.push({ name: `审核第${form.reviewStages.length + 1}级`, roleKey: 'reviewer', userAccounts: [] })
  } else {
    form.approvalStages = form.approvalStages || []
    form.approvalStages.push({ name: `批准第${form.approvalStages.length + 1}级`, roleKey: 'approver', userAccounts: [] })
  }
}
function onReportTitleChange(prefix: string) {
  form.reportTitle = reportTitleOptions.find((item) => item.prefix === prefix)?.name ?? ''
}
function openCreate() {
  resetForm()
  dialogOpen.value = true
}
async function openEdit(row?: ProjectMaster) {
  const target = row?.id ? row : selected.value
  if (!target) return
  resetForm(target)
  dialogOpen.value = true
}
async function save() {
  form.code = form.code.trim().toUpperCase()
  form.name = form.name.trim()
  form.location = form.testLocation.trim()
  form.title = form.title.trim()
  form.summary = form.summary.trim()
  form.category = form.category.trim()
  form.tags = [...new Set(form.tags.map((item) => item.trim()).filter(Boolean))]
  form.priceUnit = form.priceUnit.trim()
  form.promotion = form.promotion.trim()
  form.detail = form.detail.trim()
  form.sampleRequirements = form.sampleRequirements.trim()
  form.contactPhone = form.contactPhone.trim()
  if (!form.code || !form.name || !form.departmentId) {
    ElMessage.warning('请填写项目编号、项目名称并选择所属部门')
    return
  }
  if (form.externalPublished && form.priceType !== 'negotiable' && form.priceMin == null) {
    ElMessage.warning('外部展示方案采用固定价或区间价时，请填写最低/固定预估价')
    return
  }
  if (
    form.externalPublished
    && form.priceType === 'range'
    && (form.priceMax == null || form.priceMin == null || form.priceMax < form.priceMin)
  ) {
    ElMessage.warning('请填写有效的预估价格区间，最高价不能低于最低价')
    return
  }
  if (form.priceType === 'fixed') form.priceMax = null
  if (form.priceType === 'negotiable') {
    form.priceMin = null
    form.priceMax = null
  }
  saving.value = true
  try {
    if (editingId.value) await updateProjectMaster(editingId.value, { ...form })
    else await createProjectMaster({ ...form })
    dialogOpen.value = false
    await load()
    ElMessage.success(editingId.value ? '检测项目已保存' : '检测项目已新增')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}
async function removeSelected() {
  if (!selected.value) return
  try {
    await ElMessageBox.confirm(
      `确认删除项目「${selected.value.code} ${selected.value.name}」？历史单据会保留。`,
      '删除检测项目',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    await deleteProjectMaster(selected.value.id)
    await load()
    ElMessage.success('检测项目已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error instanceof Error ? error.message : '删除失败')
    }
  }
}
async function restoreSelected() {
  if (!selected.value) return
  await updateProjectMaster(selected.value.id, {
    code: selected.value.code,
    name: selected.value.name,
    departmentId: selected.value.departmentId,
    location: selected.value.location,
    reportTitle: selected.value.reportTitle,
    centerPrefix: selected.value.centerPrefix,
    testCategory: selected.value.testCategory,
    reportType: selected.value.reportType,
    detectionParameters: selected.value.detectionParameters,
    sampleAmount: selected.value.sampleAmount,
    sampleStatus: selected.value.sampleStatus,
    testLocation: selected.value.testLocation,
    skippedSteps: selected.value.skippedSteps,
    reviewStages: (selected.value.reviewStages ?? []).map((item) => ({ ...item, userAccounts: [...(item.userAccounts || [])] })),
    approvalStages: (selected.value.approvalStages ?? []).map((item) => ({ ...item, userAccounts: [...(item.userAccounts || [])] })),
    active: true,
    externalPublished: Boolean(selected.value.externalPublished),
    title: selected.value.title ?? selected.value.externalTitle ?? '',
    summary: selected.value.summary ?? '',
    category: selected.value.category ?? '',
    tags: [...(selected.value.tags ?? [])],
    priceType: selected.value.priceType === 'fixed' || selected.value.priceType === 'range'
      ? selected.value.priceType
      : 'negotiable',
    priceMin: selected.value.priceMin ?? null,
    priceMax: selected.value.priceMax ?? null,
    priceUnit: selected.value.priceUnit ?? '元/项',
    originalPrice: selected.value.originalPrice ?? null,
    turnaroundDays: selected.value.turnaroundDays ?? null,
    promotion: selected.value.promotion ?? '',
    featured: Boolean(selected.value.featured),
    sort: selected.value.sort ?? 0,
    detail: selected.value.detail ?? '',
    sampleRequirements: selected.value.sampleRequirements ?? '',
    contactPhone: selected.value.contactPhone ?? '',
  })
  await load()
  ElMessage.success('检测项目已恢复')
}

void load()
useLiveSearch(keyword, load)

// BEGIN TEMPLATE PROJECTS ADAPTER
const projectQueryModel={}
const projectQuerySchema:FormSchema<typeof projectQueryModel>={sections:[{id:'project-query',title:'查询检测项目',fields:[{id:'project-keyword',label:'项目编号、名称或所属部门',control:'text',binding:{get:()=>keyword.value,set:(_,value)=>keyword.value=value}},{id:'project-inactive',label:'显示已删除项目',control:'checkbox',binding:{get:()=>includeInactive.value,set:(_,value)=>{includeInactive.value=value;void load()}}},{id:'project-query-submit',label:'查询',labelHidden:true,control:'custom',slot:'project-query-actions'}]}]}
const projectActions=computed(()=>[{label:'新增项目',icon:'ti ti-plus'},{label:'修改项目',icon:'ti ti-edit',disabled:!selected.value},{label:selected.value?.active?'删除项目':'恢复项目',icon:selected.value?.active?'ti ti-trash':'ti ti-refresh',disabled:!selected.value},{label:'子项目信息配置',icon:'ti ti-settings'},{label:'检测子项目配置',icon:'ti ti-adjustments'},{label:'门户能力目录',icon:'ti ti-book'}])
function runProjectAction(index:number){if(index===0)openCreate();else if(index===1&&selected.value)openEdit();else if(index===2&&selected.value){if(selected.value.active)void removeSelected();else void restoreSelected()}else if(index===3)subprojectOpen.value=true;else if(index===4)technicalOpen.value=true;else if(index===5)void openCatalogDiagnostics()}
// END TEMPLATE PROJECTS ADAPTER
</script>


