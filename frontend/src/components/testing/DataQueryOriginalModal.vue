<script setup lang="ts">
import BootstrapModal from '../common/BootstrapModal.vue'
import OriginalRecordsWorkspace from './OriginalRecordsWorkspace.vue'
import type { DataQueryRow } from '../../types/testing/dataQuery'
defineProps<{ sample: DataQueryRow }>()
defineEmits<{ close: [] }>()
</script>
<template>
  <BootstrapModal open title="原始记录预览" size="xl" scrollable compact @close="$emit('close')">
    <OriginalRecordsWorkspace :sample-id="sample.id" :preview-title="`${sample.code} · ${sample.name}`" active readonly preview-only compact />
    <template #footer><button type="button" class="btn btn-light" @click="$emit('close')">关闭</button></template>
  </BootstrapModal>
</template>
