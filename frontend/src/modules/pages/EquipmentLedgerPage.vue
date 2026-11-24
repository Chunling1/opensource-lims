<template>
  <EquipmentPresentation :context="equipmentPresentation" />
  <input ref="importInput" type="file" accept=".xlsx" class="d-none" @change="handleImport" />

  <el-dialog
    v-model="detailOpen"
    :title="form?.id ? `${viewOnly ? '查看' : '修改'}设备 · ${form.archiveNo || ''}` : '新增仪器设备'"
    width="1040px"
    top="4vh"
    
  >
    <el-tabs v-model="tab" v-if="form" v-loading="detailLoading">
      <el-tab-pane label="设备全部信息" name="basic">
        <el-alert
          v-if="form.status === '限制使用'"
          type="warning"
          :closable="false"
          show-icon
          title="校准有效期至缺失或已过期，系统已自动限制使用；更新本次校准日期后会按周期推算。"
          
        />
        <div v-if="form.id && !viewOnly" class="mb-3">
          <label for="calibration-maintenance-mode" class="form-label">校准维护方式</label>
          <select id="calibration-maintenance-mode" v-model="form.calibrationMode" class="form-select" aria-describedby="calibration-maintenance-help">
            <option value="correction">纠正本期信息（不新增有效期）</option>
            <option value="renewal">新增一次校准（保留上一期）</option>
          </select>
          <p id="calibration-maintenance-help" class="form-text">新增校准前请核对原有效期，填写本次实际校准日期、有效期至和证书编号，并确认符合使用要求。检测按历次有效期连续覆盖判断，空档不能使用。</p>
        </div>
        <el-alert v-if="!viewOnly" type="warning" :closable="false" show-icon title="提示：换新证请选【新增一次校准】（系统自动保留上一期有效期）；若需让更早日期的历史试验通过校验，请使用【校准日期维护记录】中的【补录历史校准】，请勿将本次校准日期改回往年。" />
        <SchemaForm :model="form" :schema="equipmentFormSchema" :readonly="viewOnly" />
      </el-tab-pane>
      <el-tab-pane label="出具报告/项目" name="project">
        <div v-if="history.projects.length" class="d-flex flex-wrap gap-2">
          <el-tag v-for="project in history.projects" :key="project" effect="plain">{{ project }}</el-tag>
        </div>
        <el-empty v-else description="暂无关联报告项目" />
      </el-tab-pane>
      <el-tab-pane label="校准日期维护记录" name="cal">
        <CalibrationHistoryForm v-if="form.id && !viewOnly && canEquipmentUpdate" :key="form.id" :equipment-id="form.id" @saved="reloadCalibrationHistory" />
        <p>可用于日期校验的校准有效期（含当前台账）：</p>
        <ul><li v-for="(period, index) in history.validPeriods || []" :key="index">{{ period.start }} 至 {{ period.end }}；证书：{{ period.certificateNo || '未登记' }}</li></ul>
        <p class="form-text">下面保留所有维护记录；旧版未区分用途的修改记录不自动作为有效期放行。日期纠错只替换本期，不保留错误区间。</p>
        <el-table :data="history.calibration" border max-height="470">
          <el-table-column prop="changedAt" label="维护时间" width="170" />
          <el-table-column label="维护人" width="150">
            <template #default="{ row }">{{ row.changedByName || row.changedByAccount || '—' }}</template>
          </el-table-column>
          <el-table-column label="维护方式" width="110">
            <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
          </el-table-column>
          <el-table-column label="变更内容" min-width="420">
            <template #default="{ row }">
              <div v-for="key in row.changedFields" :key="key" >
                {{ fieldLabel(key) }}：{{ row.before[key] || '—' }} → {{ row.after[key] || '—' }}
              </div>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!history.calibration.length" description="暂无校准维护记录" />
      </el-tab-pane>
      <el-tab-pane label="设备使用记录" name="use">
        <el-table :data="history.usage" border max-height="470">
          <el-table-column prop="usedFrom" label="开始日期" width="112" />
          <el-table-column prop="usedTo" label="结束日期" width="112" />
          <el-table-column prop="reportNo" label="报告编号" min-width="155" />
          <el-table-column prop="sampleNo" label="样品编号" min-width="145" />
          <el-table-column prop="project" label="报告项目" min-width="180" show-overflow-tooltip />
          <el-table-column label="使用人" width="130">
            <template #default="{ row }">{{ row.usedByName || row.usedByAccount || '—' }}</template>
          </el-table-column>
          <el-table-column prop="statusAtUse" label="使用时状态" width="110" />
        </el-table>
        <el-empty v-if="!history.usage.length" description="暂无设备使用记录" />
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <el-button @click="detailOpen = false">{{ viewOnly ? '关闭' : '取消' }}</el-button>
      <el-button v-if="!viewOnly" type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="batchOpen" title="批量修改仪器设备" width="720px">
    <el-alert type="info" :closable="false" show-icon :title="`已选择 ${selected.length} 台设备；只修改已勾选字段，其他信息保持不变。`" />
    <label for="batch-calibration-mode" class="form-label">校准维护方式</label>
    <select id="batch-calibration-mode" v-model="batchMode" class="form-select mb-3">
      <option value="correction">纠正本期信息（不新增有效期）</option>
      <option value="renewal">新增一次校准（保留各仪器上一期）</option>
    </select>
    <p class="form-text">新增校准须核对各仪器原有效期，填写本次实际校准日期和证书编号，并确认符合使用要求；任一仪器校验失败整批不保存。</p>
    <SchemaForm :model="batchForm" :schema="equipmentBatchSchema" />
    <template #footer>
      <el-button @click="batchOpen = false">取消</el-button>
      <el-button type="primary" :loading="batchSaving" @click="saveBatch">确认批量修改</el-button>
    </template>
  </el-dialog>
  <el-dialog v-model="importPreviewOpen" title="仪器导入差异预览" width="900px">
    <template v-if="importPreview">
      <p>将新增 {{ importPreview.createdCount }} 台、修改 {{ importPreview.updatedCount }} 台、跳过未改动 {{ importPreview.unchangedCount }} 台</p>
      <p>普通空白格保留原值；“/”或“[清空]”才会清空。</p>
      <div v-for="change in importPreview.changes" :key="change.id || change.archiveNo">
        <strong>{{ change.archiveNo }} · {{ change.name }}（ID：{{ change.id || '新增' }}）</strong>
        <ul><li v-for="(delta, field) in change.fields" :key="field">
          {{ fieldLabel(String(field)) }}：{{ delta.before || '空' }} → {{ delta.after || '空' }}
          <el-tag v-if="change.clearingFields.includes(String(field))" type="warning">将清空</el-tag>
        </li></ul>
      </div>
    </template>
    <template #footer><el-button @click="importPreviewOpen = false">取消</el-button><el-button type="primary" :loading="importing" @click="confirmImport">确认导入</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
