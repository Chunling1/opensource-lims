<script setup lang="ts" generic="T">
import { useSlots, watchEffect } from 'vue'
import FormControl from './FormControl.vue'
import { formCondition, validateFormSchema, type FormSchema, type FormField } from '../../types/forms'
const props = defineProps<{ schema: FormSchema<T>; model: T; readonly?: boolean; errors?: Readonly<Record<string, string | undefined>> }>()
const slots = useSlots()
if (import.meta.env.DEV) watchEffect(() => validateFormSchema(props.schema, Object.keys(slots)))
const error = (field: FormField<T>) => props.errors?.[field.errorKey || field.id]
</script>
<template>
  <template v-for="section in schema.sections" :key="section.id">
    <section v-if="formCondition(section.visible, model, true)" class="card" :aria-label="section.title">
      <div class="card-header"><h5 class="card-title mb-0">{{ section.title }}</h5></div>
      <div class="card-body"><div class="row g-3">
        <div v-if="section.slot" class="col-12"><slot :name="section.slot" :model="model" :readonly="readonly" /></div>
        <template v-else v-for="field in section.fields" :key="field.id">
          <div v-if="formCondition(field.visible, model, true)" :class="field.width || 'col-md-6 col-xl-4'">
            <slot name="before-field" :field="field" :model="model" />
            <slot v-if="!field.ownLabel && field.control !== 'checkbox'" :name="field.labelSlot || 'label'" :field="field" :model="model">
              <label :for="field.id" class="form-label" :class="{ 'visually-hidden': formCondition(field.labelHidden, model) }">{{ field.label }}<span v-if="field.required && field.requiredMark !== false && !readonly" class="text-danger"> *</span><small v-if="field.labelNote" class="text-muted ms-2 fw-normal">{{ field.labelNote }}</small></label>
            </slot>
            <fieldset :disabled="formCondition(field.disabled, model)">
              <slot v-if="field.control === 'custom'" :name="field.slot" :field="field" :model="model" :readonly="readonly || formCondition(field.readonly, model)" :disabled="formCondition(field.disabled, model)" :error="error(field)" />
              <FormControl v-else :field="field" :model="model" :readonly="readonly" :error="error(field)" />
            </fieldset>
            <div v-if="field.hint" :id="`${field.id}-hint`" class="form-text">{{ field.hint }}</div>
            <div v-if="error(field)" :id="`${field.id}-error`" class="invalid-feedback d-block" role="alert">{{ error(field) }}</div>
            <slot name="after-field" :field="field" :model="model" />
          </div>
        </template>
      </div></div>
    </section>
  </template>
</template>
