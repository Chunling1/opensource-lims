import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useSessionStore } from '@/stores/session'

const DATE_PREFIX = /^(\d{4})-(\d{2})-(\d{2})/

export function businessToday(value = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

export function normalizeWorkflowDate(value: unknown): string {
  if (!value) return ''
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    const year = value.getFullYear()
    const month = String(value.getMonth() + 1).padStart(2, '0')
    const day = String(value.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  const matched = String(value).trim().match(DATE_PREFIX)
  if (!matched) return ''
  const year = Number(matched[1])
  const month = Number(matched[2])
  const day = Number(matched[3])
  const candidate = new Date(year, month - 1, day)
  if (
    candidate.getFullYear() !== year
    || candidate.getMonth() !== month - 1
    || candidate.getDate() !== day
  ) return ''
  return `${matched[1]}-${matched[2]}-${matched[3]}`
}

export function isWorkflowDateValid(value: unknown): boolean {
  return Boolean(normalizeWorkflowDate(value))
}

function dateOrder(value: unknown): number | null {
  const normalized = normalizeWorkflowDate(value)
  if (!normalized) return null
  const [year, month, day] = normalized.split('-').map(Number)
  const candidate = new Date(year, month - 1, day)
  if (
    candidate.getFullYear() !== year
    || candidate.getMonth() !== month - 1
    || candidate.getDate() !== day
  ) return null
  return year * 10_000 + month * 100 + day
}

export function isWorkflowDateBefore(value: unknown, previousDate: unknown): boolean {
  const current = dateOrder(value)
  const previous = dateOrder(previousDate)
  return current !== null && previous !== null && current < previous
}

export function allowAllWorkflowDates(): boolean {
  return false
}

export function useWorkflowDatePolicy(
  previousDate: MaybeRefOrGetter<unknown>,
  requirePrevious: MaybeRefOrGetter<boolean>,
  nextDate: MaybeRefOrGetter<unknown> = '',
  strictOrder: MaybeRefOrGetter<boolean> = false,
) {
  const session = useSessionStore()
  const normalizedPreviousDate = computed(() => normalizeWorkflowDate(toValue(previousDate)))
  const isSuperAdmin = computed(() => session.canOverrideWorkflowDate)
  const normalizedNextDate = computed(() => normalizeWorkflowDate(toValue(nextDate)))
  const canOverride = computed(() => isSuperAdmin.value && !toValue(strictOrder))
  const previousMissing = computed(() => Boolean(toValue(requirePrevious)) && !canOverride.value && !normalizedPreviousDate.value)

  // A new function identity refreshes an already-open calendar after either
  // boundary changes; a closure over refs alone does not notify FlatDatePicker.
  const disabledDate = computed(() => {
    const previous = normalizedPreviousDate.value
    const next = normalizedNextDate.value
    const override = canOverride.value
    return (candidate: Date) => !override && (
      isWorkflowDateBefore(candidate, previous) || isWorkflowDateBefore(next, candidate)
    )
  })

  return {
    disabledDate,
    isSuperAdmin,
    normalizedPreviousDate,
    normalizedNextDate,
    previousMissing,
  }
}
