<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { provideTestPlanCache } from '../../services/common/testPlanCache'
import ErrorBoundary from '../common/ErrorBoundary.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { failedDestination, navigationError } from '../../stores/errorState'
import { router } from '../../router/index'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import BootstrapModal from '../common/BootstrapModal.vue'
import { sessionLocked, currentActor, switchIdentity } from '../../stores/session'
import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'
import ThemePanel from './ThemePanel.vue'
import StageSigningPrompt from '@/components/StageSigningPrompt.vue'
import { useThemeStore } from '../../stores/theme/index'

provideTestPlanCache()
const route = useRoute()
const unlockError = ref<ErrorValue>('')
const navigating = ref(false)
const theme = useThemeStore()
const panel = ref<InstanceType<typeof ThemePanel>>()
const containerClass = computed(() => (theme.settings.width === 'boxed' ? 'container-xl' : 'container-fluid'))

async function retryNavigation() {
  if (navigating.value) return
  navigating.value = true
  try { await router.push(failedDestination.value) } catch { /* router.onError provides the notice */ } finally { navigating.value = false }
}

async function unlock() {
  try { await switchIdentity(currentActor.value.id); unlockError.value = '' } catch (e) { unlockError.value = normalizeError(e) }
}

const scrollY = ref(window.scrollY)
function onScroll() { scrollY.value = window.scrollY }
function backToTop() {
  window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
}

const preloading = ref(false)
let timer: ReturnType<typeof setTimeout>
function preload() {
  clearTimeout(timer)
  preloading.value = theme.settings.preloader === 'enable'
  if (preloading.value) timer = setTimeout(() => { preloading.value = false }, 1000)
}
function escape(e: KeyboardEvent) { if (e.key === 'Escape') theme.mobileOpen = false }

onMounted(() => {
  window.addEventListener('resize', theme.resize)
  window.addEventListener('keydown', escape)
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => {
  theme.mobileOpen = false
  window.removeEventListener('resize', theme.resize)
  window.removeEventListener('keydown', escape)
  window.removeEventListener('scroll', onScroll)
  clearTimeout(timer)
})
watch(() => theme.settings.preloader, preload)
</script>

<template>
  <div id="layout-wrapper" class="page">
    <AppSidebar @settings="panel?.show()" />
    <div class="page-wrapper">
      <AppTopbar :scrolled="scrollY >= 50" @settings="panel?.show()" />
      <main class="page-body">
        <div :class="containerClass">
          <ErrorNotice :error="navigationError" retry :busy="navigating" @retry="retryNavigation" />
          <ErrorBoundary :reset-key="String(route.meta.viewKey || route.path)">
            <RouterView />
          </ErrorBoundary>
        </div>
      </main>
      <footer class="footer footer-transparent d-print-none">
        <div :class="containerClass">
          <div class="row text-center align-items-center flex-row-reverse">
            <div class="col-lg-auto ms-lg-auto">
              <span class="text-secondary">让每一份样品都有迹可循</span>
            </div>
            <div class="col-12 col-lg-auto mt-3 mt-lg-0">
              <span class="text-secondary">{{ new Date().getFullYear() }} © LIMS · 实验室信息管理系统</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  </div>
  <ThemePanel ref="panel" />
  <StageSigningPrompt />
  <BootstrapModal :open="sessionLocked" title="工作空间已锁定" :busy="true" @close="() => {}">
    <ErrorNotice :error="unlockError" />
    <p>{{ currentActor.name }}的演示工作空间已锁定。</p>
    <template #footer><button class="btn btn-primary" @click="unlock">解锁演示工作空间</button></template>
  </BootstrapModal>
  <button id="back-to-top" type="button" class="btn btn-primary btn-icon rounded-circle shadow" :class="scrollY > 100 ? 'd-inline-flex' : 'd-none'" aria-label="返回顶部" @click="backToTop">
    <i aria-hidden="true" class="ti ti-arrow-up"></i>
  </button>
  <div class="lims-customizer-trigger d-none d-md-block d-print-none">
    <button type="button" class="btn btn-info btn-icon rounded-pill shadow-lg" aria-label="悬浮主题设置" @click="panel?.show()">
      <i aria-hidden="true" class="ti ti-settings ti-spin fs-2"></i>
    </button>
  </div>
  <div v-if="preloading" id="preloader" role="status" aria-label="预加载动画预览">
    <div id="status"><div class="spinner-border text-primary" aria-hidden="true"></div></div>
  </div>
</template>
