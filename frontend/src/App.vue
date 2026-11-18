<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api, ApiError, type User, type TaskList } from './api'
import { useRoute, useRouter } from 'vue-router'
import ShellMenus from './ShellMenus.vue'
import {
  IconFlask2,
  IconEye,
  IconEyeOff,
  IconMenu2,
  IconSearch,
  IconListCheck,
  IconCircleCheck,
  IconX,
} from '@tabler/icons-vue'
const route = useRoute(),
  router = useRouter()
const mobileNav = ref(false)
const groupItems = [
  { name: 'samples', title: '检测样品' },
  { name: 'reports', title: '检测报告' },
] as const
const navOpen = ref(true)
const showPassword = ref(false)
const user = ref<User | null>(null)
const ready = ref(false),
  busy = ref(false),
  account = ref(''),
  password = ref(''),
  error = ref('')
const notices = ref<{ number: string; message: string }[]>([])
async function enter(u: User) {
  user.value = u
  await refresh()
}
onMounted(async () => {
  try {
    await enter(await api<User>('me'))
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401)) error.value = String(e)
  } finally {
    ready.value = true
  }
})
async function login() {
  busy.value = true
  error.value = ''
  try {
    await enter(await api<User>('login', { account: account.value, password: password.value }))
    password.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
async function logout() {
  await api('logout', {})
  await router.replace({ name: 'tasks' })
  user.value = null
  counts.value = undefined
  hideToast()
  notices.value = []
}

const counts = ref<TaskList['counts']>()
const toast = ref(''),
  shellError = ref('')
const active = computed(() =>
  route.name === 'report' ? 'reports' : route.name === 'sample' ? 'samples' : route.name,
)
const badges = computed(() => ({
  tasks: Object.values(counts.value ?? {}).reduce((a, b) => a + b, 0),
  samples: counts.value?.claim ?? 0,
  reports:
    (counts.value?.author ?? 0) + (counts.value?.review1 ?? 0) + (counts.value?.returned ?? 0),
}))
const isCatalog = computed(() => !!user.value?.permissions.includes('catalog'))
let timer: ReturnType<typeof setTimeout>
let request = 0
async function refresh() {
  const id = ++request,
    current = user.value
  if (!current) return
  try {
    const [tasks, alerts] = await Promise.all([
      api<TaskList>('tasks'),
      current.permissions.includes('catalog')
        ? api<{ number: string; message: string }[]>('notices')
        : Promise.resolve([]),
    ])
    if (id !== request || user.value !== current) return
    counts.value = tasks.counts
    notices.value = alerts
    shellError.value = ''
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      user.value = null
      return
    }
    shellError.value = e instanceof Error ? e.message : String(e)
  }
}
function hideToast() {
  clearTimeout(timer)
  toast.value = ''
}
function saved() {
  hideToast()
  toast.value = '已保存。'
  timer = setTimeout(hideToast, 3000)
  void refresh()
}
watch(
  () => route.fullPath,
  () => {
    mobileNav.value = false
  },
)
onUnmounted(hideToast)
</script>
<template>
  <div v-if="ready && !user" class="page page-center bg-primary-lt min-vh-100">
    <div class="container container-narrow py-4">
      <div class="card card-md overflow-hidden">
        <div class="row g-0">
          <div class="col-lg-6 d-none d-lg-flex flex-column justify-content-between bg-primary text-white p-5" data-bs-theme="dark">
            <div class="d-flex align-items-center gap-2">
              <span class="avatar bg-white text-primary"><IconFlask2 /></span
              ><span class="h2 mb-0 text-white">实验室工作台</span>
            </div>
            <div>
              <div class="h1 text-white mb-3">检测业务一处办理</div>
              <ul class="list-unstyled lead text-white-50 mb-0">
                <li class="mb-2"><IconCircleCheck class="icon me-2" />样品领取、转交与退回</li>
                <li class="mb-2"><IconCircleCheck class="icon me-2" />原始记录与待签报告上传</li>
                <li><IconCircleCheck class="icon me-2" />送审与站内待办提醒</li>
              </ul>
            </div>
            <div class="text-white-50">LIMS 基础版 · v0.1</div>
          </div>
          <div class="col-12 col-lg-6 d-flex flex-column justify-content-center">
            <form class="card-body p-5" autocomplete="off" @submit.prevent="login">
              <div class="d-lg-none text-center mb-4">
                <span class="navbar-brand gap-2"
                  ><span class="avatar bg-primary text-white"><IconFlask2 /></span
                  ><span class="h2 mb-0">实验室工作台</span></span
                >
              </div>
              <h1 class="h2 mb-1">登录工作台</h1>
              <p class="text-secondary mb-4">请使用实验室分配的账号登录。</p>
              <div class="mb-3">
                <label class="form-label" for="account">账号</label
                ><input id="account" class="form-control" v-model="account" autocomplete="username" required />
              </div>
              <div class="mb-2">
                <label class="form-label" for="password">密码</label>
                <div class="input-group input-group-flat">
                  <input
                    id="password"
                    class="form-control"
                    :type="showPassword ? 'text' : 'password'"
                    v-model="password"
                    autocomplete="current-password"
                    required
                  /><span class="input-group-text"
                    ><button
                      type="button"
                      class="btn btn-link link-secondary p-0"
                      :aria-label="showPassword ? '隐藏明文' : '显示明文'"
                      :aria-pressed="showPassword"
                      @click="showPassword = !showPassword"
                    >
                      <component :is="showPassword ? IconEyeOff : IconEye" class="icon" /></button
                  ></span>
                </div>
              </div>
              <div v-if="error" class="alert alert-danger mt-3 mb-0" role="alert">
                <div class="alert-icon"><IconX class="icon alert-icon" /></div>
                <div>{{ error }}</div>
              </div>
              <div class="form-footer">
                <button class="btn btn-primary w-100" :disabled="busy">
                  <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>登录
                </button>
              </div>
              <div class="text-center text-secondary mt-4">仅限授权人员使用</div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-if="user" class="page">
    <aside class="navbar navbar-vertical navbar-expand-lg bg-primary" data-bs-theme="dark">
      <div class="container-fluid">
        <button
          class="navbar-toggler"
          type="button"
          aria-label="展开导航"
          aria-controls="sidebar-menu"
          :aria-expanded="mobileNav"
          @click="mobileNav = !mobileNav"
        >
          <IconMenu2 class="icon" />
        </button>
        <div class="navbar-brand navbar-brand-autodark py-lg-3">
          <IconFlask2 class="icon me-2" /><span>实验室工作台</span>
        </div>
        <ShellMenus
          class="d-lg-none"
          dark
          :user="user"
          :notices="notices"
          @refresh="refresh"
          @logout="logout"
        />
        <div id="sidebar-menu" class="collapse navbar-collapse" :class="{ show: mobileNav }">
          <div class="input-icon d-lg-none my-3 px-2">
            <span class="input-icon-addon"><IconSearch class="icon" /></span
            ><input
              type="search"
              class="form-control"
              disabled
              aria-label="全局搜索，范围待确定"
              placeholder="全局搜索（范围待确定）"
            />
          </div>
          <ul class="navbar-nav pt-lg-2">
            <li class="nav-item" :class="{ active: active === 'tasks' }">
              <RouterLink class="nav-link" :to="{ name: 'tasks' }"
                ><span class="nav-link-icon"><IconListCheck class="icon" /></span
                ><span class="nav-link-title">我的待办</span
                ><span v-if="counts && badges.tasks" class="badge badge-sm bg-white text-primary position-static ms-auto">{{
                  badges.tasks
                }}</span></RouterLink
              >
            </li>
            <li
              v-if="!isCatalog"
              class="nav-item dropdown"
              :class="{ active: active === 'samples' || active === 'reports' }"
            >
              <a
                href="#"
                class="nav-link dropdown-toggle"
                :class="{ show: navOpen }"
                role="button"
                aria-controls="nav-detection"
                :aria-expanded="navOpen"
                @click.prevent="navOpen = !navOpen"
                ><span class="nav-link-icon"><IconFlask2 class="icon" /></span
                ><span class="nav-link-title">检测管理</span></a
              >
              <div id="nav-detection" class="dropdown-menu" :class="{ show: navOpen }">
                <RouterLink
                  v-for="m in groupItems"
                  :key="m.name"
                  class="dropdown-item"
                  :class="{ active: active === m.name }"
                  :to="{ name: m.name }"
                  >{{ m.title
                  }}<span v-if="counts && badges[m.name]" class="badge badge-sm bg-white text-primary ms-auto">{{
                    badges[m.name]
                  }}</span></RouterLink
                >
              </div>
            </li>
          </ul>
        </div>
      </div>
    </aside>
    <div class="page-wrapper">
      <header class="navbar navbar-expand-md d-none d-lg-flex d-print-none">
        <div class="container-xl">
          <ShellMenus :user="user" :notices="notices" @refresh="refresh" @logout="logout" />
          <div class="collapse navbar-collapse show">
            <div class="input-icon w-50">
              <span class="input-icon-addon"><IconSearch class="icon" /></span
              ><input
                type="search"
                class="form-control"
                disabled
                aria-label="全局搜索，范围待确定"
                placeholder="全局搜索（范围待确定）"
              />
            </div>
          </div>
        </div>
      </header>
      <main class="page-body">
        <div class="container-xl">
          <div v-if="shellError" class="alert alert-danger" role="alert">{{ shellError }}</div>
          <RouterView v-slot="{ Component }"
            ><component
              :is="Component"
              :key="route.fullPath"
              @counts="counts = $event"
              @expired="user = null"
              @dismiss-toast="hideToast"
              @saved="saved"
          /></RouterView>
        </div>
      </main>
      <footer class="footer footer-transparent d-print-none">
        <div class="container-xl text-secondary">LIMS 基础版 · v0.1</div>
      </footer>
    </div>
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
      <div v-if="toast" class="toast show" role="status" aria-live="polite">
        <div class="toast-header">
          <IconCircleCheck class="icon text-success me-2" /><strong class="me-auto">操作完成</strong
          ><button type="button" class="btn-close" aria-label="关闭提示" @click="hideToast"></button>
        </div>
        <div class="toast-body">{{ toast }}</div>
      </div>
    </div>
  </div>
</template>
