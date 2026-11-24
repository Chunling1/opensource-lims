<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Dropdown from 'bootstrap/js/dist/dropdown'
import UserMenu from './UserMenu.vue'
import TopbarSearch from './TopbarSearch.vue'
import { useThemeStore } from '../../stores/theme/index'
import NotificationMessages from '../common/NotificationMessages.vue'
import { demoNotifications } from '../../services/business/demoNotifications'
import { currentActor, canRead, hasRole } from '../../stores/session'
import { samplePages, samplePageRoles } from '../../router/navigation/sampleNavigation'
import { navigation, flattenNavigation } from '../../router/navigation/navigation'

const theme = useThemeStore()
const route = useRoute()
defineEmits<{ settings: [] }>()
defineProps<{ scrolled?: boolean }>()

const root = ref<HTMLElement>()
const fullscreen = ref(false)
const fullscreenError = ref('')

const shortcuts = computed(() =>
  navigation
    .flatMap(group => flattenNavigation(group.children))
    .filter(
      i =>
        ['/dashboard'].includes(i.to) ||
        (samplePages.some(page => page.to === i.to) && hasRole(currentActor.value, samplePageRoles)) ||
        (i.module && ['commissions', 'tasks', 'reports'].includes(i.module) && canRead(currentActor.value, i.module)),
    )
    .slice(0, 9),
)
const dark = computed(() => theme.displaySettings.mode === 'dark')

let dropdowns: Dropdown[] = []
function hideDropdowns() { dropdowns.forEach(dropdown => dropdown.hide()) }
function closeNotifications(event: KeyboardEvent) {
  const trigger = root.value?.querySelector<HTMLElement>('#page-header-notifications-dropdown')
  if (event.key === 'Escape' && trigger?.getAttribute('aria-expanded') === 'true') {
    Dropdown.getOrCreateInstance(trigger).hide()
    trigger.focus()
  }
}
function syncFullscreen() {
  fullscreen.value = !!document.fullscreenElement
  document.body.classList.toggle('fullscreen-enable', fullscreen.value)
}
async function toggleFullscreen() {
  fullscreenError.value = ''
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch {
    fullscreenError.value = '浏览器暂不支持全屏，请检查浏览器权限。'
  }
}

onMounted(() => {
  dropdowns = Array.from(root.value!.querySelectorAll<HTMLElement>('[data-topbar-dropdown]')).map(element => Dropdown.getOrCreateInstance(element))
  document.addEventListener('fullscreenchange', syncFullscreen)
  document.addEventListener('keydown', closeNotifications)
  syncFullscreen()
})
watch(() => route.fullPath, hideDropdowns)
onBeforeUnmount(() => {
  hideDropdowns()
  dropdowns.forEach(dropdown => dropdown.dispose())
  document.removeEventListener('fullscreenchange', syncFullscreen)
  document.body.classList.remove('fullscreen-enable')
  document.removeEventListener('keydown', closeNotifications)
})
</script>

