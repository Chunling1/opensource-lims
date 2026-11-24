<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">
    <template #header-actions>
    <el-button type="primary" @click="openCreate">新增用户</el-button>
    <el-button :disabled="!selectedId" @click="resetPwd">重置密码</el-button>
    <el-button :disabled="!selectedId || saving" :loading="saving" @click="save">保存授权</el-button>
    </template>

  <el-alert
    v-if="!available"
    type="info"
    :closable="false"
    show-icon
    title="本地演示模式：可查看用户授权版式，账号和权限调整不会写入任何平台。"
  />

  <div class="row g-3">
    <el-card shadow="never" class="col-12 col-lg-4">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2"><strong>用户列表</strong><el-tag size="small">{{ users.length }} 人</el-tag></div>
      </template>
      <el-input v-model="userKeyword" clearable placeholder="账号 / 姓名 / 角色"  />
      <button
        v-for="u in filteredUsers"
        :key="u.id"
        class="list-group-item list-group-item-action"
        :class="{ active: u.id === selectedId }"
        @click="selectUser(u.id)"
      >
        <strong>{{ u.name }}（{{ u.account }}）</strong>
        <span>{{ u.roleName }} · {{ u.department }}</span>
        <small>
          功能 {{ u.permissionCount }} · 操作 {{ u.actionCount }}
          <el-tag v-if="!u.enabled" type="danger" size="small">已禁用</el-tag>
        </small>
      </button>
    </el-card>

    <el-card v-if="form" shadow="never" class="col-12 col-lg-8">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
          <strong>{{ form.name }} 的用户授权（立体）</strong>
          <el-tag size="small" type="warning">{{ form.account }}</el-tag>
        </div>
      </template>

      <el-tabs v-model="activeTab" >
        <!-- 功能授权 -->
        <el-tab-pane label="功能授权" name="func">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
            <span class="text-muted">控制能看到哪些菜单 / 页面</span>
            <div>
              <el-button link size="small" @click="selectAllPerms(true)">全选</el-button>
              <el-button link size="small" @click="selectAllPerms(false)">清空</el-button>
            </div>
          </div>
          <div >
            <div v-for="m in permModules" :key="m.key" >
              <el-checkbox
                :model-value="moduleChecked(m)"
                :indeterminate="moduleIndeterminate(m)"
                @change="toggleModule(m)"
              >
                <strong>{{ m.name }}</strong>
              </el-checkbox>
              <div >
                <el-checkbox v-for="p in m.pages" :key="p.permission" v-model="permSet[p.permission]" :label="p.name" />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 项目授权 -->
        <el-tab-pane label="项目授权" name="project">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
            <span class="text-muted">按检测项目 × 工作流步骤授权（可跨部门）</span>
            <div>
              <el-button link size="small" @click="selectAllSteps(true)">全选</el-button>
              <el-button link size="small" @click="selectAllSteps(false)">清空</el-button>
            </div>
          </div>
          <div >
            <table class="row g-3 table table-hover align-middle">
              <thead class="col-12 col-md-6">
                <tr>
                  <th >项目名称</th>
                  <th>代号</th>
                  <th v-for="s in catalog.stepColumns" :key="s.code">{{ s.name }}</th>
                </tr>
              </thead>
              <tbody class="col-12 col-md-6">
                <tr v-for="p in catalog.projects" :key="p.id">
                  <td >{{ p.name }}<span class="text-muted"> · {{ p.department }}</span></td>
                  <td >{{ p.code }}</td>
                  <td v-for="(sid, i) in p.stepIds" :key="i">
                    <el-checkbox v-if="sid != null" v-model="projectStepSet[sid]" />
                    <span v-else class="text-muted">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </el-tab-pane>

        <!-- 标准授权 -->
        <el-tab-pane label="标准授权" name="standard">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
            <span class="text-muted">
              {{ standardDepartment || '当前所属部门' }}；新用户和切换部门后默认全部授权，系统管理员及公司根机构显示全院标准
            </span>
            <div>
              <el-button link size="small" @click="selectAllStandards(true)">全选</el-button>
              <el-button link size="small" @click="selectAllStandards(false)">清空</el-button>
            </div>
          </div>
          <el-input
            v-model="standardKeyword"
            clearable
            placeholder="搜索标准号 / 标准名称"
            
          />
          <div v-if="filteredStandardItems.length" class="list-group">
            <label v-for="item in filteredStandardItems" :key="item.id" class="list-group-item form-label d-block">
              <el-checkbox v-model="standardItemSet[item.id]" />
              <span>
                <strong>{{ item.code }}</strong>
                <small>{{ item.name }}</small>
              </span>
              <el-tag size="small" :type="item.status === '现行' ? 'success' : 'warning'">{{ item.status }}</el-tag>
            </label>
          </div>
          <el-empty v-else description="该部门暂未分配受控标准" />
        </el-tab-pane>

        <!-- 数据授权 -->
        <el-tab-pane label="数据授权" name="data">
          <section class="mb-4">
            <div class="row g-3">
              <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">角色名</label><div class="col"><el-input v-model="form.roleName" size="small" /></div></div></div>
              <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">所属部门</label><div class="col">
                <el-select v-model="form.departmentId" size="small" placeholder="部门" @change="onDepartmentChange">
                  <el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id" />
                </el-select>
              </div></div></div>
              <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">数据范围</label><div class="col">
                <el-select v-model="form.dataScope.scopeType" size="small">
                  <el-option v-for="s in catalog.scopeTypes" :key="s.value" :label="s.label" :value="s.value" />
                </el-select>
              </div></div></div>
              <div class="col-12 col-md-6"><span class="form-label d-block">启用</span><el-switch v-model="form.enabled" /></div>
              <div class="col-12"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">电子签名</label><div class="col"><el-input v-model="form.eSignature" size="small" placeholder="主检/审核/批准签字时取用（如 张三 / 张三（电子签））" /></div></div></div>
            </div>
          </section>

          <section v-if="['department', 'department_project'].includes(form.dataScope.scopeType)" class="mb-4">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
              <h3 class="h5 mb-3">授权部门（可跨部门，选中部门的数据可见）</h3>
              <div>
                <el-button link size="small" @click="selectAllDepts(true)">全选</el-button>
                <el-button link size="small" @click="selectAllDepts(false)">清空</el-button>
              </div>
            </div>
            <div class="row g-3">
              <el-checkbox class="col-12 col-md-6" v-for="d in catalog.departments" :key="d.id" v-model="dataDeptSet[d.id]" :label="d.name" />
            </div>
          </section>

          <section class="mb-4">
            <h3 class="h5 mb-3">授权站点</h3>
            <div class="row g-3">
              <el-checkbox class="col-12 col-md-6" v-for="s in catalog.sites" :key="s" v-model="dataSiteSet[s]" :label="s" />
            </div>
          </section>

          <el-alert
            v-if="scopeHint"
            type="info"
            :closable="false"
            :title="scopeHint"
          />
        </el-tab-pane>

        <!-- 审批事项授权 -->
        <el-tab-pane label="审批事项授权" name="action">
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
            <span class="text-muted">报告各节点的通过/退回、上传、预览下载等操作权限</span>
            <div>
              <el-button link size="small" @click="selectAllActions(true)">全选</el-button>
              <el-button link size="small" @click="selectAllActions(false)">清空</el-button>
            </div>
          </div>
          <div class="row g-3">
            <el-checkbox class="col-12 col-md-6" v-for="a in catalog.actions" :key="a.code" v-model="actionSet[a.code]" :label="a.name" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-empty v-else description="请选择左侧用户进行授权" />
  </div>

  <el-dialog v-model="createOpen" title="新增用户" width="460px">
    <el-form label-width="90px">
      <el-form-item label="账号"><el-input v-model="createForm.account" /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="createForm.name" /></el-form-item>
      <el-form-item label="临时密码"><el-input v-model="createForm.password" placeholder="留空由系统随机生成" /></el-form-item>
      <el-form-item label="部门">
        <el-select v-model="createForm.departmentId" placeholder="部门">
          <el-option v-for="d in catalog.departments" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createOpen = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="doCreate">创建（默认无权限）</el-button>
    </template>
  </el-dialog>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modules } from '@/data/modules'
