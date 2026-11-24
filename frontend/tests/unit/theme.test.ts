// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { applyTheme, defaults, normalizeSettings } from '../../src/stores/theme/settings'

describe('Tabler theme configuration', () => {
  it('rejects unrecognized values and keeps known values', () => {
    expect(normalizeSettings(null)).toEqual(defaults)
    expect(normalizeSettings({ mode: 'dark', colors: 'green', sidebar: '__proto__', unknown: 'x' })).toEqual({
      ...defaults,
      mode: 'dark',
      colors: 'green',
    })
  })

  it('applies Tabler Bootstrap theme mode and primary color attributes', () => {
    applyTheme({ ...defaults, mode: 'dark', colors: 'purple' })
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('dark')
    expect(document.documentElement.getAttribute('data-lims-primary')).toBe('purple')

    applyTheme({ ...defaults, mode: 'light', colors: 'default' })
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('light')
    expect(document.documentElement.getAttribute('data-lims-primary')).toBeNull()
  })
})
