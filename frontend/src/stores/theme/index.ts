import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { applyTheme, defaults, normalizeSettings, restoreTheme, THEME_KEY, type ThemeKey, type ThemeSettings } from './settings'

export const useThemeStore = defineStore('theme', () => {
  const settings = ref<ThemeSettings>(restoreTheme())
  const viewport = ref(window.innerWidth)
  const mobileOpen = ref(false)
  const collapsed = ref(false)
  const error = ref('')

  const displaySettings = computed(() => settings.value)

  function apply() {
    applyTheme(settings.value)
    document.body.classList.toggle('lims-sidebar-collapsed', collapsed.value && viewport.value >= 992)
  }

  function save() {
    try {
      localStorage.setItem(THEME_KEY, JSON.stringify({ version: 2, settings: settings.value }))
      error.value = ''
    } catch {
      error.value = '主题已应用，但浏览器存储不可用，刷新后可能无法保留。'
    }
  }

  function set(key: ThemeKey, value: string) {
    settings.value = normalizeSettings({ ...settings.value, [key]: value })
    save()
  }

  function reset() {
    settings.value = { ...defaults }
    collapsed.value = false
    mobileOpen.value = false
    save()
  }

  function toggleMenu() {
    if (viewport.value < 992) {
      mobileOpen.value = !mobileOpen.value
    } else {
      collapsed.value = !collapsed.value
    }
  }

  function resize() {
    viewport.value = window.innerWidth
    if (viewport.value >= 992) mobileOpen.value = false
  }

  watch([settings, viewport, collapsed], apply, { immediate: true, deep: true, flush: 'sync' })

  return { settings, displaySettings, viewport, mobileOpen, collapsed, error, set, reset, toggleMenu, resize }
})
