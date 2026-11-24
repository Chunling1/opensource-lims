<script setup lang="ts">
import BootstrapModal from '../common/BootstrapModal.vue'
import LoadState from '../common/LoadState.vue'
defineProps<{ title: string; embedded?: boolean; loading?: boolean }>()
defineEmits<{ close: [] }>()
</script>
<template>
  <div v-if="embedded" class="d-flex flex-column h-100 overflow-hidden">
    <div class="px-3 flex-shrink-0"><slot name="toolbar" /></div>
    <div class="modal-body px-3 pt-0 overflow-auto" :aria-busy="loading"><LoadState v-if="loading" loading /><slot v-else /></div>
    <div v-if="!loading" class="flex-shrink-0"><slot name="pagination" /></div>
    <div class="modal-footer flex-shrink-0"><slot name="footer" /></div>
  </div>
  <BootstrapModal v-else open :loading="loading" :title="title" size="lg" scrollable fullscreen-mobile fill-height body-class="px-3 pt-0 overflow-auto" @close="$emit('close')">
    <template #toolbar><slot name="toolbar" /></template>
    <slot />
    <template #pagination><slot name="pagination" /></template>
    <template #footer><slot name="footer" /></template>
  </BootstrapModal>
</template>