// BEGIN TEMPLATE EQUIPMENT IMPORTS
import EquipmentPresentation from '../../platformUi/quality/EquipmentPresentation.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import {createEquipmentPresentation,equipmentSchema,equipmentBatchForm} from '../../platformUi/quality/equipmentPresentation'
// END TEMPLATE EQUIPMENT IMPORTS
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import CalibrationHistoryForm from '../../platformUi/quality/CalibrationHistoryForm.vue'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import { useSessionStore } from '@/stores/session'
import {
  batchDeleteEquipment,
  batchUpdateEquipment,
  createEquipment,
  downloadEquipmentTemplate,
  exportEquipment,
  fetchEquipment,
  fetchEquipmentDetail,
  fetchEquipmentHistory,
  fetchQualityDepts,
  importEquipment,
  removeEquipment,
  updateEquipment,
  type EquipItem,
  type EquipmentHistory,
} from '@/services/quality'

const route = useRoute()
const session = useSessionStore()
const isSystemAdmin = computed(() => (session.fullPlatformAuthority || session.roleKey === 'admin'))
const canEquipmentCreate = computed(() => (
  isSystemAdmin.value || session.canAction('quality.equipment.create')
))
const canEquipmentUpdate = computed(() => (
  isSystemAdmin.value || session.canAction('quality.equipment.update')
))
const canEquipmentDelete = computed(() => (
  isSystemAdmin.value || session.canAction('quality.equipment.delete')
))
const canEquipmentBatchUpdate = computed(() => (
  isSystemAdmin.value
  || session.canAction('quality.equipment.batch_update')
  || session.canAction('quality.equipment.update')
))
const canEquipmentBatchDelete = computed(() => (
  isSystemAdmin.value
  || session.canAction('quality.equipment.batch_delete')
  || session.canAction('quality.equipment.delete')
))
const canEquipmentImport = computed(() => (
  isSystemAdmin.value
  || session.canAction('quality.equipment.import')
  || session.canAction('quality.equipment.update')
))
const canEquipmentExport = computed(() => (
  isSystemAdmin.value
  || session.canAction('quality.equipment.export')
  || session.canAction('quality.equipment.update')
))
const pageKey = computed(() => String(route.meta.pageKey ?? ''))
const departmentOnly = computed(() => pageKey.value === 'equipment_ledger_department')
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pages = computed(() => modules.find((m) => m.key === 'quality')?.pages ?? [])
const STATUSES = ['可用', '限制使用', '停用/报废']
const EMPTY_HISTORY: EquipmentHistory = { usage: [], calibration: [], reports: [], projects: [] }