import {
  ADMIN_AVAILABLE,
  createUser,
  getDepartmentStandardCatalog,
  getCatalog,
  getUser,
  listUsers,
  resetUserPassword,
  updateUser,
  type AdminCatalog,
  type AdminUserBrief,
  type AdminUserDetail,
} from '@/services/admin'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'

const route = useRoute()
const available = ADMIN_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '用户管理'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'user'))
const moduleKey = computed(() => route.meta.moduleKey ?? 'system')
const pages = computed(() => modules.find((m) => m.key === moduleKey.value)?.pages ?? [])

const permModules = modules.map((m) => ({
  key: m.key,
  name: m.name,
  modulePermission: m.permission,
  pages: m.pages.map((p) => ({ name: p.name, permission: p.permission })),
  allCodes: [m.permission, ...m.pages.map((p) => p.permission)],
}))

const users = ref<AdminUserBrief[]>([])
const catalog = reactive<AdminCatalog>({
  permissions: [], actions: [], departments: [], sites: [], stepColumns: [], projects: [], scopeTypes: [],
})
const selectedId = ref<number | null>(null)
const form = ref<AdminUserDetail | null>(null)
const activeTab = ref('func')
const permSet = reactive<Record<string, boolean>>({})
const actionSet = reactive<Record<string, boolean>>({})
const projectStepSet = reactive<Record<number, boolean>>({})
const dataDeptSet = reactive<Record<number, boolean>>({})
const dataSiteSet = reactive<Record<string, boolean>>({})
const standardItemSet = reactive<Record<number, boolean>>({})
const standardItems = ref<AdminUserDetail['standardAuthorization']['items']>([])
const standardDepartment = ref('')
const standardKeyword = ref('')
const userKeyword = ref('')
const saving = ref(false)

