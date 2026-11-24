<script setup lang="ts" generic="T">
import { computed } from 'vue'
import { formCondition, type FormField } from '../../types/forms'
const props = defineProps<{ field: FormField<T>; model: T; readonly?: boolean; disabled?: boolean; error?: string }>()
const locked = computed(() => !!props.readonly || formCondition(props.field.readonly, props.model))
const disabled = computed(() => !!props.disabled || formCondition(props.field.disabled, props.model))
const describedBy = computed(() => [props.field.hint ? `${props.field.id}-hint` : '', props.error ? `${props.field.id}-error` : ''].filter(Boolean).join(' ') || undefined)
const value = computed(() => props.field.control === 'custom' ? '' : props.field.binding.get(props.model))
function write(event: Event) {
  if (locked.value || disabled.value) return
  const field = props.field, input = event.target as HTMLInputElement
  if (field.control === 'checkbox') field.binding.set?.(props.model, input.checked)
  else if (field.control === 'boolean-select') field.binding.set?.(props.model, input.value === 'true')
  else if (field.control !== 'custom') field.binding.set?.(props.model, input.value)
}
</script>
<template>
  <textarea v-if="field.control === 'textarea'" :id="field.id" class="form-control" :class="{ 'bg-light': !locked && formCondition(field.muted, model), 'bg-body-tertiary': locked, 'is-invalid': !!error }" :value="String(value)" :rows="field.rows || 2" :maxlength="field.maxlength" :placeholder="field.placeholder" :readonly="locked" :disabled="disabled" :required="field.required" :aria-describedby="describedBy" :aria-invalid="!!error || undefined" @input="write"></textarea>
  <select v-else-if="field.control === 'select'" :id="field.id" class="form-select" :class="{ 'is-invalid': !!error }" :value="String(value)" :disabled="disabled || locked" :required="field.required" :aria-describedby="describedBy" :aria-invalid="!!error || undefined" @change="write"><option v-if="field.emptyLabel !== undefined" value="">{{ field.emptyLabel }}</option><option v-if="locked && value && !field.options.some(option => option.value === String(value))" :value="String(value)">{{ value }}</option><option v-for="option in field.options" :key="option.value" :value="option.value" :disabled="option.disabled">{{ option.label }}</option></select>
  <select v-else-if="field.control === 'boolean-select'" :id="field.id" class="form-select" :value="String(value)" :disabled="disabled || locked" :aria-describedby="describedBy" @change="write"><option v-for="option in field.options || [{ value: false, label: '否' }, { value: true, label: '是' }]" :key="String(option.value)" :value="String(option.value)">{{ option.label }}</option></select>
  <template v-else-if="field.control === 'checkbox'">
    <input :id="field.id" class="btn-check" type="checkbox" :checked="!!value" :disabled="disabled || locked" :required="field.required" :aria-describedby="describedBy" :aria-invalid="!!error || undefined" @change="write" />
    <label :for="field.id" class="btn btn-outline-primary w-100 text-start d-flex align-items-center gap-2 text-break">
      <i :class="value ? 'ti ti-square-check' : 'ti ti-square'" aria-hidden="true"></i>
      <span>{{ field.label }}<span v-if="field.required && field.requiredMark !== false && !locked" class="text-danger"> *</span></span>
    </label>
  </template>
  <input v-else-if="field.control !== 'custom'" :id="field.id" class="form-control" :class="{ 'bg-light': !locked && formCondition(field.muted, model), 'bg-body-tertiary': locked, 'is-invalid': !!error }" :type="field.control" :value="String(value)" :min="field.min" :max="field.max" :step="field.step" :maxlength="field.maxlength" :placeholder="field.placeholder" :readonly="locked" :disabled="disabled" :required="field.required" :aria-describedby="describedBy" :aria-invalid="!!error || undefined" @input="write" />
</template>
