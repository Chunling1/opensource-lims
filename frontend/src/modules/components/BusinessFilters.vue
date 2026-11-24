<template>
  <ModuleCommandBar
    :count-label="`显示 ${total} 条结果`"
    aria-label="列表筛选"
    show-search
    :show-reset="hasActiveFilters"
    :status-model-value="state.status"
    :status-options="statusOptions"
    @search="emitChange"
    @reset="onReset"
    @update:status-model-value="state.status = $event"
    @status-change="emitChange"
  >
    <template #filters>
      <el-input
        v-model="state.keyword"
        
        clearable
        aria-label="关键词"
        :placeholder="keywordPlaceholder"
        @clear="emitChange"
        @keyup.enter="emitChange"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <FlatDatePicker
        v-if="showDate"
        v-model="state.dateRange"
        mode="range"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        aria-label="日期范围"
        @change="emitChange"
      />
      <slot name="filters" />
    </template>
    <template v-if="$slots.actions" #actions><slot name="actions" /></template>
  </ModuleCommandBar>
</template>

<script setup lang="ts">
import { useLiveSearch } from '@/composables/liveSearch'
import { computed } from 'vue'
import { Search } from '@element-plus/icons-vue'
import FlatDatePicker from '@/components/FlatDatePicker.vue'
import ModuleCommandBar from '@/components/ModuleCommandBar.vue'
import type { FilterState } from '@/composables/tableFilter'

const props = withDefaults(
  defineProps<{
    state: FilterState
    statusOptions: string[]
    total: number
    showDate?: boolean
    keywordPlaceholder?: string
  }>(),
  {
    showDate: true,
    keywordPlaceholder: '关键词搜索（编号 / 单位 / 名称）',
  },
)

const emit = defineEmits<{
  change: []
  reset: []
}>()

const hasActiveFilters = computed(
  () => Boolean(props.state.keyword.trim() || props.state.status || props.state.dateRange?.some(Boolean)),
)

function emitChange() {
  emit('change')
}

function onReset() {
  emit('reset')
}
useLiveSearch(() => props.state.keyword, emitChange)
</script>