const scopeHint = computed(() => {
  const t = form.value?.dataScope.scopeType
  if (t === 'department_project') return '可查看本部门、勾选部门及专业岗位授权项目的样品与报告；部门数据授权不增加项目办理权限。'
  if (t === 'department') return '按勾选部门查看数据；未勾选时默认本部门。办理业务仍需对应功能和项目步骤权限。'
  if (t === 'all') return '全部数据：可查看全院所有报告与数据；办理业务仍需对应权限。'
  if (t === 'self') return '仅本人：只能查看本人承担/登记的数据'
  if (t === 'authorization') return '授权范围：仅查看授权签字范围内（待批准）报告'
  return ''
})

const filteredUsers = computed(() => {
  const kw = userKeyword.value.trim().toLowerCase()
  if (!kw) return users.value
  return users.value.filter((u) => [u.account, u.name, u.roleName].some((x) => x.toLowerCase().includes(kw)))
})
const filteredStandardItems = computed(() => {
  const keyword = standardKeyword.value.trim().toLowerCase()
  if (!keyword) return standardItems.value
  return standardItems.value.filter((item) =>
    `${item.code} ${item.name}`.toLowerCase().includes(keyword),
  )
})

async function init() {
  if (!available) return
  try {
    const [u, c] = await Promise.all([listUsers(), getCatalog()])
    users.value = u
    Object.assign(catalog, c)
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  }
}
init()

function clearSets(...sets: Record<string | number, boolean>[]) {
  for (const s of sets) for (const k of Object.keys(s)) delete s[k]
}

async function selectUser(id: number) {
  selectedId.value = id
  const detail = await getUser(id)
  form.value = detail
  clearSets(permSet, actionSet, projectStepSet, dataDeptSet, dataSiteSet, standardItemSet)
  detail.permissions.forEach((c) => (permSet[c] = true))
  detail.actionPermissions.forEach((c) => (actionSet[c] = true))
  detail.projectStepIds.forEach((sid) => (projectStepSet[sid] = true))
  detail.dataDepartmentIds.forEach((did) => (dataDeptSet[did] = true))
  detail.dataSites.forEach((s) => (dataSiteSet[s] = true))
  standardItems.value = detail.standardAuthorization.items
  standardDepartment.value = detail.standardAuthorization.department
  detail.standardAuthorization.authorizedItemIds.forEach((sid) => (standardItemSet[sid] = true))
  standardKeyword.value = ''
}

