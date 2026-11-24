<template>
  <el-card shadow="never" >
    <template #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
        <strong>{{ workflow.title }}</strong>
        <span class="text-muted">{{ workflow.note }}</span>
      </div>
    </template>
    <div ref="workflowRef" class="d-flex flex-wrap gap-3">
      <div
        v-for="(step, index) in workflow.steps"
        :key="step"
        class="d-flex flex-wrap align-items-center justify-content-between gap-2 p-3 border rounded" data-ui="flow-node"
        :class="{ 'text-success': index < activeIndex, 'border-primary': index === activeIndex }"
      >
        <strong>{{ index + 1 }}. {{ step }}</strong>
        <el-tag :type="tagType(index)" size="small">
          {{ tagText(index) }}
        </el-tag>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { workflowProfiles } from '@/data/mock'

const route = useRoute()
const workflowRef = ref<HTMLElement | null>(null)

const moduleKey = computed(() => String(route.meta.moduleKey ?? 'testing') as keyof typeof workflowProfiles)
const pageKey = computed(() => String(route.meta.pageKey ?? ''))
const workflow = computed(() => workflowProfiles[moduleKey.value] ?? workflowProfiles.testing)
const activeIndex = computed(() => {
  const map = workflow.value.activeByPage as Record<string, number>
  return map[pageKey.value] ?? 0
})

function tagType(index: number) {
  if (index < activeIndex.value) return 'success'
  if (index === activeIndex.value) return 'primary'
  return 'warning'
}

function tagText(index: number) {
  if (index < activeIndex.value) return '已完成'
  if (index === activeIndex.value) return '当前'
  return '待办'
}
</script>
