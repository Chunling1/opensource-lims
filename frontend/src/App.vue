<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import WorkspaceLayout from './components/layout/WorkspaceLayout.vue'
import ErrorBoundary from './components/common/ErrorBoundary.vue'
import ErrorPage from './components/common/ErrorPage.vue'
import { fatalError, failApplication, navigationError, failedDestination } from './stores/errorState'
import { refreshIdentity } from './stores/session'
import { normalizeError } from './services/common/errors'
import { router } from './router/index'
import { useThemeStore } from './stores/theme/index'

const startupPreloader = useThemeStore().settings.preloader === 'enable'
const documentLoading = ref(document.readyState !== 'complete')
function documentLoaded() { documentLoading.value = false }
const ready = ref(false), busy = ref(false), route = useRoute()

async function initialize() {
  if (busy.value) return
  busy.value = true
  try {
    await refreshIdentity(true, !ready.value && !fatalError.value)
    if (failedDestination.value) await router.replace(failedDestination.value)
    await router.isReady()
    fatalError.value = undefined
    ready.value = true
  } catch (e) {
    const error = normalizeError(navigationError.value || e)
    if (error.code === 'UNAUTHORIZED') {
      await router.replace('/identity')
      navigationError.value = error
      ready.value = true
      fatalError.value = undefined
    } else {
      failApplication(error)
    }
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  if (document.readyState === 'complete') documentLoaded()
  else window.addEventListener('load', documentLoaded, { once: true })
  void initialize()
})
onBeforeUnmount(() => window.removeEventListener('load', documentLoaded))
</script>

<template>
  <div v-if="documentLoading && startupPreloader && !fatalError" id="preloader" role="status" aria-label="正在加载工作空间">
    <div id="status"><div class="spinner-border text-primary" aria-hidden="true"></div></div>
  </div>
  <ErrorPage v-if="fatalError" :error="fatalError" standalone retry :busy="busy" @retry="initialize" />
  <ErrorBoundary v-else-if="ready" standalone>
    <RouterView v-if="route.meta.layout === 'standalone'" />
    <WorkspaceLayout v-else />
  </ErrorBoundary>
</template>
