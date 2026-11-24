<template>
  <div class="row g-2 align-items-end mb-3">
    <div class="col-12 col-md-4">
    <el-select :model-value="modelValue.codes" multiple clearable collapse-tags collapse-tags-tooltip placeholder="筛选项目编号" aria-label="筛选项目编号" @update:model-value="update('codes', $event)">
      <el-option v-for="code in codes" :key="code" :label="code" :value="code" />
    </el-select>
    </div>
    <div class="col-12 col-md-4">
    <el-select :model-value="modelValue.departments" multiple clearable collapse-tags collapse-tags-tooltip placeholder="筛选项目归属部门" aria-label="筛选项目归属部门" @update:model-value="update('departments', $event)">
      <el-option v-for="dept in departments" :key="dept" :label="dept || '未设置部门'" :value="dept" />
    </el-select>
    </div>
    <div class="col-12 col-md-4">
    <el-select :model-value="modelValue.locations" multiple clearable collapse-tags collapse-tags-tooltip placeholder="筛选地点" aria-label="筛选地点" @update:model-value="update('locations', $event)">
      <el-option v-for="location in locations" :key="location" :label="location || '未设置地点'" :value="location" />
    </el-select>
    </div>
    <div class="col-12 d-flex justify-content-end">
    <el-button @click="emit('update:modelValue', emptyProjectFilter())">重置筛选</el-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { emptyProjectFilter, type FilterableProject, type ProjectFilter } from '@/data/projectAuthorizationFilter'
const props = defineProps<{ modelValue: ProjectFilter; projects: FilterableProject[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: ProjectFilter] }>()
const unique = (values: string[]) => [...new Set(values)].sort((a, b) => a.localeCompare(b, 'zh-CN', { numeric: true }))
const codes = computed(() => unique(props.projects.map(p => p.code)))
const departments = computed(() => unique(props.projects.map(p => p.department)))
const locations = computed(() => unique(props.projects.map(p => p.location || '')))
function update(key: keyof ProjectFilter, value: string[]) { emit('update:modelValue', { ...props.modelValue, [key]: value }) }
</script>

