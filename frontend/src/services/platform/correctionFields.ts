export type Value = string | number | boolean | null | Value[] | { [key: string]: Value }
export type Field = { key: string; label: string; type: string; nullable: boolean; maxLength?: number }
export type Correction = { label: string; fields: Field[]; values: Record<string, Value>; revision: string; warning: string }
export const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export const equal = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
export function changes(original: Correction, draft: Record<string, Value>) {
  return Object.fromEntries(original.fields.filter(f => !equal(original.values[f.key], draft[f.key])).map(f => [f.key, draft[f.key]]))
}
