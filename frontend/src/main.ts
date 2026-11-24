import '@tabler/core/dist/css/tabler.min.css'
import '@tabler/icons-webfont/dist/tabler-icons.min.css'
import 'filepond/dist/filepond.min.css'
import 'flatpickr/dist/flatpickr.min.css'
import 'flatpickr/dist/plugins/monthSelect/style.css'
import './styles/tabler-lims.css'

import * as FilePond from 'filepond'
import flatpickr from 'flatpickr'
import { Mandarin } from 'flatpickr/dist/l10n/zh.js'
import monthSelectPlugin from 'flatpickr/dist/plugins/monthSelect/index.js'

import { createApp, defineComponent, h, Fragment, watch } from 'vue'
import { createPinia } from 'pinia'
import { router } from './router/index'
import { PlatformSession as App } from './platformSession'
import { failApplication } from './stores/errorState'
import { normalizeError } from './services/common/errors'
import { installPlatformControls, PlatformFeedback } from './platformUi/controls'
import { profile, refreshProfile } from './services/platform/auth'
import { getSessionToken } from './services/platform/http'
import { useSessionStore } from './modules/stores/session'
import { setAccessToken } from './modules/services/http'
import type { AuthResponse } from './modules/services/auth'

flatpickr.localize(Mandarin)
const globalWindow = window as unknown as Record<string, unknown>
globalWindow.FilePond = FilePond
globalWindow.flatpickr = flatpickr
globalWindow.monthSelectPlugin = monthSelectPlugin

const pinia = createPinia()
const app = createApp(defineComponent({ setup: () => () => h(Fragment, [h(App), h(PlatformFeedback)]) })).use(pinia).use(router)
installPlatformControls(app)
watch(profile, value => {
  const store = useSessionStore(pinia)
  if (value) {
    setAccessToken(getSessionToken())
    store.applyAuth(value as unknown as AuthResponse)
  } else {
    store.clear()
  }
}, { immediate: true })
window.addEventListener('lims:permissions-stale', () => { void refreshProfile().catch(normalizeError) })
app.config.errorHandler = value => failApplication(value)
window.addEventListener('unhandledrejection', event => { normalizeError(event.reason) })
window.addEventListener('error', event => { if (event.error) normalizeError(event.error) })
app.mount('#app')
window.dispatchEvent(new Event('lims:mounted'))
