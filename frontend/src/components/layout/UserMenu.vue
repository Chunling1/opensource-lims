<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Dropdown from 'bootstrap/js/dist/dropdown'
import { currentActor, roleLabels, sessionLocked } from '../../stores/session'
import { profile, logout } from '../../services/platform/auth'
import { flushTablePreferences } from '../../services/platform/tablePreferences'
import BootstrapModal from '../common/BootstrapModal.vue'
import UserAvatar from '../common/UserAvatar.vue'
const props = defineProps<{ sidebar?: boolean }>()
const emit = defineEmits<{ settings: [] }>()
const route = useRoute(), trigger = ref<HTMLElement>(), dialog = ref('')
const id = props.sidebar ? 'sidebar-user-dropdown' : 'page-header-user-dropdown'
let dropdown: Dropdown | undefined
function escapeMenu(event: KeyboardEvent) { if (event.key === 'Escape') dropdown?.hide() }
onMounted(() => { dropdown = Dropdown.getOrCreateInstance(trigger.value!); document.addEventListener('keydown', escapeMenu) })
onBeforeUnmount(() => { document.removeEventListener('keydown', escapeMenu); dropdown?.hide(); dropdown?.dispose() })
watch(() => route.fullPath, () => dropdown?.hide())
function showDialog(title: string) { dropdown?.hide(); dialog.value = title }
async function signOut() { if (!await flushTablePreferences()) { window.alert('显示设置尚未保存，请重试后退出。'); return } dropdown?.hide(); logout(); location.reload() }
function settings() { dropdown?.hide(); emit('settings') }
</script>

<template>
  <div class="dropdown" :class="sidebar ? 'sidebar-user m-1 rounded' : 'ms-sm-3 header-item topbar-user'">
    <button :id="id" ref="trigger" type="button" class="btn material-shadow-none" data-bs-toggle="dropdown" aria-haspopup="true" aria-expanded="false" :aria-label="sidebar ? '侧栏用户菜单' : '用户菜单'">
      <span class="d-flex align-items-center" :class="{ 'gap-2': sidebar }">
        <UserAvatar class="header-profile-user" :class="sidebar ? 'rounded' : 'rounded-circle'" :src="currentActor.avatar" />
        <span class="text-start" :class="{ 'ms-xl-2': !sidebar }">
          <span :class="sidebar ? 'd-block fw-medium sidebar-user-name-text' : 'd-none d-xl-inline-block ms-1 fw-medium user-name-text'">{{ currentActor.name }}</span>
          <span v-if="sidebar" class="d-block fs-5 sidebar-user-name-sub-text"><i aria-hidden="true" class="ti ti-circle small text-success align-baseline"></i> <span class="align-middle">在线</span></span>
          <span v-else class="d-none d-xl-block ms-1 small user-name-sub-text">{{ profile?.personal?.departmentName || '未设置部门' }}</span>
        </span>
      </span>
    </button>
    <div class="dropdown-menu dropdown-menu-end" :aria-labelledby="id">
      <h6 class="dropdown-header">欢迎，{{ currentActor.name }}！</h6>
      <RouterLink class="dropdown-item" to="/profile"><i aria-hidden="true" class="ti ti-user-circle text-muted fs-4 align-middle me-1"></i> <span class="align-middle">个人资料</span></RouterLink>
      <RouterLink class="dropdown-item" to="/notifications"><i class="ti ti-message text-muted fs-4 align-middle me-1"></i>消息中心</RouterLink>
      <button type="button" class="dropdown-item" @click="showDialog('使用帮助')"><i aria-hidden="true" class="ti ti-lifebuoy text-muted fs-4 align-middle me-1"></i> <span class="align-middle">使用帮助</span></button>
      <div class="dropdown-divider"></div>
      <button type="button" class="dropdown-item" @click="settings"><span class="badge bg-success-subtle text-success mt-1 float-end">主题</span><i aria-hidden="true" class="ti ti-settings text-muted fs-4 align-middle me-1"></i> <span class="align-middle">设置</span></button>
      <RouterLink class="dropdown-item" to="/identity"><i class="ti ti-user-share text-muted fs-4 align-middle me-1"></i>账号信息</RouterLink>
      <button type="button" class="dropdown-item" @click="signOut"><i class="ti ti-lock text-muted fs-4 align-middle me-1"></i>退出登录</button>
    </div>
  </div>
  <BootstrapModal :open="!!dialog" :title="dialog" @close="dialog = ''">
    <template v-if="dialog === '个人资料'"><div class="text-center"><UserAvatar :src="currentActor.avatar" class="avatar-lg rounded-circle img-thumbnail" /><h5 class="mt-3 mb-1">{{ currentActor.name }}</h5><p class="text-muted">{{ currentActor.roles.map(role => roleLabels[role] || role).join(' / ') }} · 平台工作空间</p></div><div class="alert alert-info mb-0">{{ profile?.dataScope.description || '权限由平台账号统一管理。' }}</div></template>
    <template v-else-if="dialog === '使用帮助'"><h6>样品处理流程</h6><p>样品在委托登记中创建，后续通过合同评审、样品管理和检测管理处理，可在委托查询中查看详情。</p><p class="mb-0 text-muted">顶部搜索可按编号和名称查找委托查询中的样品，通知服务尚未接入，不展示演示消息。主题设置会自动保存。</p></template>
    <template #footer><button type="button" class="btn btn-light" @click="dialog = ''">关闭</button></template>
  </BootstrapModal>
</template>