function statusTag(status: string) {
  if (status === '可用') return 'success'
  if (status === '限制使用') return 'warning'
  if (status === '停用/报废') return 'danger'
  return 'info'
}
function equipmentRowClass({ row }: { row: EquipItem }) {
  if (row.status === '限制使用') return 'equipment-row-limited'
  if (row.status === '停用/报废') return 'equipment-row-stopped'
  return ''
}

const rows = ref<EquipItem[]>([])
const selected = ref<EquipItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const kw = ref('')
const deptFilter = ref('')
const statusFilter = ref('')
const depts = ref<string[]>([])

const beginListSearch = useSearchRequest(() => [kw.value, deptFilter.value, statusFilter.value, page.value, size.value, departmentOnly.value])
async function reload(toPage?: number) {
  if (toPage) page.value = toPage
  if (departmentOnly.value) deptFilter.value = session.dataScope.department || ''
  const current = beginListSearch()
  loading.value = true
  try {
    const data = await fetchEquipment({
      keyword: kw.value,
      dept: deptFilter.value,
      status: statusFilter.value,
      page: page.value,
      size: size.value,
      scope: departmentOnly.value ? 'department' : undefined,
    })
    if (!current()) return
    rows.value = data.rows
    total.value = data.total
    selected.value = []
  } catch (error) {
    if (current()) ElMessage.error((error as Error).message || '加载设备台账失败')
  } finally {
    if (current()) loading.value = false
  }
}
function resetFilter() {
  kw.value = ''
  deptFilter.value = departmentOnly.value ? (session.dataScope.department || '') : ''
  statusFilter.value = ''
  void reload(1)
}

const detailOpen = ref(false)
const detailLoading = ref(false)
const saving = ref(false)
const viewOnly = ref(false)
const tab = ref('basic')
const form = ref<EquipItem | null>(null)
const initialSnapshot = ref<EquipItem | null>(null)
const history = ref<EquipmentHistory>({ ...EMPTY_HISTORY })

async function reloadCalibrationHistory() {
  if (!form.value?.id) return
  try { history.value = await fetchEquipmentHistory(form.value.id, departmentOnly.value ? 'department' : undefined) }
  catch { ElMessage.warning('补录已保存，记录列表刷新失败，请重新打开设备查看。') }
}

function normalizeDateText(value?: string) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  let compact = raw.replace(/[年月/.]/g, '-').replace(/日/g, '').replace(/^-+|-+$/g, '')
  if (/^\d{8}$/.test(compact)) {
    compact = `${compact.slice(0, 4)}-${compact.slice(4, 6)}-${compact.slice(6)}`
  }
  const match = compact.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const parsed = new Date(year, month - 1, day)
  if (
    parsed.getFullYear() !== year
    || parsed.getMonth() !== month - 1
    || parsed.getDate() !== day
  ) return null
  return `${year.toString().padStart(4, '0')}-${month.toString().padStart(2, '0')}-${day.toString().padStart(2, '0')}`
}

