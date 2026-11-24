<template>
  <StandardsPresentation :context="standardsPresentation" />
  <ScopeEvidenceDialog v-model="scopeEvidenceOpen" />
  <StandardParameterManager v-model="parameterOpen" :standard="parameterStandard" />
  <input ref="importInput" type="file" accept=".xlsx" class="d-none" @change="onImportFile" />
  <!-- 修改检测标准基础信息（图1） -->
  <el-dialog v-if="datasetMode === 'controlled'" v-model="editOpen" :title="controlledReadOnly ? '查看检测标准基础信息' : (form?.id ? '修改检测标准基础信息' : '新增检测标准基础信息')" width="860px" top="6vh" >
    <el-alert v-if="controlledReadOnly" type="info" :closable="false" show-icon class="mb-3" title="只读查看" />
    <SchemaForm v-if="form" :model="form" :schema="standardFormSchema" :readonly="controlledReadOnly || departmentOnly" />
    <template #footer>
      <el-button @click="editOpen = false">返回</el-button>
      <el-button v-if="!departmentOnly && form?.id" @click="openParameters(form)">参数维护</el-button>
      <el-button v-if="!controlledReadOnly && form?.id && session.canAction('quality.standard.delete')" type="danger" plain :loading="controlledRemoving" @click="confirmRemoveControlled(form)">移除</el-button>
      <el-button v-if="!controlledReadOnly && form?.id && session.canAction('quality.standard.void')" type="danger" plain :disabled="form.status === '已作废'" @click="voidCurrent">作废标准</el-button>
      <el-button v-if="!controlledReadOnly && canSave" type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="departmentAuthOpen" title="标准部门授权" width="720px" top="10vh">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="勾选后，该部门拥有“标准基础信息库[科室]”功能的人员即可查看此标准。"
      class="text-muted small"
    />
    <el-descriptions v-if="departmentAuthItem" :column="1" border >
      <el-descriptions-item label="标准编号">{{ departmentAuthItem.code }}</el-descriptions-item>
      <el-descriptions-item label="标准名称">{{ departmentAuthItem.name }}</el-descriptions-item>
    </el-descriptions>
    <el-checkbox-group v-model="departmentAuthValues" class="row g-3">
      <el-checkbox class="col-12 col-md-6" v-for="department in depts" :key="department" :value="department" :label="department" />
    </el-checkbox-group>
    <template #footer>
      <el-button @click="departmentAuthOpen = false">取消</el-button>
      <el-button type="primary" :loading="departmentAuthSaving" @click="saveDepartmentAuthorization">保存授权</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="masterEditOpen" :title="masterForm?.id ? '编辑标准主数据' : '新增标准主数据'" width="720px" top="8vh">
    <SchemaForm v-if="masterForm" :model="masterForm" :schema="standardMasterSchema" :readonly="masterViewOnly || !canSaveMaster" />
    <template #footer>
      <el-button @click="masterEditOpen = false">取消</el-button>
      <el-button v-if="!masterViewOnly && masterForm?.id && session.canAction('quality.master_standard.delete')" type="danger" plain :loading="masterRemoving" @click="confirmRemoveMaster(masterForm)">移除主数据</el-button>
      <el-button v-if="!masterViewOnly && canSaveMaster" type="primary" :loading="masterSaving" @click="saveMaster">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="cnasOpen" title="CNAS 能力批次与待确认部门映射" width="94%" top="4vh" >
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <el-select v-model="cnasBatchId" placeholder="选择导入批次"  @change="reloadCnasEntries(1)">
        <el-option
          v-for="batch in cnasBatches"
          :key="batch.id"
          :value="batch.id"
          :label="`#${batch.id} ${batch.sourceName} · ${batch.status} · 待确认${batch.pendingCount}`"
        />
      </el-select>
      <el-input v-model="cnasKeyword" clearable placeholder="标准 / 对象 / 项目"  @keyup.enter="reloadCnasEntries(1)" />
      <el-switch v-model="cnasPendingOnly" active-text="只看待确认" @change="reloadCnasEntries(1)" />
      <el-button @click="reloadCnasEntries(1)">查询</el-button>
      <el-tag v-if="selectedCnasBatch" :type="selectedCnasBatch.anomalyCount ? 'danger' : 'success'">
        解析异常 {{ selectedCnasBatch.anomalyCount }}
      </el-tag>
      <el-tag v-if="selectedCnasBatch" :type="selectedCnasBatch.pendingCount ? 'warning' : 'success'">
        待确认 {{ selectedCnasBatch.pendingCount }}
      </el-tag>
      <el-button
        v-if="selectedCnasBatch?.status !== 'active'"
        type="success"
        :disabled="!canActivateCnas"
        :loading="cnasActivating"
        @click="activateSelectedCnas"
      >
        激活该批次
      </el-button>
    </div>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="只有解析异常为 0 且所有能力记录均完成部门映射后才允许激活；激活后样品登记才会使用本批次。"
    />
    <el-table :data="cnasEntries" border height="58vh" v-loading="cnasLoading" >
      <el-table-column prop="capabilityType" label="类型" width="70" />
      <el-table-column prop="site" label="场所" width="90" />
      <el-table-column prop="standardCode" label="标准编号" min-width="150" show-overflow-tooltip />
      <el-table-column prop="standardName" label="标准名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="objectName" label="检测对象" min-width="160" show-overflow-tooltip />
      <el-table-column prop="itemName" label="项目/参数" min-width="160" show-overflow-tooltip />
      <el-table-column label="来源" width="115">
        <template #default="{ row }">第 {{ row.sourcePage }} 页</template>
      </el-table-column>
      <el-table-column label="部门映射" min-width="300" fixed="right">
        <template #default="{ row }">
          <div >
            <el-select v-model="cnasDepartmentIds[row.id]" multiple filterable collapse-tags placeholder="选择一个或多个部门">
              <el-option v-for="department in cnasDepartments" :key="department.id" :label="department.name" :value="department.id" />
            </el-select>
            <el-button size="small" type="primary" @click="saveCnasMapping(row)">保存</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-if="cnasTotal > cnasSize"
      v-model:current-page="cnasPage"
      
      background
      layout="prev, pager, next, total"
      :total="cnasTotal"
      :page-size="cnasSize"
      @current-change="reloadCnasEntries()"
    />
  </el-dialog>