function moduleChecked(m: (typeof permModules)[number]) {
  return m.allCodes.every((c) => permSet[c])
}
function moduleIndeterminate(m: (typeof permModules)[number]) {
  const some = m.allCodes.some((c) => permSet[c])
  return some && !m.allCodes.every((c) => permSet[c])
}
function toggleModule(m: (typeof permModules)[number]) {
  const next = !moduleChecked(m)
  m.allCodes.forEach((c) => (permSet[c] = next))
}
function selectAllPerms(v: boolean) {
  permModules.forEach((m) => m.allCodes.forEach((c) => (permSet[c] = v)))
}
function selectAllActions(v: boolean) {
  catalog.actions.forEach((a) => (actionSet[a.code] = v))
}
function selectAllSteps(v: boolean) {
  catalog.projects.forEach((p) => p.stepIds.forEach((sid) => { if (sid != null) projectStepSet[sid] = v }))
}
function selectAllDepts(v: boolean) {
  catalog.departments.forEach((d) => (dataDeptSet[d.id] = v))
}
function selectAllStandards(v: boolean) {
  standardItems.value.forEach((item) => (standardItemSet[item.id] = v))
}
async function onDepartmentChange(departmentId: number) {
  try {
    const result = await getDepartmentStandardCatalog(departmentId, form.value?.id)
    clearSets(dataDeptSet)
    dataDeptSet[departmentId] = true
    standardItems.value = result.items
    standardDepartment.value = result.department
    clearSets(standardItemSet)
    result.authorizedItemIds.forEach((sid) => (standardItemSet[sid] = true))
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '部门标准加载失败')
  }
}

async function save() {
  if (!form.value) return
  saving.value = true
  try {
    const perms = new Set(Object.keys(permSet).filter((k) => permSet[k]))
    permModules.forEach((m) => {
      if (m.pages.some((p) => perms.has(p.permission))) perms.add(m.modulePermission)
    })
    const updated = await updateUser(form.value.id, {
      permissions: [...perms],
      actionPermissions: Object.keys(actionSet).filter((k) => actionSet[k]),
      projectStepIds: Object.keys(projectStepSet).filter((k) => projectStepSet[Number(k)]).map(Number),
      standardItemIds: Object.keys(standardItemSet).filter((k) => standardItemSet[Number(k)]).map(Number),
      dataDepartmentIds: Object.keys(dataDeptSet).filter((k) => dataDeptSet[Number(k)]).map(Number),
      dataSites: Object.keys(dataSiteSet).filter((k) => dataSiteSet[k]),
      dataScopeType: form.value.dataScope.scopeType,
      dataScopeDesc: form.value.dataScope.description,
      departmentId: form.value.departmentId,
      roleName: form.value.roleName,
      enabled: form.value.enabled,
      eSignature: form.value.eSignature,
    })
    ElMessage.success('授权已保存，该用户下次登录生效')
    const idx = users.value.findIndex((u) => u.id === updated.id)
    if (idx >= 0) users.value[idx] = updated
    form.value = updated
    standardItems.value = updated.standardAuthorization.items
    standardDepartment.value = updated.standardAuthorization.department
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function resetPwd() {
  if (!selectedId.value) return
  try {
    const { value } = await ElMessageBox.prompt('输入临时密码；留空将由系统随机生成。该账户下次登录必须改密。', '重置密码', {
      inputValue: '', confirmButtonText: '重置', cancelButtonText: '取消',
    })
    const result = await resetUserPassword(selectedId.value, value || undefined)
    await ElMessageBox.alert(`临时密码：${result.tempPassword}\n请通过安全渠道交给该用户，此信息关闭后不再显示。`, '密码已重置', {
      confirmButtonText: '我已记录', type: 'success',
    })
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '重置失败')
  }
}

const createOpen = ref(false)
const creating = ref(false)
const createForm = reactive({ account: '', name: '', password: '', departmentId: null as number | null })
function openCreate() {
  Object.assign(createForm, { account: '', name: '', password: '', departmentId: null })
  createOpen.value = true
}
async function doCreate() {
  creating.value = true
  try {
    const result = await createUser({
      account: createForm.account,
      name: createForm.name,
      password: createForm.password || undefined,
      departmentId: createForm.departmentId,
    })
    createOpen.value = false
    await init()
    await selectUser(result.user.id)
    await ElMessageBox.alert(`临时密码：${result.tempPassword}\n请通过安全渠道交给该用户，此信息关闭后不再显示。`, '用户已创建', {
      confirmButtonText: '我已记录', type: 'success',
    })
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    creating.value = false
  }
}
</script>