function calibrationPeriodMonths(value?: string) {
  const text = String(value || '').trim().toLowerCase().replace(/\s/g, '')
  if (!text || ['长期', '永久', '不定期'].some((token) => text.includes(token))) return null
  if (text === '半年') return 6
  if (/^\d+(\.\d+)?$/.test(text)) return Math.max(1, Math.round(Number(text) * 12))
  const yearMatch = text.match(/(\d+(?:\.\d+)?)年/)
  const monthMatch = text.match(/(\d+)个?月/)
  if (!yearMatch && !monthMatch) return null
  return Math.max(
    1,
    Math.round(Number(yearMatch?.[1] || 0) * 12) + Number(monthMatch?.[1] || 0),
  )
}

function addMonths(dateText: string, months: number) {
  const [year, month, day] = dateText.split('-').map(Number)
  const targetMonth = month - 1 + months
  const targetYear = year + Math.floor(targetMonth / 12)
  const normalizedMonth = ((targetMonth % 12) + 12) % 12
  const lastDay = new Date(targetYear, normalizedMonth + 1, 0).getDate()
  const target = new Date(targetYear, normalizedMonth, Math.min(day, lastDay))
  target.setDate(target.getDate() - 1)
  return `${target.getFullYear().toString().padStart(4, '0')}-${(target.getMonth() + 1).toString().padStart(2, '0')}-${target.getDate().toString().padStart(2, '0')}`
}

function refreshStatusPreview() {
  if (!form.value) return
  if (form.value.manualStatus === '停用/报废') {
    form.value.status = '停用/报废'
    return
  }
  if (String(form.value.period || '').trim() === '长期') {
    form.value.status = '可用'
    return
  }
  const nextDate = normalizeDateText(form.value.planCalDate)
  const today = new Date()
  const todayText = `${today.getFullYear().toString().padStart(4, '0')}-${(today.getMonth() + 1).toString().padStart(2, '0')}-${today.getDate().toString().padStart(2, '0')}`
  form.value.status = nextDate && nextDate >= todayText ? '可用' : '限制使用'
}

function recalculateNextDate() {
  if (!form.value) return
  const planDate = normalizeDateText(form.value.actualCalDate)
  const months = calibrationPeriodMonths(form.value.period)
  if (planDate) form.value.lastCalDate = planDate
  if (planDate && months) form.value.planCalDate = addMonths(planDate, months)
  refreshStatusPreview()
}

function normalizeNextDate() {
  if (!form.value) return
  const normalized = normalizeDateText(form.value.planCalDate)
  if (normalized === null) {
    ElMessage.warning('校准有效期至格式无效，请输入如 2027-03-04')
    return
  }
  form.value.planCalDate = normalized
  refreshStatusPreview()
}

