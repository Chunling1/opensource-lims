<script setup lang="ts">
import type { SampleRow } from '@/services/pipeline'
defineProps<{ row?: SampleRow }>()
</script>
<template>
  <dl class="row g-3 mb-0">
    <div class="col-12 col-sm-6"><dt class="text-muted fw-normal small mb-1">样品编号</dt><dd class="fw-semibold mb-0 text-break">{{ row?.sampleNo || '—' }}</dd></div>
    <div class="col-12 col-sm-6"><dt class="text-muted fw-normal small mb-1">报告编号</dt><dd class="fw-semibold mb-0 text-break">{{ row?.reportNo || '—' }}</dd></div>
    <div class="col-12 col-sm-6"><dt class="text-muted fw-normal small mb-1">委托单位</dt><dd class="mb-0 text-break">{{ row?.client || '—' }}</dd></div>
    <div class="col-12 col-sm-6"><dt class="text-muted fw-normal small mb-1">检测项目</dt><dd class="mb-0 text-break">{{ row?.project || '—' }}</dd></div>
  </dl>
</template>