<template>
  <header id="page-topbar" ref="root" class="navbar navbar-expand-md d-print-none" :class="{ 'shadow-sm': scrolled }">
    <div class="container-fluid">
      <div class="d-flex align-items-center gap-2">
        <button
          id="topnav-hamburger-icon"
          type="button"
          class="btn btn-icon btn-ghost-secondary d-lg-none"
          aria-label="切换导航菜单"
          @click="theme.toggleMenu()"
        >
          <i aria-hidden="true" class="ti ti-menu-2 fs-2"></i>
        </button>
        <TopbarSearch />
      </div>

      <div class="navbar-nav flex-row align-items-center gap-1 ms-auto">
        <div class="nav-item dropdown d-md-none">
          <button
            id="page-header-search-dropdown"
            type="button"
            class="btn btn-icon btn-ghost-secondary rounded-circle"
            data-topbar-dropdown
            data-bs-toggle="dropdown"
            aria-haspopup="true"
            aria-expanded="false"
            aria-label="打开手机搜索"
          >
            <i aria-hidden="true" class="ti ti-search fs-2"></i>
          </button>
          <div class="dropdown-menu dropdown-menu-end p-0" style="min-width: 18rem" aria-labelledby="page-header-search-dropdown">
            <TopbarSearch mobile />
          </div>
        </div>

        <div class="nav-item dropdown">
          <button
            id="page-header-apps-dropdown"
            type="button"
            class="btn btn-icon btn-ghost-secondary rounded-circle"
            data-topbar-dropdown
            data-bs-toggle="dropdown"
            aria-haspopup="true"
            aria-expanded="false"
            aria-label="快捷应用"
          >
            <i aria-hidden="true" class="ti ti-apps fs-2"></i>
          </button>
          <div class="dropdown-menu dropdown-menu-end p-0" style="min-width: 20rem" aria-labelledby="page-header-apps-dropdown">
            <div class="p-3 border-bottom d-flex align-items-center justify-content-between">
              <h6 class="m-0 fw-semibold">快捷应用</h6>
              <RouterLink to="/dashboard" class="btn btn-sm btn-info-lt">
                工作台 <i aria-hidden="true" class="ti ti-chevron-right align-middle"></i>
              </RouterLink>
            </div>
            <div class="p-2">
              <div class="row g-0">
                <div v-for="item in shortcuts" :key="item.to" class="col-4">
                  <RouterLink class="dropdown-icon-item" :to="item.to">
                    <i aria-hidden="true" class="fs-2 text-primary" :class="item.icon"></i>
                    <span>{{ item.label }}</span>
                  </RouterLink>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="nav-item d-none d-sm-flex">
          <button
            type="button"
            class="btn btn-icon btn-ghost-secondary rounded-circle"
            :aria-label="fullscreen ? '退出全屏' : '进入全屏'"
            @click="toggleFullscreen"
          >
            <i aria-hidden="true" class="fs-2 ti" :class="fullscreen ? 'ti-arrows-minimize' : 'ti-arrows-maximize'"></i>
          </button>
        </div>

        <div class="nav-item d-none d-sm-flex">
          <button
            type="button"
            class="btn btn-icon btn-ghost-secondary rounded-circle light-dark-mode"
            aria-label="切换明暗模式"
            @click="theme.set('mode', dark ? 'light' : 'dark')"
          >
            <i aria-hidden="true" class="fs-2 ti" :class="dark ? 'ti-sun' : 'ti-moon'"></i>
          </button>
        </div>

        <div id="notificationDropdown" class="nav-item dropdown">
          <button
            id="page-header-notifications-dropdown"
            type="button"
            class="btn btn-icon btn-ghost-secondary rounded-circle position-relative"
            data-topbar-dropdown
            data-bs-toggle="dropdown"
            data-bs-auto-close="outside"
            aria-haspopup="true"
            aria-expanded="false"
            aria-label="通知消息"
          >
            <i aria-hidden="true" class="ti ti-bell fs-2"></i>
            <span class="position-absolute topbar-badge small translate-middle badge rounded-pill bg-danger">
              {{ demoNotifications.length }}
              <span class="visually-hidden">条通知</span>
            </span>
          </button>
          <div class="dropdown-menu dropdown-menu-end p-0" style="min-width: 22rem" aria-labelledby="page-header-notifications-dropdown">
            <div class="bg-primary text-white rounded-top p-3 d-flex align-items-center justify-content-between">
              <h6 class="m-0 fw-semibold text-white">通知消息</h6>
              <span class="badge bg-light text-body">{{ demoNotifications.length }} 条消息</span>
            </div>
            <NotificationMessages />
          </div>
        </div>

        <div class="nav-item">
          <button
            type="button"
            class="btn btn-icon btn-ghost-secondary rounded-circle"
            aria-label="打开主题设置"
            @click="$emit('settings')"
          >
            <i aria-hidden="true" class="ti ti-settings fs-2"></i>
          </button>
        </div>

        <UserMenu @settings="$emit('settings')" />
      </div>
    </div>
    <div v-if="fullscreenError" class="alert alert-warning alert-dismissible mb-0 w-100" role="alert">
      {{ fullscreenError }}
      <button type="button" class="btn-close" aria-label="关闭全屏提示" @click="fullscreenError = ''"></button>
    </div>
  </header>
</template>
