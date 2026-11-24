<script setup lang="ts">
import UserAvatar from '../../components/common/UserAvatar.vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { currentActor, roleLabels } from '../../stores/session'
import { profile } from '../../services/platform/auth'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'

const assets = `${import.meta.env.BASE_URL}template/assets/images/`
const department = ref(''), loading = ref(true), ready = ref(false), error = ref<ErrorValue>(''), actionError = ref<ErrorValue>('')
const tab = ref('overview')
const tabs = [{ key: 'overview', label: '个人概览' }, { key: 'security', label: '账号安全' }]
const scope = computed(() => profile.value?.dataScope.description || '未设置')
const info = computed(() => [
  ['姓名', currentActor.value.name], ['人员账号', currentActor.value.id], ['所属部门', department.value],
  ['联系电话', currentActor.value.phone], ['电子邮箱', currentActor.value.email],
  ['岗位', currentActor.value.position], ['职务', currentActor.value.jobTitle], ['上岗证号', currentActor.value.certificateNumber],
])
const responsibilities: Record<string, string> = {
  admin: '统筹系统配置、人员权限与检测业务管理。', commissions: '办理委托登记，维护委托与客户信息。',
  sampling: '执行采样任务，记录现场采样信息。', samples: '办理样品接收、流转、保管与处置。',
  testing: '执行检测任务，填写检测数据与原始记录。', reviewer: '复核检测数据和报告内容。',
  approver: '审批检测报告及相关业务事项。', reports: '管理报告签发、发放与归档。',
  finance: '办理费用结算与财务业务。', quality: '维护质量体系、人员资料与质量记录。',
  equipment: '维护仪器设备台账与检定校准记录。', inventory: '管理物资、耗材与库存。', system: '维护系统基础资料与业务配置。',
}
let sequence = 0
async function load() {
  const token = ++sequence, actorId = currentActor.value.id, departmentId = currentActor.value.departmentId
  loading.value = true; ready.value = false; error.value = ''; department.value = ''
  try {
    await Promise.resolve()
    if (token !== sequence || actorId !== currentActor.value.id) return
    department.value = profile.value?.personal?.departmentName || '未设置'
    ready.value = true
  } catch (cause) { if (token === sequence) error.value = normalizeError(cause) }
  finally { if (token === sequence) loading.value = false }
}
watch(currentActor, load, { immediate: true })
const unsubscribe = () => {}
onBeforeUnmount(() => { unsubscribe(); sequence++ })

async function navigateTab(event: KeyboardEvent, index: number) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length
  tab.value = tabs[next]!.key
  await nextTick(); document.getElementById(`profile-tab-${tab.value}`)?.focus()
}
</script>

