import { ref, watch, type Ref } from 'vue'
import { profile } from './auth'
import { getSessionToken, platformRequest } from './http'

type Settings = Record<string, any>
const saved = ref<Record<string, Settings>>({})
const session = ref('')
const dirty = new Map<string, Settings>()
export const preferenceError = ref('')
export const preferenceSaving = ref(false)
let running: Promise<void> | undefined
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value))

watch(profile, value => {
  const identity = value ? `${value.account}:${getSessionToken()}` : ''
  if (identity === session.value) return
  dirty.clear()
  saved.value = copy(value?.uiPreferences || {})
  preferenceError.value = ''
  session.value = identity
}, { immediate: true, flush: 'sync' })

async function savePending() {
  const owner = session.value
  preferenceSaving.value = true
  preferenceError.value = ''
  try {
    while (dirty.size && owner && owner === session.value) {
      const [key, settings] = dirty.entries().next().value!
      await platformRequest('/api/auth/ui-preferences', { method: 'PUT', body: { key, settings } })
      if (owner !== session.value) break
      if (dirty.get(key) === settings) dirty.delete(key)
    }
  } catch {
    if (owner === session.value) preferenceError.value = '显示设置未保存，请重试。'
  } finally { preferenceSaving.value = false }
}

export async function flushTablePreferences(): Promise<boolean> {
  do {
    if (!running) running = savePending().finally(() => { running = undefined })
    await running
  } while (dirty.size && session.value && !preferenceError.value)
  return dirty.size === 0
}

/** Persist only table presentation, never selected records, filters or authorization. */
export function persistTableSettings(key: () => string, fields: Record<string, Ref<any>>, addedColumns: string[] = []) {
  const defaults = Object.fromEntries(Object.entries(fields).filter(([, field]) => field.value !== undefined).map(([name, field]) => [name, copy(field.value)]))
  let restoring = false
  watch([key, session], () => {
    restoring = true
    const settings = saved.value[key()] || {}
    for (const [name, value] of Object.entries(defaults)) fields[name]!.value = copy(settings[name] ?? value)
    const introduced = new Set<string>(settings.introducedColumns || [])
    const missing = addedColumns.filter(column => !introduced.has(column))
    if (missing.length && fields.columns) {
      fields.columns.value = [...new Set([...fields.columns.value, ...missing])]
      if (session.value) {
        const updated = {...settings, columns: copy(fields.columns.value), introducedColumns: [...introduced, ...missing]}
        saved.value[key()] = updated
        dirty.set(key(), updated)
        void flushTablePreferences()
      }
    }
    restoring = false
  }, { immediate: true, flush: 'sync' })
  watch(() => Object.fromEntries(Object.entries(fields).filter(([, field]) => field.value !== undefined).map(([name, field]) => [name, field.value])), settings => {
    if (restoring || !session.value) return
    const value = {...copy(saved.value[key()] || {}), ...copy(settings)}
    saved.value[key()] = value
    dirty.set(key(), value)
    void flushTablePreferences()
  }, { deep: true, flush: 'sync' })
}
