<template><PageHeading :title="title" :section="moduleName" /><div v-if="$slots.default" class="d-flex flex-wrap align-items-center gap-2 mb-3"><slot /></div><p v-if="description" class="text-muted">{{ description }}</p></template>
<script setup lang="ts">
import PageHeading from '../../components/common/PageHeading.vue'
defineProps<{
  title: string
  areaName: string
  moduleName: string
  path?: string
  description?: string
}>()
</script>
