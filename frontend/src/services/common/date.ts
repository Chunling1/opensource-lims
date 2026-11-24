export function clientToday() {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/** Previous calendar month, clamped to its last day when needed. */
export function clientMonthRange(date = new Date()) {
  const format = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  const from = new Date(date.getFullYear(), date.getMonth() - 1, 1)
  from.setDate(Math.min(date.getDate(), new Date(date.getFullYear(), date.getMonth(), 0).getDate()))
  return { from: format(from), to: format(date) }
}

/** Local calendar year; clamp February 29 to February 28 in the previous year. */
export function clientYearRange(date = new Date()) {
  const format = (value: Date) => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
  const year = date.getFullYear() - 1, month = date.getMonth()
  const day = Math.min(date.getDate(), new Date(year, month + 1, 0).getDate())
  return { from: format(new Date(year, month, day)), to: format(date) }
}