</template>

<script setup lang="ts">
// BEGIN TEMPLATE STANDARDS IMPORTS
import StandardParameterManager from '@/components/StandardParameterManager.vue'
import {reactive} from 'vue'
import StandardsPresentation from '../../platformUi/quality/StandardsPresentation.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import {createStandardsPresentation,standardSchema,masterStandardSchema} from '../../platformUi/quality/standardsPresentation'
// END TEMPLATE STANDARDS IMPORTS
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import ModuleCommandBar from '@/components/ModuleCommandBar.vue'
import ModuleContentCard from '@/components/ModuleContentCard.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import ScopeEvidenceDialog from '@/components/ScopeEvidenceDialog.vue'
import {
  activateCnasBatch,
  getCatalog,
  listCnasBatches,
  listCnasEntries,
  updateCnasEntryDepartments,
  type CnasBatch,
  type CnasMappingEntry,
} from '@/services/admin'
import {
  createStandard,
  createStd,
  downloadStdLibraryTemplate,
  exportStdLibrary,
  fetchQualityDepts,
  fetchStandards,
  fetchStdLibrary,
  importStdLibrary,
  removeStd,
  removeStandard,
  updateStandard,
  updateStd,
  updateStdDepartments,
  voidStd,
  type StandardMasterItem,
  type StdItem,
} from '@/services/quality'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const session = useSessionStore()
const scopeEvidenceOpen = ref(false)
const pageKey = computed(() => String(route.meta.pageKey ?? ''))
const departmentOnly = computed(() => pageKey.value === 'standard_library_department')
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pages = computed(() => modules.find((m) => m.key === 'quality')?.pages ?? [])

const AUTH_KINDS = ['一单一库+CNAS+CMA', '非一单一库+CNAS+CMA', 'CNAS资质授权', '检验', '检测']
const DATASET_OPTIONS = [
  { label: '受控标准登记', value: 'controlled' },
  { label: '标准主数据', value: 'master' },
]
const datasetMode = ref<'controlled' | 'master'>('controlled')

