<template>
  <el-table ref="tableRef" :data="rows" border height="100%" highlight-current-row @selection-change="onSelectionChange" @row-click="toggleRow">
    <el-table-column type="selection" width="42" />
    <el-table-column prop="sampleNo" label="样品编号" min-width="150" />
    <el-table-column prop="reportNo" label="报告编号" min-width="150" />
    <el-table-column prop="project" label="检测项目" min-width="130" />
    <el-table-column prop="client" label="委托单位" min-width="150" />
    <el-table-column prop="projectName" label="工程名称" min-width="150" />
    <el-table-column prop="status" label="当前状态" min-width="130" />
    <el-table-column label="标记" width="90">
      <template #default="{ row }">
        <el-tag :type="tagType(row.tag)" size="small">{{ row.tag }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="owner" label="责任人" width="100" />
    <el-table-column prop="date" label="委托日期" width="120" />
    <template v-if="showFlowInfo">
      <el-table-column prop="dataStatus" label="数据状态" min-width="130" />
      <el-table-column prop="inboundPerson" label="入库人" width="110" />
      <el-table-column prop="inboundTime" label="入库时间" min-width="160" />
      <el-table-column prop="pickupPerson" label="出库领取人" width="120" />
      <el-table-column prop="pickupTime" label="出库领取时间" min-width="160" />
      <el-table-column prop="sampleDisposition" label="样品处置" min-width="140" />
    </template>
  </el-table>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { sampleRows } from '@/data/mock'

withDefaults(
  defineProps<{
    rows?: Record<string, unknown>[]
    showFlowInfo?: boolean
  }>(),
  { rows: () => sampleRows as unknown as Record<string, unknown>[] },
)

const emit = defineEmits<{
  view: [Record<string, unknown>]
  edit: [Record<string, unknown>]
  select: [Record<string, unknown>]
  selection: [Record<string, unknown>[]]
}>()

type TableSelectionRef<T> = { toggleRowSelection: (row: T, selected?: boolean) => void }
const tableRef = ref<TableSelectionRef<Record<string, unknown>> | null>(null)

function onSelectionChange(selection: Record<string, unknown>[]) {
  emit('selection', selection)
  const last = selection[selection.length - 1]
  if (last) emit('select', last)
}

function toggleRow(row: Record<string, unknown>) {
  tableRef.value?.toggleRowSelection(row)
}

function tagType(tag: string) {
  if (tag === '超期') return 'danger'
  if (tag === '加急') return 'warning'
  if (tag === '正常') return 'success'
  return 'primary'
}
</script>
