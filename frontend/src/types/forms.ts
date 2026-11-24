/** UI-only schema. Business APIs and defaults remain in the owning page. */
export type FormCondition<T> = boolean | ((model: T) => boolean)
export interface FormBinding<T, V> { get: (model: T) => V; set?: (model: T, value: V) => void }
export interface FormFieldBase<T> {
  id: string; label: string; width?: string; placeholder?: string; hint?: string; labelNote?: string
  required?: boolean; requiredMark?: boolean; readonly?: FormCondition<T>; disabled?: FormCondition<T>; visible?: FormCondition<T>
  labelHidden?: FormCondition<T>; labelSlot?: string; ownLabel?: boolean; muted?: FormCondition<T>; errorKey?: string
}
type StringControl<T> = { control: 'text' | 'tel' | 'date' | 'number' | 'textarea'; binding: FormBinding<T, string>; maxlength?: number; rows?: number; min?: number | string; max?: number | string; step?: number | 'any' }
type SelectControl<T> = { control: 'select'; binding: FormBinding<T, string>; options: readonly { value: string; label: string; disabled?: boolean }[]; emptyLabel?: string }
type BooleanControl<T> = { control: 'checkbox'; binding: FormBinding<T, boolean> } | { control: 'boolean-select'; binding: FormBinding<T, boolean>; options?: readonly { value: boolean; label: string }[] }
export type FormField<T> = FormFieldBase<T> & (StringControl<T> | SelectControl<T> | BooleanControl<T> | { control: 'custom'; slot: string })
export interface FormSection<T> { id: string; title: string; fields: readonly FormField<T>[]; slot?: string; visible?: FormCondition<T> }
export interface FormSchema<T> { sections: readonly FormSection<T>[] }
export interface FormTab { key: string; label: string; tabId: string; panelId: string }
export function formCondition<T>(condition: FormCondition<T> | undefined, model: T, fallback = false): boolean {
  return typeof condition === 'function' ? condition(model) : condition ?? fallback
}
/** Validate configuration rather than silently dropping an unregistered business control. */
export function validateFormSchema<T>(schema: FormSchema<T>, slots: readonly string[]): void {
  const ids = new Set<string>()
  const unique = (id: string) => { if (!id || ids.has(id)) throw new Error(`Duplicate or empty form ID: ${id}`); ids.add(id) }
  for (const section of schema.sections) {
    unique(section.id)
    if (section.slot && section.fields.length) throw new Error(`Section ${section.id} has two renderers`)
    if (section.slot && !slots.includes(section.slot)) throw new Error(`Missing form slot: ${section.slot}`)
    for (const field of section.fields) {
      unique(field.id)
      if (field.labelSlot && !slots.includes(field.labelSlot)) throw new Error(`Missing form slot: ${field.labelSlot}`)
      if (field.control === 'custom' && !slots.includes(field.slot)) throw new Error(`Missing form slot: ${field.slot}`)
    }
  }
}
/** Same empty/invalid-input behavior as Vue v-model.number, without converting string-valued amounts. */
export function numberInputValue(value: string): number | string {
  const number = Number.parseFloat(value)
  return Number.isNaN(number) ? value : number
}
