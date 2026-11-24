<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ErrorPage from '../../components/common/ErrorPage.vue'
import { errorForStatus } from '../../services/common/errors'
const route = useRoute()
const error = computed(() => errorForStatus(Number(route.meta.errorStatus || route.params.code || 404)))
</script>
<template><ErrorPage :back-to="route.meta.layout === 'standalone' ? '/dashboard' : undefined" back-label="返回工作台" :error="error" :standalone="route.meta.layout === 'standalone'" :title="error.status === 404 ? '页面不存在' : undefined" /></template>
