<template>
  <!--
    模块内的页面切换统一由左侧业务导航承担。
    保留本兼容组件是为了让现有页面无需一次性改动路由装配，但它不再输出第二套横向目录。
  -->
</template>

<script setup lang="ts">
import type { PageConfig } from '@/data/modules'

defineProps<{
  pages: PageConfig[]
  activeKey: string
}>()
</script>
