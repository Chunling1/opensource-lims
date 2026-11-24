<template>
  <div class="card">
    <div v-if="$slots.actions || countLabel || $slots.summary" class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2" role="status"><span class="text-muted">{{ listReadLoading ? '正在加载数据…' : listReadFailed ? '数据加载失败，请重试' : countLabel }}</span><slot name="summary" /></div>
      <TemplateBusinessActions v-if="$slots.actions" :label="ariaLabel"><slot name="actions" /></TemplateBusinessActions>
    </div>
    <form v-if="$slots.filters || statusOptions.length || showSearch || showReset" class="card-body" :aria-label="ariaLabel" @submit.prevent="$emit('search')">
      <QueryFormLayout><TemplateFilterFields><slot name="filters" />
        <el-select v-if="statusOptions.length" clearable :model-value="statusModelValue" :aria-label="statusAriaLabel" :placeholder="statusPlaceholder" @update:model-value="$emit('update:statusModelValue', String($event ?? ''))" @change="$emit('statusChange')"><el-option v-for="option in statusOptions" :key="option" :label="option" :value="option" /></el-select>
      </TemplateFilterFields><template #actions><button v-if="showSearch" type="submit" class="btn btn-primary text-nowrap" :disabled="searchLoading || searchDisabled"><i class="ti ti-search me-1" aria-hidden="true"></i>{{ searchLabel }}</button><button v-if="showReset" type="button" class="btn btn-light" @click="$emit('reset')">重置</button></template></QueryFormLayout>
    </form>
  </div>
</template>
<script setup lang="ts">
import { listReadLoading, listReadFailed } from '@/services/listReadState'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'
import { TemplateFilterFields, TemplateBusinessActions } from '../../platformUi/layouts'

withDefaults(
  defineProps<{
    countLabel?: string
    ariaLabel?: string
    showSearch?: boolean
    showReset?: boolean
    searchLabel?: string
    searchLoading?: boolean
    searchDisabled?: boolean
    statusModelValue?: string
    statusOptions?: string[]
    statusPlaceholder?: string
    statusAriaLabel?: string
  }>(),
  {
    countLabel: '',
    ariaLabel: '列表筛选与操作',
    showSearch: false,
    showReset: false,
    searchLabel: '搜索',
    searchLoading: false,
    searchDisabled: false,
    statusModelValue: '',
    statusOptions: () => [],
    statusPlaceholder: '全部数据状态',
    statusAriaLabel: '数据状态筛选',
  },
)

defineEmits<{
  search: []
  reset: []
  statusChange: []
  'update:statusModelValue': [value: string]
}>()
</script>
