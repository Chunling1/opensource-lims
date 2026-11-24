<script setup lang="ts">
import type { RegistrationSample } from '../../types/commissions/registration'
defineProps<{ sample: RegistrationSample }>()
</script>
<template>
  <div class="ms-sm-auto d-flex flex-wrap align-items-center gap-2">
    <span>报告形式</span><output aria-label="报告形式" class="mb-0">{{ sample.details?.reportForm || '纸质' }}</output>
  </div>
</template>
