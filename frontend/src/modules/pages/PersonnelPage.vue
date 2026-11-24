<template>
  <PersonnelPresentation :context="personnelPresentation" />
  <EsignBindingRoster v-model="bindingRosterOpen" />

  <BootstrapModal :open="editOpen" :title="form?.id ? `人员调整 · ${form.name || ''}` : '新建人员'" size="xl" scrollable :busy="saving || removing" @close="editOpen = false">
    <SchemaForm v-if="form" :model="form" :schema="personnelFormSchema" :readonly="personnelReadOnly" />
    <SchemaForm v-if="form && form.linkedUserId && canManageEsign" :model="personnelEsignModel" :schema="personnelEsignSchema" :readonly="personnelReadOnly">
      <template #binding><RosterBindingButton v-if="esignBinding?.status === 'unbound'" :user-id="form.linkedUserId" :disabled="personnelReadOnly || session.businessReadOnly" @bound="refreshRosterBinding" /></template>
    </SchemaForm>

    <template #footer>
      <el-button @click="editOpen = false">取消</el-button>
      <el-button v-if="!personnelReadOnly && form?.id && session.canAction('quality.personnel.delete')" type="danger" plain :loading="removing" @click="confirmRemove(form)">移出人员名册</el-button>
      <el-button v-if="form?.id ? session.canAction('quality.personnel.update') : session.canAction('quality.personnel.create')" type="primary" :loading="saving" :disabled="personnelReadOnly" @click="save">保存</el-button>
    </template>
  </BootstrapModal>

  <el-dialog v-model="importOpen" title="人员登记导入预检" width="780px" :close-on-click-modal="false">
    <el-alert type="info" :closable="false" title="与列表使用相同7列表头（不含操作）。按人员编号更新，不删除表外人员；流程权限列仅为档案标签，正式功能和项目权限仍在组织机构维护。" />
    <el-upload :auto-upload="false" :show-file-list="false" accept=".xlsx" :disabled="importBusy" :on-change="selectImportFile">
      <el-button  :disabled="importBusy">选择xlsx文件</el-button>
    </el-upload>
    <p>{{ importFile?.name || '请使用本页导出文件或下载导入模板' }}</p>
    <div v-if="importPreview">
      <p>共 {{ importPreview.total }} 人；新增档案 {{ importPreview.createPersonnel }}，更新档案 {{ importPreview.updatePersonnel }}，新建账号 {{ importPreview.createAccounts }}，部门调整 {{ importPreview.departmentMoves }}。</p>
      <el-alert v-if="importPreview.valid" type="success" :closable="false" title="预检通过，尚未写入。请核对后点击确认导入。部门调整仍按现有部门上限收敛权限。" />
      <el-table v-else :data="importPreview.errors" max-height="300" border>
        <el-table-column prop="row" label="行号" width="70" />
        <el-table-column prop="code" label="人员编号/账号" width="160" />
        <el-table-column prop="message" label="校验问题" />
      </el-table>
    </div>
    <template #footer>
      <el-button :disabled="importBusy" @click="importOpen = false">取消</el-button>
      <el-button :disabled="!importFile || importBusy" @click="runImportPreview">重新预检</el-button>
      <el-button type="primary" :loading="importBusy" :disabled="!importPreview?.valid" @click="confirmImport">确认导入</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
// BEGIN TEMPLATE PERSONNEL IMPORTS
import {reactive} from 'vue'
import PersonnelPresentation from '../../platformUi/quality/PersonnelPresentation.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import {createPersonnelPresentation,personnelSchema,esignSchema} from '../../platformUi/quality/personnelPresentation'
// END TEMPLATE PERSONNEL IMPORTS
import { downloadInitialCredentials } from '@/services/loginSecurityUi'
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import { useSessionStore } from '@/stores/session'
import { getCatalog } from '@/services/admin'
import { fetchEsignBinding, saveEsignBinding, type EsignBinding } from '@/services/esign'
import RosterBindingButton from '@/components/RosterBindingButton.vue'
import EsignBindingRoster from '@/components/EsignBindingRoster.vue'
async function refreshRosterBinding() {
  if (form.value?.linkedUserId) esignBinding.value = await fetchEsignBinding(form.value.linkedUserId)
}
import {
  createPersonnel,
  fetchPermOptions,
  fetchPersonnel,
  fetchPersonnelDetail,
  fetchQualityDepts,
  removePersonnel,
  updatePersonnel,
  exportPersonnel,
  downloadPersonnelTemplate,
  previewPersonnelImport,
  importPersonnel,
  type PersonnelImportPreview,
  type PersonItem,
} from '@/services/quality'

