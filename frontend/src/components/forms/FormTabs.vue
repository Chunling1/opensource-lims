<script setup lang="ts">
import ScrollableTabs from '../common/ScrollableTabs.vue'
import type { FormTab } from '../../types/forms'
defineProps<{ tabs: readonly FormTab[]; modelValue: string; label: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>
<template>
  <ScrollableTabs :tabs="tabs" :model-value="modelValue" :label="label" :disabled="disabled" variant="pills" @update:model-value="emit('update:modelValue', $event)" />
</template>
