<template>
  <PageHeading :title="title" :section="moduleName" />
  <div v-if="$slots['header-actions']" class="d-flex flex-wrap align-items-center gap-2 mb-3"><slot name="header-actions" /></div>
  <slot name="before" />
  <el-alert v-if="notice" :type="noticeType" :title="notice" :closable="noticeClosable" />
  <section v-if="showContent || showCommand && hasCommandContent" class="card">
    <div class="card-header d-flex flex-wrap align-items-center justify-content-between gap-3">
      <div class="d-flex align-items-center gap-2"><h5 class="card-title mb-0"><slot name="content-title">{{ contentTitle || title }}</slot></h5><span v-if="resultCount !== undefined" class="badge bg-primary-subtle text-body">{{ resultCount }}</span><slot name="summary" /></div>
      <TemplateBusinessActions v-if="$slots.actions" :label="title"><slot name="actions" /></TemplateBusinessActions>
      <slot name="content-meta" />
    </div>
    <form v-if="showCommand && ($slots.filters || statusOptions.length)" class="card-body border-bottom" :aria-label="commandAriaLabel" @submit.prevent="$emit('search')">
      <QueryFormLayout>
        <TemplateFilterFields>
          <slot name="filters" />
          <el-select v-if="statusOptions.length" :model-value="statusModelValue" clearable data-filter-label="数据状态" :placeholder="statusPlaceholder" @update:model-value="$emit('update:statusModelValue', $event)" @change="$emit('statusChange')">
            <el-option v-for="status in statusOptions" :key="status" :value="status" :label="status" />
          </el-select>
        </TemplateFilterFields>
        <template #actions>
          <button v-if="showSearch" type="submit" class="btn btn-primary text-nowrap" :disabled="searchLoading || searchDisabled"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button>
          <button v-if="showReset" type="button" class="btn btn-light text-nowrap" @click="$emit('reset')">重置</button>
        </template>
      </QueryFormLayout>
    </form>
    <p v-if="contentDescription" class="text-muted">{{ contentDescription }}</p>
    <slot v-if="showContent" />
    <slot v-if="showContent" name="footer" />
  </section>
  <slot v-if="!showContent" />
  <slot name="after" />
</template>
<script setup lang="ts">
import { computed, useSlots } from 'vue'
import type { PageConfig } from '@/data/modules'
import { TemplateFilterFields, TemplateBusinessActions } from '../../platformUi/layouts'
import PageHeading from '../../components/common/PageHeading.vue'
import QueryFormLayout from '../../components/common/QueryFormLayout.vue'

const props = withDefaults(
  defineProps<{
    title: string
    areaName: string
    moduleName: string
    path?: string
    description?: string
    pages?: PageConfig[]
    activeKey?: string
    notice?: string
    noticeType?: 'success' | 'warning' | 'info' | 'error'
    noticeClosable?: boolean
    countLabel?: string
    commandAriaLabel?: string
    contentTitle?: string
    contentDescription?: string
    variant?: 'list' | 'form' | 'split' | 'experiment'
    showCommand?: boolean
    showContent?: boolean
    showSearch?: boolean
    showReset?: boolean
    searchLoading?: boolean
    searchDisabled?: boolean
    statusModelValue?: string
    statusOptions?: string[]
    statusPlaceholder?: string
  }>(),
  {
    path: '',
    description: '',
    pages: () => [],
    activeKey: '',
    notice: '',
    noticeType: 'info',
    noticeClosable: false,
    countLabel: '',
    commandAriaLabel: '列表筛选与操作',
    contentTitle: '',
    contentDescription: '',
    variant: 'list',
    showCommand: true,
    showContent: true,
    showSearch: true,
    showReset: false,
    searchLoading: false,
    searchDisabled: false,
    statusModelValue: '',
    statusOptions: () => [],
    statusPlaceholder: '全部数据状态',
  },
)

defineEmits<{
  search: []
  reset: []
  statusChange: []
  'update:statusModelValue': [value: string]
}>()

const resultCount = computed(() => { const match=props.countLabel.match(/(?:显示|共)\s*(\d+)\s*条/); return match ? Number(match[1]) : undefined })
const slots = useSlots()
const hasCommandContent = computed(
  () => Boolean(props.countLabel || props.statusOptions.length || slots.filters || slots.summary || slots.actions),
)
</script>