const route = useRoute()
const session = useSessionStore()
const bindingRosterOpen = ref(false)
const pageKey = computed(() => String(route.meta.pageKey ?? ''))
const pageName = computed(() => String(route.meta.pageName ?? ''))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pages = computed(() => modules.find((m) => m.key === 'quality')?.pages ?? [])
const canManageAccounts = computed(() => session.can('system.user.view'))
const canImport = computed(() => canManageAccounts.value && session.canAction('quality.personnel.create') && session.canAction('quality.personnel.update'))
const canManageEsign = computed(() => session.roleKey === 'admin' || session.canAction('quality.personnel.update'))

const rows = ref<PersonItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const loading = ref(false)
const kw = ref('')
const deptFilter = ref('')
const deptOptions = ref<{ id: number | null; name: string }[]>([])
const permOptions = ref<string[]>([])

const beginListSearch = useSearchRequest(() => [kw.value, deptFilter.value, page.value, size.value])
async function reload(toPage?: number) {
  if (toPage) page.value = toPage
  const current = beginListSearch()
  loading.value = true
  try {
    const data = await fetchPersonnel({ keyword: kw.value, dept: deptFilter.value, page: page.value, size: size.value })
    if (!current()) return
    rows.value = data.rows
    total.value = data.total
  } catch (error) {
    if (current()) ElMessage.error(error instanceof Error ? error.message : '人员加载失败')
  } finally {
    if (current()) loading.value = false
  }
}
function resetFilter() {
  kw.value = ''
  deptFilter.value = ''
  void reload(1)
}