function blankEquipment(): EquipItem {
  return {
    id: 0,
    archiveNo: '',
    name: '',
    spec: '',
    dept: '',
    status: '限制使用',
    manualStatus: '可用',
    keeper: '',
    lastCalDate: '',
    planCalDate: '',
    certificateNo: '',
    calibrationMode: 'correction',
  }
}
function openCreate() {
  tab.value = 'basic'
  viewOnly.value = false
  form.value = blankEquipment()
  history.value = { ...EMPTY_HISTORY }
  detailOpen.value = true
}
async function openDetail(row: EquipItem, readonly: boolean) {
  tab.value = 'basic'
  viewOnly.value = readonly
  form.value = { ...row }
  history.value = { ...EMPTY_HISTORY }
  detailOpen.value = true
  detailLoading.value = true
  try {
    const [detail, historyData] = await Promise.all([
      fetchEquipmentDetail(row.id, departmentOnly.value ? 'department' : undefined),
      fetchEquipmentHistory(row.id, departmentOnly.value ? 'department' : undefined),
    ])
    form.value = { ...detail, actualCalDate: detail.actualCalDate || detail.lastCalDate, planCalDate: detail.validUntil || detail.planCalDate, calibrationMode: 'correction' }
    initialSnapshot.value = { ...form.value }
    history.value = historyData
  } catch (error) {
    ElMessage.error((error as Error).message || '加载设备详情失败')
  } finally {
    detailLoading.value = false
  }
}
async function save() {
  if (!form.value) return
  if (!form.value.archiveNo.trim() || !form.value.name.trim()) {
    return ElMessage.warning('请填写档案号和仪器设备名称')
  }
  const nextDate = normalizeDateText(form.value.planCalDate)
  const actualDate = normalizeDateText(form.value.actualCalDate)
  if (nextDate === null || actualDate === null) {
    return ElMessage.warning('请检查本次校准日期和校准有效期至的格式')
  }
  form.value.planCalDate = nextDate
  form.value.actualCalDate = actualDate
  saving.value = true
  try {
    const payload = form.value.id ? Object.fromEntries(Object.entries(form.value).filter(([key, value]) => ['editVersion', 'archiveNo', 'name', 'calibrationMode'].includes(key) || value !== initialSnapshot.value?.[key as keyof EquipItem])) : form.value
    form.value = form.value.id ? await updateEquipment(form.value.id, payload) : await createEquipment(payload)
    initialSnapshot.value = { ...form.value }
    ElMessage.success('设备信息已保存')
    detailOpen.value = false
    await reload(form.value.id ? page.value : 1)
  } catch (error) {
    ElMessage.error((error as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}
async function confirmRemove(item: EquipItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除“${item.name || item.archiveNo}”？历史报告和使用记录会保留。`,
      '删除设备',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    )
    await removeEquipment(item.id)
    ElMessage.success('设备已从有效台账中删除')
    await reload()
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message)
  }
}

const batchOpen = ref(false)
const batchSaving = ref(false)
const batchMode = ref<'correction' | 'renewal'>('correction')
const batchForm = reactive<Partial<EquipItem>>({})
const batchEnabled = reactive<Record<string, boolean>>({
  dept: false,
  keeper: false,
  manualStatus: false,
  actualCalDate: false,
  certificateNo: false,
  planCalDate: false,
  period: false,
  calUnit: false,
  place: false,
})
function openBatch() {
  batchMode.value = 'correction'
  Object.keys(batchEnabled).forEach((key) => { batchEnabled[key] = false })
  Object.keys(batchForm).forEach((key) => { delete (batchForm as Record<string, unknown>)[key] })
  batchForm.manualStatus = '可用'
  batchOpen.value = true
}
async function saveBatch() {
  const changes: Partial<EquipItem> = {}
  Object.entries(batchEnabled).forEach(([key, enabled]) => {
    if (enabled) (changes as Record<string, unknown>)[key] = (batchForm as Record<string, unknown>)[key] ?? ''
  })
  if (!Object.keys(changes).length) return ElMessage.warning('请至少勾选一个要修改的字段')
  for (const key of ['actualCalDate', 'lastCalDate', 'planCalDate'] as const) {
    if (!batchEnabled[key]) continue
    const normalized = normalizeDateText(batchForm[key])
    if (normalized === null) return ElMessage.warning(`${fieldLabel(key)}格式无效`)
    changes[key] = normalized
  }
  batchSaving.value = true
  try {
    await batchUpdateEquipment(selected.value.map((row) => row.id), changes, batchMode.value)
    ElMessage.success(`已批量修改 ${selected.value.length} 台设备`)
    batchOpen.value = false
    await reload()
  } catch (error) {
    ElMessage.error((error as Error).message || '批量修改失败')
  } finally {
    batchSaving.value = false
  }
}
async function confirmBatchDelete() {
  try {
    await ElMessageBox.confirm(
      `确认批量删除已选择的 ${selected.value.length} 台设备？历史报告和使用记录会保留。`,
      '批量删除设备',
      { type: 'warning', confirmButtonText: '确认批量删除', cancelButtonText: '取消' },
    )
    await batchDeleteEquipment(selected.value.map((row) => row.id))
    ElMessage.success('批量删除完成')
    await reload()
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message)
  }
}

const importInput = ref<HTMLInputElement>()
const importing = ref(false)
const importPreviewOpen = ref(false)
const importFile = ref<File>()
const importPreview = ref<Awaited<ReturnType<typeof importEquipment>>>()
async function confirmImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const result = await importEquipment(importFile.value)
    ElMessage.success(`导入完成：新增 ${result.createdCount} 台，修改 ${result.updatedCount} 台，跳过 ${result.unchangedCount} 台`)
    importPreviewOpen.value = false
    await reload(1)
  } catch (error) {
    ElMessage.error((error as Error).message || '导入失败')
  } finally { importing.value = false }
}
const exporting = ref(false)
function triggerImport() {
  importInput.value?.click()
}
async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    importPreview.value = await importEquipment(file, true)
    importFile.value = file
    importPreviewOpen.value = true
  } catch (error) {
    ElMessage.error((error as Error).message || '导入失败')
  } finally {
    importing.value = false
    input.value = ''
  }
}
async function downloadTemplate() {
  try {
    await downloadEquipmentTemplate()
  } catch (error) {
    ElMessage.error((error as Error).message || '模板下载失败')
  }
}
async function exportRows(ids?: number[]) {
  exporting.value = true
  try {
    await exportEquipment({
      keyword: kw.value,
      dept: deptFilter.value,
      status: statusFilter.value,
      ...(ids ? { ids: ids.join(',') } : {}),
    })
  } catch (error) {
    ElMessage.error((error as Error).message || '导出失败')
  } finally {
    exporting.value = false
  }
}

const FIELD_LABELS: Record<string, string> = {
  historicalStart: '历史校准开始日期', historicalEnd: '历史校准有效期至', historicalCertificateNo: '历史证书编号', backfillReason: '补录依据',
  actualCalDate: '本次校准日期',
  lastCalDate: '本次校准日期',
  planCalDate: '校准有效期至',
  validUntil: '有效期',
  period: '校准周期',
  calUnit: '检定/校准单位',
  certificateNo: '证书编号',
}
function fieldLabel(key: string) {
  return FIELD_LABELS[key] || key
}
function sourceLabel(source: string) {
  return {
    historical_backfill: '历史补录',
    create: '新增',
    single_update: '单条修改',
    batch_update: '批量修改',
    import: '导入',
  }[source] || source
}

const tableHeight = ref(560)
const ROW_H = 41
function calcLayout() {
  const element = document.querySelector('[data-ui~=fill-card] table') as HTMLElement | null
  const top = element ? element.getBoundingClientRect().top : 260
  const height = Math.max(280, Math.floor(window.innerHeight - top - 58))
  tableHeight.value = height
  const newSize = size.value // Template pagination owns page size; resize must not reset it.
  if (newSize !== size.value) {
    size.value = newSize
    void reload(1)
  }
}
onMounted(async () => {
  if (departmentOnly.value) {
    deptFilter.value = session.dataScope.department || ''
    depts.value = deptFilter.value ? [deptFilter.value] : []
  } else {
    depts.value = await fetchQualityDepts().catch(() => [])
  }
  await reload(1)
  await nextTick()
  calcLayout()
  window.addEventListener('resize', calcLayout)
})
onUnmounted(() => window.removeEventListener('resize', calcLayout))
useLiveSearch(kw, () => reload(1))

// BEGIN TEMPLATE EQUIPMENT ADAPTER
const equipmentPresentation=createEquipmentPresentation(reactive({pageName,departmentOnly,session,rows,total,page,size,loading,kw,deptFilter,statusFilter,depts,selected,importing,exporting,canEquipmentCreate,canEquipmentUpdate,canEquipmentDelete,canEquipmentImport,canEquipmentExport,canEquipmentBatchUpdate,canEquipmentBatchDelete,openCreate,openDetail,confirmRemove,openBatch,confirmBatchDelete,triggerImport,downloadTemplate,exportRows,reload}))
const equipmentFormSchema=computed(()=>equipmentSchema({depts:depts.value,refreshStatusPreview,recalculateNextDate,normalizeNextDate}))
const equipmentBatchSchema=computed(()=>equipmentBatchForm({depts:depts.value,batchEnabled}))
// END TEMPLATE EQUIPMENT ADAPTER
</script>


