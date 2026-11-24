import { refreshIdentity } from './stores/session'
import { useRoute } from 'vue-router'
import { router } from './router'
import LoginView from './views/auth/LoginView.vue'
import ForgotPasswordView from './views/auth/ForgotPasswordView.vue'
import { defineComponent, h, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { logout, profile } from './services/platform/auth'
import { getSessionToken, hasSession, platformRequest } from './services/platform/http'
import { normalizeError, type ErrorValue } from './services/common/errors'
import ErrorPage from './components/common/ErrorPage.vue'
import PageHeading from './components/common/PageHeading.vue'
import LoadState from './components/common/LoadState.vue'
import App from './App.vue'

export const PlatformSession = defineComponent({
  setup() {
    const restoring=ref(hasSession()), route=useRoute()
    const restorationError=ref<ErrorValue>('')
    const offline = ref(!navigator.onLine)
    const interrupted = ref(false), checking = ref(false), sessionExpired = ref(false)
    watch(profile, value => { if (value) sessionExpired.value = false })
    const expired = () => {
      restorationError.value = ''
      interrupted.value = false
      sessionExpired.value = true
      logout()
      if (route.path !== '/login') {
        const redirect = route.fullPath
        void nextTick(() => router.replace({ path: '/login', query: { redirect } }))
      }
    }
    const disconnected = () => { offline.value = true; interrupted.value = true }
    const requestInterrupted = () => { interrupted.value = true }
    async function checkConnection() {
      if (offline.value || checking.value || restoring.value || !profile.value) return
      const token = getSessionToken()
      checking.value = true
      try {
        await platformRequest('/api/auth/profile')
        if (token === getSessionToken() && !offline.value) interrupted.value = false
      } catch (error) {
        if (token === getSessionToken()) {
          if (normalizeError(error).code === 'UNAUTHORIZED') expired()
          else interrupted.value = true
        }
      } finally { checking.value = false }
    }
    const reconnected = () => { offline.value = false; void checkConnection() }
    const visible = () => { if (document.visibilityState === 'visible') void checkConnection() }
    let sessionCheck: ReturnType<typeof setInterval>
    async function restoreSession() {
      restoring.value=true
      restorationError.value=''
      const restoringToken = getSessionToken()
      try {
        if (restoringToken) await refreshIdentity(true)
      } catch (cause) {
        if (getSessionToken() !== restoringToken) return
        const error=normalizeError(cause)
        if (error.code === 'UNAUTHORIZED') { expired(); return }
        restorationError.value=error
      } finally { restoring.value=false }
    }
    onMounted(() => {
      window.addEventListener('lims-next:unauthorized',expired)
      window.addEventListener('lims:connection-interrupted', requestInterrupted)
      window.addEventListener('offline', disconnected)
      window.addEventListener('online', reconnected)
      document.addEventListener('visibilitychange', visible)
      sessionCheck = setInterval(visible, 120_000)
      void restoreSession()
    })
    onBeforeUnmount(() => {
      window.removeEventListener('lims-next:unauthorized', expired)
      window.removeEventListener('lims:connection-interrupted', requestInterrupted)
      window.removeEventListener('offline', disconnected)
      window.removeEventListener('online', reconnected)
      document.removeEventListener('visibilitychange', visible)
      clearInterval(sessionCheck)
    })
    // Keep the submitting form alive while signIn finishes profile loading and
    // navigation. Mounting App on /login would render a second, empty login form.
    return () => restoring.value ? h(LoadState,{loading:true})
      : restorationError.value ? h(ErrorPage,{error:restorationError.value,standalone:true,retry:true,title:'暂时无法恢复登录，请重试',onRetry:restoreSession})
      : profile.value && !['/login', '/forgot-password'].includes(route.path) ? [
        offline.value || interrupted.value ? h('div', {
          class: 'alert alert-warning position-fixed bottom-0 start-50 translate-middle-x z-3 d-flex align-items-center gap-2',
          role: 'status',
        }, [
          offline.value ? '网络已断开。当前页面内容仍保留，请恢复连接后再提交。'
            : '服务器连接中断或超时。当前页面内容仍保留，请先核对连接和操作状态。',
          h('button', { type: 'button', class: 'btn btn-sm btn-light text-nowrap', disabled: offline.value || checking.value, onClick: checkConnection },
            checking.value ? '正在核对' : '核对连接'),
        ]) : null,
        h(App),
      ]
      : route.path === '/forgot-password' ? h(ForgotPasswordView)
      : h(LoginView, { sessionExpired: sessionExpired.value && !profile.value })
  },
})
export const SessionDetails = defineComponent({ setup() { return () => h('div', [h(PageHeading, { title: '账号信息' }), h('div', { class: 'card' }, [h('div', { class: 'card-body' }, [h('p', `${profile.value?.userName || ''} · ${profile.value?.roleName || ''}`), h('p', profile.value?.dataScope.description || ''), h('button', { class: 'btn btn-primary', onClick: () => { logout(); location.reload() } }, '退出登录')])])]) } })
