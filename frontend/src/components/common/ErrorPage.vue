<script setup lang="ts">
import ErrorContent from './ErrorContent.vue'
import type { AppError } from '../../services/common/errors'
defineProps<{ error: AppError; standalone?: boolean; retry?: boolean; backTo?: string; backLabel?: string; title?: string; busy?: boolean }>()
defineEmits<{ retry: [] }>()
</script>
<template>
  <main v-if="standalone" class="auth-page-wrapper py-5 d-flex justify-content-center align-items-center min-vh-100"><div class="auth-page-content overflow-hidden p-0"><div class="container"><ErrorContent v-bind="$props" @retry="$emit('retry')" /></div></div></main>
  <div v-else class="card"><div class="card-body"><ErrorContent v-bind="$props" @retry="$emit('retry')" /></div></div>
</template>
