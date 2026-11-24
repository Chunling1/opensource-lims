<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ id: string; label: string; modelValue: string; error?: string; autocomplete?: string; disabled?: boolean }>()
defineEmits<{ 'update:modelValue': [value: string] }>()
const visible = ref(false)
</script>
<template>
  <div class="mb-3">
    <div v-if="$slots['label-action']" class="float-end"><slot name="label-action" /></div>
    <label class="form-label" :for="id">{{ label }}</label>
    <div class="position-relative auth-pass-inputgroup">
      <!-- Keep the error border without Bootstrap's validation icon, which occupies the eye button's space. -->
      <input :id="id" :value="modelValue" :type="visible ? 'text' : 'password'" class="form-control pe-5" :class="{ 'border-danger': error }" :autocomplete="autocomplete || 'current-password'" :disabled="disabled" :aria-invalid="!!error" :aria-describedby="error ? `${id}-error` : undefined" @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
      <button class="btn btn-link position-absolute end-0 top-0 text-decoration-none text-muted password-addon" type="button" :aria-label="`${visible ? '隐藏' : '显示'}${label}`" :aria-pressed="visible" :disabled="disabled" @click="visible = !visible"><i :class="visible ? 'ti ti-eye-off' : 'ti ti-eye'" aria-hidden="true"></i></button>
    </div>
    <div v-if="error" :id="`${id}-error`" class="invalid-feedback d-block" role="alert">{{ error }}</div>
  </div>
</template>
