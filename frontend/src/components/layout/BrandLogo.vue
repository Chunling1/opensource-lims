<script setup lang="ts">
defineProps<{ compact?: boolean; sidebar?: boolean }>()
</script>

<template>
  <RouterLink to="/dashboard" class="navbar-brand navbar-brand-autodark d-inline-flex align-items-center gap-2 text-decoration-none" aria-label="LIMS，返回工作台">
    <span class="avatar avatar-sm bg-primary text-white rounded">
      <i class="ti ti-flask fs-3" aria-hidden="true"></i>
    </span>
    <span v-if="!compact" class="navbar-brand-text fw-bold fs-4">LIMS</span>
  </RouterLink>
</template>
