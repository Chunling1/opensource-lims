<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ReportCheckView from './ReportCheckView.vue'
import type { ReportStage } from '../../types/reports/reportCheck'
const route = useRoute()
const stage = computed(() => route.path.split('/')[2] as ReportStage)
</script>
<template><ReportCheckView :key="stage" :stage="stage" /></template>