const editOpen = ref(false)
const saving = ref(false)
const removing = ref(false)
const form = ref<PersonItem | null>(null)
const esignBinding = ref<EsignBinding | null>(null)
const esignLegalName = ref('')
const esignAccountInput = ref('')
const esignBindingStatus = computed(() => ({
  verified: '已实名', pending: '待首次实名', disabled: '已停用', unbound: '未绑定',
} as Record<string, string>)[esignBinding.value?.status || 'unbound'])
function blank(): PersonItem {
  return {
    id: 0,
    name: '',
    code: '',
    dept: '',
    title: '',
    position: '',
    approvalPosition: '',
    roleName: '',
    departmentId: null,
    accountEnabled: true,
    assignedDepts: [],
    permissions: [],
  }
}
function syncDepartmentName(departmentId: number | null) {
  if (!form.value) return
  const department = deptOptions.value.find((item) => item.id === departmentId)
  if (department) {
    form.value.dept = department.name
    form.value.assignedDepts = [department.name]
  }
}
function openCreate() {
  form.value = blank()
  esignBinding.value = null
  esignLegalName.value = ''
  esignAccountInput.value = ''
  editOpen.value = true
}
async function openEdit(row: PersonItem) {
  esignBinding.value = null
  esignLegalName.value = ''
  esignAccountInput.value = ''
  form.value = { ...row, assignedDepts: [...(row.assignedDepts || [])], permissions: [...(row.permissions || [])] }
  editOpen.value = true
  try {
    const full = await fetchPersonnelDetail(row.id)
    form.value = { ...full, assignedDepts: [...(full.assignedDepts || [])], permissions: [...(full.permissions || [])] }
    if (full.linkedUserId && canManageEsign.value) {
      esignBinding.value = await fetchEsignBinding(full.linkedUserId)
      esignLegalName.value = esignBinding.value.legalName || full.name
      esignAccountInput.value = ''
    }
  } catch {
    // 列表数据仍可用于只读查看。
  }
}
function personnelProfile(person: PersonItem) {
  const payload: Partial<PersonItem> = { ...person }
  if (payload.idNo?.includes('*')) delete payload.idNo
  if (!session.canAction('quality.personnel.sensitive.view') || payload.mobile?.includes('*')) delete payload.mobile
  if (!canManageAccounts.value) {
    delete payload.departmentId
    delete payload.accountEnabled
    delete payload.roleName
  }
  return payload
}
async function save() {
  const current = form.value
  if (!current) return
  if (!current.name.trim() || !current.code.trim()) {
    ElMessage.warning('请填写姓名和人员编号')
    return
  }
  if (!current.linkedUserId && canManageAccounts.value && !current.departmentId) {
    ElMessage.warning('新建登录账号必须选择所属部门')
    return
  }
  if (!/^[A-Za-z0-9_.-]{2,40}$/.test(current.code.trim())) {
    ElMessage.warning('人员编号仅支持字母、数字、点、下划线和短横线')
    return
  }
  saving.value = true
  try {
    const payload = personnelProfile(current)
    if (current.roleName?.trim()) payload.position = current.roleName.trim()
    if (current.id) {
      const saved = await updatePersonnel(current.id, payload)
      downloadInitialCredentials(saved)
      if (saved.linkedUserId && canManageEsign.value && esignAccountInput.value.trim()) {
        try {
          esignBinding.value = await saveEsignBinding(saved.linkedUserId, {
            legalName: esignLegalName.value.trim() || current.name.trim(),
            psnAccount: esignAccountInput.value.trim(),
            psnAccountKind: 'mobile',
            status: 'pending',
          })
          esignAccountInput.value = ''
        } catch (error) {
          ElMessage.error('人员资料已保存，签署绑定未更新：' + (error instanceof Error ? error.message : '请核实名册手机号'))
          return
        }
      }
    } else {
      downloadInitialCredentials(await createPersonnel(payload))
    }
    await reload(current.id ? undefined : 1)
    ElMessage.success(current.id ? '人员调整已保存' : '人员已新建')
    editOpen.value = false
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

const exporting = ref(false)
const importOpen = ref(false)
const importBusy = ref(false)
const importFile = ref<File | null>(null)
const importPreview = ref<PersonnelImportPreview | null>(null)
function showError(error: unknown) { ElMessage.error(error instanceof Error ? error.message : '操作失败') }
async function handleExport() {
  exporting.value = true
  try { await exportPersonnel({ keyword: kw.value, dept: deptFilter.value }) }
  catch (error) { showError(error) }
  finally { exporting.value = false }
}
function openImport() {
  importFile.value = null
  importPreview.value = null
  importOpen.value = true
}
function selectImportFile(upload: { raw?: File }) {
  importPreview.value = null
  importFile.value = upload.raw || null
  if (importFile.value) void runImportPreview()
}
async function runImportPreview() {
  const file = importFile.value
  if (!file || importBusy.value) return
  importPreview.value = null
  if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 5 * 1024 * 1024) {
    ElMessage.warning('请选择不超过5MB的xlsx文件')
    return
  }
  importBusy.value = true
  try { importPreview.value = await previewPersonnelImport(file) }
  catch (error) { showError(error) }
  finally { importBusy.value = false }
}
async function confirmImport() {
  if (!importFile.value || !importPreview.value?.valid || importBusy.value) return
  try { await ElMessageBox.confirm('确认按预检结果更新人员和账号状态？现有密码不变，表外人员不删除。', '确认导入', {type:'warning'}) }
  catch { return }
  importBusy.value = true
  try {
    downloadInitialCredentials(await importPersonnel(importFile.value, importPreview.value.previewToken))
    importOpen.value = false
    ElMessage.success('人员导入完成')
    await reload(1)
  } catch (error) {
    importPreview.value = null
    showError(error)
  } finally { importBusy.value = false }
}
async function confirmRemove(person: PersonItem) {
  try {
    await ElMessageBox.confirm(
      `确认将“${person.name || person.code}”移出人员名册？已关联的登录账号会同时停用，历史业务和审计记录不会删除。`,
      '移出人员名册',
      { type: 'warning', confirmButtonText: '确认移出', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  removing.value = true
  try {
    await removePersonnel(person.id)
    ElMessage.success('人员已移出名册')
    if (form.value?.id === person.id) editOpen.value = false
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    await reload()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '移出失败')
  } finally {
    removing.value = false
  }
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
  const [departmentNames, permissions] = await Promise.all([
    fetchQualityDepts().catch(() => []),
    fetchPermOptions().catch(() => []),
  ])
  permOptions.value = permissions
  if (canManageAccounts.value) {
    const catalog = await getCatalog().catch(() => null)
    deptOptions.value = catalog?.departments ?? departmentNames.map((name) => ({ id: null, name }))
  } else {
    deptOptions.value = departmentNames.map((name) => ({ id: null, name }))
  }
  await reload(1)
  await nextTick()
  calcLayout()
  window.addEventListener('resize', calcLayout)
})
onUnmounted(() => window.removeEventListener('resize', calcLayout))
useLiveSearch(kw, () => reload(1))

// BEGIN TEMPLATE PERSONNEL ADAPTER
const personnelViewOnly=ref(false)
const personnelReadOnly=computed(()=>personnelViewOnly.value||(form.value?.id?!session.canAction('quality.personnel.update'):!session.canAction('quality.personnel.create')))
const personnelFormSchema=computed(()=>personnelSchema({form:form.value,deptOptions:deptOptions.value,canManageAccounts:canManageAccounts.value,canSensitive:session.canAction('quality.personnel.sensitive.view'),syncDepartmentName}))
const personnelPresentation=createPersonnelPresentation(reactive({rows,total,page,size,loading,kw,deptFilter,deptOptions,session,canImport,canManageEsign,exporting,reload,openCreate,openEdit,confirmRemove,handleExport,downloadPersonnelTemplate,openImport,bindingRosterOpen,personnelViewOnly}))
const personnelEsignModel=reactive({esignLegalName,esignAccountInput,esignBindingStatus})
const personnelEsignSchema=computed(()=>esignSchema({placeholder:esignBinding.value?.psnAccountMasked}))
// END TEMPLATE PERSONNEL ADAPTER
</script>


