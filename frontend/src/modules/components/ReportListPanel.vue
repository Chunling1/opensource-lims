<template>
  <el-card shadow="never" >
    <template #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-2"><strong>{{ title }}</strong><el-tag size="small">{{ filtered.length }} 条</el-tag></div>
    </template>
    <div >
      <el-input v-model="kw" clearable :placeholder="placeholder" aria-label="搜索列表">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-select v-if="statusOptions && statusOptions.length" v-model="statusSel" clearable placeholder="全部状态">
        <el-option v-for="o in statusOptions" :key="o" :label="o" :value="o" />
      </el-select>
      <el-button v-if="kw || statusSel" link type="primary" @click="resetFilters">重置</el-button>
    </div>
    <button
      v-for="row in paged"
      :key="String(row[rowKey])"
      type="button"
      class="list-group-item list-group-item-action"
      :class="{ active: row[rowKey] === selected }"
      :aria-pressed="row[rowKey] === selected"
      @click="$emit('select', String(row[rowKey]))"
    >
      <span v-if="row.rowProjection === 'recall'" >
        可撤回记录
      </span>
      <slot name="item" :row="row" />
    </button>
    <el-empty v-if="!filtered.length" :description="emptyText" :image-size="60" />
    <el-pagination
      v-model:current-page="page"
      small
      layout="prev, pager, next"
      :total="filtered.length"
      :page-size="pageSize"
      
    />
  </el-card>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { computed, ref, watch } from 'vue'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Row = Record<string, any>
const props = withDefaults(
  defineProps<{
    title: string
    rows: Row[]
    selected?: string
    rowKey?: string
    searchFields?: string[]
    placeholder?: string
    statusOptions?: string[]
    statusField?: string
    initialKeyword?: string
    emptyText?: string
  }>(),
  { rowKey: 'reportNo', searchFields: () => [], placeholder: '搜索', statusField: 'status', emptyText: '无匹配数据' },
)
defineEmits<{ select: [string] }>()

const pageSize = 5
const page = ref(1)
const kw = ref(props.initialKeyword ?? '')
const statusSel = ref('')
watch(() => props.initialKeyword, (v) => { kw.value = v ?? '' })

const filtered = computed(() =>
  props.rows.filter((r) => {
    const keyword = kw.value.trim().toLocaleLowerCase()
    const okKw = !keyword || props.searchFields.some((f) => String(r[f] ?? '').toLocaleLowerCase().includes(keyword))
    const okSt = !statusSel.value || String(r[props.statusField] ?? '') === statusSel.value
    return okKw && okSt
  }),
)
watch([kw, statusSel], () => { page.value = 1 })
watch(() => filtered.value.length, () => { if ((page.value - 1) * pageSize >= filtered.value.length) page.value = 1 })
const paged = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))

function resetFilters() {
  kw.value = ''
  statusSel.value = ''
}
</script>
