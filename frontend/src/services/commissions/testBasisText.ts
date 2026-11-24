import type { TestBasisStandard } from '../../types/commissions/testBasis'

export function basisLabel(row: Pick<TestBasisStandard, 'code' | 'name'>, english: boolean): string {
  return `${row.code}${english ? '<' : '《'}${row.name}${english ? '>' : '》'}`
}
export function validBasisSeparator(value: unknown, allowEmpty = false): value is string {
  return typeof value === 'string' && (allowEmpty || value.length > 0) && [...value].length <= 2 && /^[\p{P}\p{S}\p{Zs}\n]*$/u.test(value)
}
export function joinBasisText(labels: string[], separators: string[]): string {
  return labels.map((label, index) => (index ? separators[index - 1] ?? '；' : '') + label).join('')
}
// Match the known, ordered labels. Text never determines which standards are selected.
export function readBasisSeparators(text: string, labels: string[]): string[] | null {
  if (!labels.length) return text === '' ? [] : null
  if (!text.startsWith(labels[0]!)) return null
  let position = labels[0]!.length
  const separators: string[] = []
  for (const label of labels.slice(1)) {
    const next = text.indexOf(label, position)
    if (next < 0) return null
    const separator = text.slice(position, next)
    if (!validBasisSeparator(separator, true)) return null
    separators.push(separator); position = next + label.length
  }
  return position === text.length ? separators : null
}
export function retainBasisSeparators(before: string[], separators: string[], after: string[]): string[] {
  return after.slice(1).map((id, index) => {
    const previous = before.indexOf(after[index]!)
    return previous >= 0 && before[previous + 1] === id ? separators[previous] ?? '；' : '；'
  })
}
