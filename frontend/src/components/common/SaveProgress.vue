<script setup lang="ts">
defineProps<{ active: boolean; percent?: number }>()
</script>
<template>
  <div v-if="active" class="me-auto d-flex align-items-center gap-2 text-primary" role="status" aria-live="polite" aria-atomic="true">
    <span class="spinner-border spinner-border-sm flex-shrink-0" aria-hidden="true"></span>
    <span>{{ percent === undefined ? '正在准备传输…' : percent >= 100 ? '传输完成，正在保存…' : `正在传输 ${percent}%` }}</span>
  </div>
</template>
