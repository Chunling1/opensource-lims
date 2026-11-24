// 通用表格筛选：关键词（跨字段模糊）+ 状态 + 日期区间。各模块通过 FilterConfig 声明字段。
import { computed, reactive, type Ref } from 'vue'

export interface FilterState {
  keyword: string
  status: string
  dateRange: [string, string] | null
}

export interface FilterConfig {
  // 状态筛选对应的字段（无则不显示状态下拉）
  statusField?: string
  // 日期筛选对应的字段（无则不显示日期选择）
  dateField?: string
  // 关键词搜索的字段；缺省时搜索所有字符串字段
  keywordFields?: string[]
}

export function createFilterState(): FilterState {
  return reactive({ keyword: '', status: '', dateRange: null }) as FilterState
}

function flattenValues(value: unknown): unknown[] {
  if (Array.isArray(value)) return value.flatMap(flattenValues)
  if (value && typeof value === 'object') return Object.values(value as Record<string, unknown>).flatMap(flattenValues)
  return [value]
}

function matchKeyword(row: Record<string, unknown>, keyword: string, fields?: string[]): boolean {
  const kw = keyword.trim().toLowerCase()
  if (!kw) return true
  const values = fields === undefined
    ? flattenValues(row)
    : fields.flatMap((field) => flattenValues(row[field]))
  return values.some((v) => String(v ?? '').toLowerCase().includes(kw))
}

function matchStatus(row: Record<string, unknown>, status: string, field?: string): boolean {
  if (!status || !field) return true
  return String(row[field] ?? '') === status
}

function matchDate(row: Record<string, unknown>, range: [string, string] | null, field?: string): boolean {
  if (!range || !field) return true
  const [start, end] = range
  if (!start && !end) return true
  const dates = flattenValues(row[field])
    .map((value) => String(value ?? '').slice(0, 10))
    .filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value))
  return dates.some((value) => (!start || value >= start) && (!end || value <= end))
}

export function filterRows<T extends Record<string, unknown>>(
  rows: T[],
  state: FilterState,
  config: FilterConfig,
): T[] {
  return rows.filter(
    (row) =>
      matchKeyword(row, state.keyword, config.keywordFields) &&
      matchStatus(row, state.status, config.statusField) &&
      matchDate(row, state.dateRange, config.dateField),
  )
}

// 从数据中提取某字段的去重选项，用于状态下拉
export function distinctOptions<T extends Record<string, unknown>>(rows: T[], field?: string): string[] {
  if (!field) return []
  const set = new Set<string>()
  for (const row of rows) {
    const v = String(row[field] ?? '').trim()
    if (v) set.add(v)
  }
  return [...set]
}

// 组合式封装：传入源数据(可为 ref)和配置，返回筛选状态、状态选项和筛选结果
export function useTableFilter<T extends Record<string, unknown>>(
  source: Ref<T[]> | (() => T[]),
  config: Ref<FilterConfig> | FilterConfig,
) {
  const state = createFilterState()
  const rows = computed(() => (typeof source === 'function' ? source() : source.value))
  const cfg = computed(() => ('value' in (config as Ref) ? (config as Ref<FilterConfig>).value : (config as FilterConfig)))
  const statusOptions = computed(() => distinctOptions(rows.value, cfg.value.statusField))
  const result = computed(() => filterRows(rows.value, state, cfg.value))

  function reset() {
    state.keyword = ''
    state.status = ''
    state.dateRange = null
  }

  return { state, statusOptions, result, reset, config: cfg }
}