const rows = ref<StdItem[]>([])
const selectedControlled = ref<StdItem>()
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const kw = ref('')
const deptFilter = ref('')
const authFilter = ref('')
const depts = ref<string[]>([])
const importInput = ref<HTMLInputElement>()
const fileBusy = ref(false)
const departmentAuthOpen = ref(false)
const departmentAuthSaving = ref(false)
const departmentAuthItem = ref<StdItem>()
const departmentAuthValues = ref<string[]>([])

function openDepartmentAuthorization(item: StdItem) {
  departmentAuthItem.value = item
  departmentAuthValues.value = [...(item.useDepts || [])]
  departmentAuthOpen.value = true
}

async function saveDepartmentAuthorization() {
  if (!departmentAuthItem.value) return
  departmentAuthSaving.value = true
  try {
    const updated = await updateStdDepartments(
      departmentAuthItem.value.id,
      departmentAuthValues.value,
    )
    const index = rows.value.findIndex((row) => row.id === updated.id)
    if (index >= 0) rows.value[index] = updated
    selectedControlled.value = updated
    departmentAuthOpen.value = false
    ElMessage.success('标准授权部门已保存')
  } catch (error) {
    ElMessage.error((error as Error).message || '标准部门授权保存失败')
  } finally {
    departmentAuthSaving.value = false
  }
}

async function downloadTemplate() {
  fileBusy.value = true
  try {
    await downloadStdLibraryTemplate()
  } catch (error) {
    ElMessage.error((error as Error).message || '模板下载失败')
  } finally {
    fileBusy.value = false
  }
}

function triggerImport() {
  importInput.value?.click()
}

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  fileBusy.value = true
  try {
    const result = await importStdLibrary(file)
    ElMessage.success(`标准信息上传完成：新增 ${result.created} 条，更新 ${result.updated} 条`)
    await reload(1)
  } catch (error) {
    ElMessage.error((error as Error).message || '标准信息上传失败')
  } finally {
    fileBusy.value = false
  }
}

async function downloadInformation() {
  fileBusy.value = true
  try {
    await exportStdLibrary({
      keyword: kw.value,
      dept: deptFilter.value,
      authKind: authFilter.value,
    })
  } catch (error) {
    ElMessage.error((error as Error).message || '标准信息下载失败')
  } finally {
    fileBusy.value = false
  }
}

const cnasOpen = ref(false)
const cnasBatches = ref<CnasBatch[]>([])
const cnasBatchId = ref<number>()
const cnasEntries = ref<CnasMappingEntry[]>([])
const cnasDepartments = ref<{ id: number; name: string }[]>([])
const cnasDepartmentIds = ref<Record<number, number[]>>({})
const cnasKeyword = ref('')
const cnasPendingOnly = ref(true)
const cnasPage = ref(1)
const cnasSize = ref(50)
const cnasTotal = ref(0)
const cnasLoading = ref(false)
const cnasActivating = ref(false)
const selectedCnasBatch = computed(() => (
  cnasBatches.value.find((batch) => batch.id === cnasBatchId.value)
))
const canActivateCnas = computed(() => Boolean(
  selectedCnasBatch.value
  && selectedCnasBatch.value.anomalyCount === 0
  && selectedCnasBatch.value.pendingCount === 0
  && selectedCnasBatch.value.attachmentCount === 42
  && selectedCnasBatch.value.chinesePageCount === 791,
))

async function openCnasDialog() {
  cnasOpen.value = true
  cnasLoading.value = true
  try {
    const [batches, catalog] = await Promise.all([listCnasBatches(), getCatalog()])
    cnasBatches.value = batches
    cnasDepartments.value = catalog.departments
    cnasBatchId.value = batches.find((batch) => batch.status === 'review')?.id
      || batches[0]?.id
    await reloadCnasEntries(1)
  } catch (error) {
    ElMessage.error((error as Error).message || 'CNAS 能力批次加载失败')
  } finally {
    cnasLoading.value = false
  }
}

