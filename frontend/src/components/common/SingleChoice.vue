<script setup lang="ts">
defineProps<{ id?: string; name: string; value?: string; checked: boolean; disabled?: boolean; label: string }>()
const emit = defineEmits<{ change: [Event] }>()
</script>
<template>
  <!-- Keep native radio grouping, focus and arrow keys; template utilities supply the square/check appearance. -->
  <span class="position-relative d-inline-flex align-middle flex-shrink-0" @click.stop>
    <input :id="id" type="radio" class="form-check-input rounded-1 bg-gradient fs-4 m-0" :name="name" :value="value" :checked="checked" :disabled="disabled" :aria-label="label" @change="emit('change', $event)" />
    <i v-if="checked" class="ti ti-check position-absolute top-50 start-50 translate-middle text-white fs-4 lh-1 pe-none" :class="{ 'opacity-50': disabled }" aria-hidden="true"></i>
  </span>
</template>
