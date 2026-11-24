<template>
  <div  :class="{ 'opacity-75': listReadLoading, 'text-danger': !listReadLoading && listReadFailed }" :aria-busy="listReadLoading">
    <div v-if="listReadLoading"  role="status" aria-live="polite">
      <span  aria-hidden="true" />正在加载数据，请稍候…
    </div>
    <div v-else-if="listReadFailed"  role="alert">
      部分数据加载失败，当前列表可能不完整。请重新搜索或刷新页面重试。
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { listReadLoading, listReadFailed } from '@/services/listReadState'
</script>