const beginCnasSearch = useSearchRequest(() => [cnasBatchId.value, cnasKeyword.value, cnasPendingOnly.value, cnasPage.value, cnasSize.value])
async function reloadCnasEntries(toPage?: number) {
  if (!cnasBatchId.value) {
    cnasEntries.value = []
    cnasTotal.value = 0
    return
  }
  if (toPage) cnasPage.value = toPage
  const current = beginCnasSearch()
  cnasLoading.value = true
  try {
    const data = await listCnasEntries(cnasBatchId.value, {
      keyword: cnasKeyword.value,
      mappingStatus: cnasPendingOnly.value ? 'pending' : '',
      page: cnasPage.value,
      size: cnasSize.value,
    })
    if (!current()) return
    cnasEntries.value = data.rows
    cnasTotal.value = data.total
    const idByName = new Map(cnasDepartments.value.map((department) => [department.name, department.id]))
    cnasDepartmentIds.value = Object.fromEntries(data.rows.map((entry) => [
      entry.id,
      entry.departments.map((name) => idByName.get(name)).filter((id): id is number => Boolean(id)),
    ]))
  } catch (error) {
    if (current()) ElMessage.error((error as Error).message || '能力记录加载失败')
  } finally {
    if (current()) cnasLoading.value = false
  }
}

async function saveCnasMapping(entry: CnasMappingEntry) {
  try {
    await updateCnasEntryDepartments(entry.id, cnasDepartmentIds.value[entry.id] || [])
    ElMessage.success('部门映射已保存')
    cnasBatches.value = await listCnasBatches()
    await reloadCnasEntries()
  } catch (error) {
    ElMessage.error((error as Error).message || '部门映射保存失败')
  }
}

async function activateSelectedCnas() {
  if (!cnasBatchId.value || !canActivateCnas.value) return
  try {
    await ElMessageBox.confirm(
      '激活后，新样品登记将立即按本批次筛选标准和能力项目。确认继续？',
      '激活 CNAS 能力批次',
      { type: 'warning', confirmButtonText: '确认激活' },
    )
    cnasActivating.value = true
    await activateCnasBatch(cnasBatchId.value)
    cnasBatches.value = await listCnasBatches()
    ElMessage.success('CNAS 能力批次已激活')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error((error as Error).message || '能力批次激活失败')
  } finally {
    cnasActivating.value = false
  }
}

const beginListSearch = useSearchRequest(() => [kw.value, deptFilter.value, authFilter.value, page.value, size.value, departmentOnly.value])
async function reload(toPage?: number) {
  if (toPage) page.value = toPage
  if (departmentOnly.value) deptFilter.value = session.dataScope.department || ''
  const current = beginListSearch()
  selectedControlled.value = undefined
  loading.value = true
  try {
    if (departmentOnly.value) {
      datasetMode.value = 'controlled'
      deptFilter.value = session.dataScope.department || ''
    }
    const d = await fetchStdLibrary({
      keyword: kw.value,
      dept: deptFilter.value,
      authKind: authFilter.value,
      page: page.value,
      size: size.value,
      scope: departmentOnly.value ? 'department' : undefined,
    })
    if (!current()) return
    rows.value = d.rows
    total.value = d.total
  } catch (e) {
    if (current()) ElMessage.error((e as Error).message || '加载失败')
  } finally {
    if (current()) loading.value = false
  }
}
function resetFilter() {
  kw.value = ''
  deptFilter.value = departmentOnly.value ? (session.dataScope.department || '') : ''
  authFilter.value = ''
  reload(1)
}

const masterRows = ref<StandardMasterItem[]>([])
const masterTotal = ref(0)
const masterPage = ref(1)
const masterLoading = ref(false)
const masterKw = ref('')
const masterCategory = ref('')
const beginMasterSearch = useSearchRequest(() => [masterKw.value, masterCategory.value, masterPage.value, size.value])
async function reloadMaster(toPage?: number) {
  if (toPage) masterPage.value = toPage
  const current = beginMasterSearch()
  masterLoading.value = true
  try {
    const d = await fetchStandards({
      keyword: masterKw.value,
      category: masterCategory.value,
      page: masterPage.value,
      size: size.value,
    })
    if (!current()) return
    masterRows.value = d.rows
    masterTotal.value = d.total
  } catch (e) {
    if (current()) ElMessage.error((e as Error).message || '标准主数据加载失败')
  } finally {
    if (current()) masterLoading.value = false
  }
}
function resetMasterFilter() {
  masterKw.value = ''
  masterCategory.value = ''
  reloadMaster(1)
}
function onDatasetChange() {
  if (datasetMode.value === 'master') reloadMaster(1)
}

