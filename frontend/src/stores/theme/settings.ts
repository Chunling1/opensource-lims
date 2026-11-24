export const choices = {
  mode: { label: '明暗模式', values: { light: '浅色', dark: '深色' } },
  colors: { label: '主色', values: { default: '默认', green: '绿色', purple: '紫色', blue: '深蓝' } },
  width: { label: '内容宽度', values: { fluid: '流式', boxed: '居中容器' } },
  sidebar: { label: '侧栏外观', values: { dark: '深色', light: '浅色' } },
  preloader: { label: '预加载动画', values: { disable: '关闭', enable: '开启' } },
  user: { label: '侧栏用户菜单', values: { hide: '隐藏', show: '显示' } },
} as const

export type ThemeKey = keyof typeof choices
export type ThemeSettings = { [K in ThemeKey]: keyof typeof choices[K]['values'] }
export const THEME_KEY = 'lims.theme.v2'

export const defaults: ThemeSettings = {
  mode: 'light',
  colors: 'default',
  width: 'fluid',
  sidebar: 'dark',
  preloader: 'disable',
  user: 'hide',
}

export function normalizeSettings(value: unknown): ThemeSettings {
  const result = { ...defaults }
  if (!value || typeof value !== 'object') return result
  for (const key of Object.keys(choices) as ThemeKey[]) {
    const candidate = (value as Record<string, unknown>)[key]
    if (typeof candidate === 'string' && Object.hasOwn(choices[key].values, candidate)) {
      ;(result as Record<string, string>)[key] = candidate
    }
  }
  return result
}

export function restoreTheme(): ThemeSettings {
  try {
    const saved = JSON.parse(localStorage.getItem(THEME_KEY) || 'null')
    return normalizeSettings(saved?.version === 2 ? saved.settings : null)
  } catch {
    return { ...defaults }
  }
}

export function applyTheme(settings: ThemeSettings) {
  document.documentElement.setAttribute('data-bs-theme', settings.mode)
  if (settings.colors === 'default') {
    document.documentElement.removeAttribute('data-lims-primary')
  } else {
    document.documentElement.setAttribute('data-lims-primary', settings.colors)
  }
  return settings
}