<template>
  <section aria-label="个人资料">
    <div class="profile-foreground position-relative mx-n4 mt-n4" aria-hidden="true"><div class="profile-wid-bg"><img :src="`${assets}profile-bg.jpg`" alt="" class="profile-wid-img" /></div></div>
    <div class="pt-4 mb-4 mb-lg-3 pb-lg-4 profile-wrapper position-relative">
      <div class="row g-4 align-items-center">
        <div class="col-auto"><div class="avatar-lg"><UserAvatar :src="currentActor.avatar" class="img-thumbnail rounded-circle w-100 h-100" /></div></div>
        <div class="col"><div class="p-2 text-break"><p class="text-white-50 mb-1">个人资料</p><h1 class="h3 text-white mb-2">{{ currentActor.name }}</h1><p class="text-white text-opacity-75 mb-0"><i class="ti ti-building me-1" aria-hidden="true"></i>{{ department || '正在加载部门…' }}</p></div></div>
        <div class="col-12 col-lg-auto"><div class="d-flex gap-4 text-white text-center"><div class="p-2"><h2 class="h4 text-white mb-1">{{ currentActor.roles.length }}</h2><p class="mb-0 text-white-50">已配置角色</p></div><div class="p-2"><h2 class="h4 text-white mb-1">{{ scope }}</h2><p class="mb-0 text-white-50">数据范围</p></div></div></div>
      </div>
    </div>
    <div class="d-flex flex-wrap gap-3 align-items-center profile-wrapper position-relative">
      <ul class="nav nav-pills animation-nav profile-nav gap-2 flex-grow-1" role="tablist" aria-label="个人资料栏目">
        <li v-for="(item, index) in tabs" :key="item.key" class="nav-item" role="presentation"><button :id="`profile-tab-${item.key}`" type="button" class="nav-link fs-5" :class="{ active: tab === item.key }" role="tab" :aria-selected="tab === item.key" :aria-controls="`profile-panel-${item.key}`" :tabindex="tab === item.key ? 0 : -1" @click="tab = item.key" @keydown="navigateTab($event, index)">{{ item.label }}</button></li>
      </ul>
      <RouterLink to="/profile/edit" class="btn btn-success"><i class="ti ti-edit me-1" aria-hidden="true"></i>编辑资料</RouterLink>
    </div>
    <div class="pt-4 position-relative">
      <LoadState :loading="loading" :error="error" @retry="load" />
      <div v-if="ready" v-show="tab === 'overview'" id="profile-panel-overview" role="tabpanel" aria-labelledby="profile-tab-overview" tabindex="0">
        <div class="row">
          <aside class="col-xxl-3">
            <div class="card"><div class="card-body"><h2 class="card-title mb-3">基本资料</h2><dl class="mb-0"><div v-for="[label, value] in info" :key="label" class="row g-2 mb-3"><dt class="col-4 fw-medium">{{ label }}</dt><dd class="col-8 text-muted text-break mb-0">{{ value || '未填写' }}</dd></div></dl><p class="text-muted small mb-0">联系方式可在“编辑资料”中修改。</p></div></div>
            <div class="card"><div class="card-body"><h2 class="card-title mb-3">工作入口</h2><div class="d-grid gap-2"><RouterLink to="/dashboard" class="btn btn-primary-lt text-start"><i class="ti ti-dashboard me-2" aria-hidden="true"></i>工作台</RouterLink><RouterLink to="/notifications" class="btn btn-light text-start"><i class="ti ti-bell me-2" aria-hidden="true"></i>消息中心</RouterLink></div></div></div>
          </aside>
          <div class="col-xxl-9">
            <div class="card"><div class="card-body"><h2 class="card-title mb-3">岗位与业务分工</h2><p class="text-muted">当前人员在检测系统中的角色配置。具体操作以业务页面的权限和流程状态为准。</p><div class="row g-3"><div v-for="role in currentActor.roles" :key="role" class="col-md-6"><div class="card profile-project-card profile-project-primary shadow-none h-100 mb-0"><div class="card-body"><div class="d-flex align-items-center gap-3 mb-3"><div class="avatar-xs flex-shrink-0"><span class="avatar bg-primary-subtle text-primary rounded"><i class="ti ti-user-cog fs-2" aria-hidden="true"></i></span></div><h3 class="fs-5 mb-0">{{ roleLabels[role] || role }}</h3></div><p class="text-muted mb-0">{{ responsibilities[role] || '按已配置的角色权限办理业务。' }}</p></div></div></div></div><p v-if="!currentActor.roles.length" class="text-muted mb-0">尚未配置岗位角色，请联系管理员。</p></div></div>
            <div class="card"><div class="card-body"><h2 class="card-title mb-3">业务数据范围</h2><div class="row g-3"><div class="col-sm-6"><p class="text-muted mb-2">所属部门</p><h3 class="fs-5 mb-0">{{ department }}</h3></div><div class="col-sm-6"><p class="text-muted mb-2">部门访问范围</p><span class="badge bg-success-subtle text-success small">{{ scope }}</span></div></div><p class="text-muted mt-3 mb-0">检测项目授权、上岗资质及有效期以人员能力与质量管理记录为准。</p></div></div>
          </div>
        </div>
      </div>
      <div v-show="tab === 'security'" id="profile-panel-security" role="tabpanel" aria-labelledby="profile-tab-security" tabindex="0">
        <div class="card"><div class="card-body"><h2 class="card-title mb-4">账号安全</h2><ErrorNotice :error="actionError" />
          <div class="d-flex flex-wrap align-items-center gap-3 pb-4 border-bottom"><div class="flex-grow-1"><h3 class="fs-5">登录密码</h3><p class="text-muted mb-0">修改密码后需要重新登录。</p></div><RouterLink to="/change-password" class="btn btn-primary-lt">修改密码</RouterLink></div>
          <div class="pt-4"><h3 class="fs-5">当前会话</h3><p class="text-muted mb-0">当前使用平台账号登录，权限和数据范围由管理员统一维护。</p></div>
        </div></div>
      </div>
    </div>
  </section>
</template>