const editOpen = ref(false)
const saving = ref(false)
const controlledRemoving = ref(false)
const controlledReadOnly = ref(false)
const form = ref<StdItem | null>(null)
const canSave = computed(() => form.value?.id
  ? session.canAction('quality.standard.update')
  : session.canAction('quality.standard.create'))
function emptyStandard(): StdItem {
  return {
    id: 0, controlledNo: '', code: '', name: '', parameters: '', authKind: '', outOfScope: false,
    category: '', location: '', issueCount: '', issuer: '', useDepts: [], implDate: '',
    voidDate: '', delayDays: '', replaceNo: '', isEnglish: false, isOnsiteStandard: false, remark: '', status: '现行',
  }
}
function openCreate() {
  controlledReadOnly.value = false
  form.value = emptyStandard()
  editOpen.value = true
}
async function openEdit(row: StdItem) {
  controlledReadOnly.value = false
  form.value = { ...row, useDepts: [...(row.useDepts || [])] }
  editOpen.value = true
}
function openView(row: StdItem) {
  controlledReadOnly.value = true
  form.value = { ...row, useDepts: [...(row.useDepts || [])] }
  editOpen.value = true
}
async function save() {
  if (!form.value) return
  if (!form.value.code.trim() || !form.value.name.trim()) return ElMessage.warning('请填写标准编号和标准名称')
  saving.value = true
  try {
    const payload: Partial<StdItem> = { ...form.value }
    if (!session.canAction('quality.standard.authorize')) delete payload.useDepts
    const updated = form.value.id ? await updateStd(form.value.id, payload) : await createStd(payload)
    if(updated.identityImpactCount)ElMessage.warning(`同编号新增后有 ${updated.identityImpactCount} 份在途报告待确认，请选中标准使用“在途单标准关联”，或在各报告校核中确认。`)
    const i = rows.value.findIndex((r) => r.id === updated.id)
    if (i >= 0) rows.value[i] = updated
    else rows.value.unshift(updated)
    ElMessage.success('已保存')
    editOpen.value = false
    await reload(1)
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}
async function voidCurrent() {
  if (!form.value?.id) return
  if (!form.value.voidDate) return ElMessage.warning('请先填写作废日期')
  try {
    const result = await ElMessageBox.prompt('请输入作废原因；替代标准号可在表单中填写。', '作废受控标准', {
      type: 'warning', confirmButtonText: '确认作废', cancelButtonText: '取消',
      inputPattern: /\S+/, inputErrorMessage: '作废原因不能为空',
    })
    form.value = await voidStd(form.value.id, {
      voidDate: form.value.voidDate, replaceNo: form.value.replaceNo, reason: result.value,
    })
    ElMessage.success('标准已作废')
    editOpen.value = false
    await reload(1)
  } catch (error) {
    if (error instanceof Error && error.message) ElMessage.error(error.message)
  }
}

async function confirmRemoveControlled(item: StdItem) {
  try {
    await ElMessageBox.confirm(
      `确认移除受控标准“${item.controlledNo || '无受控号'} / ${item.code} ${item.name}”？该操作不影响已有委托、样品和报告记录。`,
      '移除受控标准',
      { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  controlledRemoving.value = true
  try {
    await removeStd(item.id)
    ElMessage.success('受控标准已移除')
    if (form.value?.id === item.id) editOpen.value = false
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    await reload()
  } catch (e) {
    ElMessage.error((e as Error).message || '移除失败')
  } finally {
    controlledRemoving.value = false
  }
}

const masterEditOpen = ref(false)
const masterSaving = ref(false)
const masterRemoving = ref(false)
const masterForm = ref<StandardMasterItem | null>(null)
const canSaveMaster = computed(() => masterForm.value?.id
  ? session.canAction('quality.master_standard.update')
  : session.canAction('quality.master_standard.create'))
function emptyMaster(): StandardMasterItem {
  return {
    id: 0,
    code: '',
    name: '',
    category: '',
    authKind: '',
    department: '',
    status: '现行',
    expired: false,
  }
}
function openMasterCreate() {
  masterForm.value = emptyMaster()
  masterEditOpen.value = true
}
async function openMasterEdit(row: StandardMasterItem) {
  masterForm.value = { ...row }
  masterEditOpen.value = true
}
async function saveMaster() {
  if (!masterForm.value) return
  if (!masterForm.value.code.trim() || !masterForm.value.name.trim()) {
    return ElMessage.warning('请填写标准编号和标准名称')
  }
  masterSaving.value = true
  try {
    if (masterForm.value.id) await updateStandard(masterForm.value.id, masterForm.value)
    else await createStandard(masterForm.value)
    ElMessage.success('标准主数据已保存')
    masterEditOpen.value = false
    await reloadMaster(masterForm.value.id ? masterPage.value : 1)
  } catch (e) {
    ElMessage.error((e as Error).message || '保存失败')
  } finally {
    masterSaving.value = false
  }
}
async function confirmRemoveMaster(item: StandardMasterItem) {
  try {
    await ElMessageBox.confirm(
      `确认从标准主数据中移除“${item.code} ${item.name}”？该操作表示停用目录项，不影响已有委托、样品和报告记录。`,
      '移除标准主数据',
      { type: 'warning', confirmButtonText: '确认移除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  masterRemoving.value = true
  try {
    await removeStandard(item.id)
    ElMessage.success('标准主数据已移除')
    if (masterForm.value?.id === item.id) masterEditOpen.value = false
    if (masterRows.value.length === 1 && masterPage.value > 1) masterPage.value -= 1
    await reloadMaster()
  } catch (e) {
    ElMessage.error((e as Error).message || '移除失败')
  } finally {
    masterRemoving.value = false
  }
}
function masterStatusType(row: StandardMasterItem) {
  if (row.expired || row.status === '作废') return 'danger'
  if (row.status === '被替代') return 'warning'
  return 'success'
}
function statusType(status: string) {
  if (status === '现行') return 'success'
  if (status === '待实施') return 'warning'
  return 'danger'
}

onMounted(async () => {
  const departmentsReady = fetchQualityDepts().then(value => { depts.value = value }).catch(() => { depts.value = [] })
  if (departmentOnly.value) deptFilter.value = session.dataScope.department || ''
  await reload(1)
  await departmentsReady
})
watch(departmentOnly, () => {
  datasetMode.value = 'controlled'
  resetFilter()
})
useLiveSearch(kw, () => reload(1))
useLiveSearch(() => [masterKw.value, masterCategory.value], () => reloadMaster(1))
useLiveSearch(cnasKeyword, () => reloadCnasEntries(1), () => Boolean(cnasBatchId.value))

// BEGIN TEMPLATE STANDARDS ADAPTER
const parameterOpen = ref(false)
const parameterStandard = ref<StdItem>()
function openParameters(row: StdItem) { parameterStandard.value = row; parameterOpen.value = true }
const masterViewOnly=ref(false)
const standardFormSchema=computed(()=>standardSchema({depts:depts.value,canAuthorize:session.canAction('quality.standard.authorize')}))
const standardMasterSchema=masterStandardSchema()
const standardsPresentation=createStandardsPresentation(reactive({pageName,departmentOnly,session,datasetMode,rows,total,page,size,loading,kw,deptFilter,authFilter,depts,AUTH_KINDS,fileBusy,selectedControlled,masterRows,masterTotal,masterPage,masterLoading,masterKw,masterCategory,masterViewOnly,reload,reloadMaster,openCreate,openEdit,openView,confirmRemoveControlled,openMasterCreate,openMasterEdit,confirmRemoveMaster,openDepartmentAuthorization,downloadTemplate,triggerImport,downloadInformation,openCnasDialog,scopeEvidenceOpen,onDatasetChange,openParameters}))
// END TEMPLATE STANDARDS ADAPTER
</script>


