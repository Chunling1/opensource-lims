<script setup lang="ts">
import { computed } from 'vue'
import DataTable from '../common/table/DataTable.vue'
import type { TableColumn } from '../../types/common/table'
import type { PersonnelHistory } from '../../types/quality/personnel'
const props = defineProps<{ kind: 'awards' | 'trainings'; rows: PersonnelHistory[]; readonly: boolean; busy?: boolean }>()
defineEmits<{ open: [mode: 'new' | 'edit' | 'view' | 'delete' | 'attachments', row?: PersonnelHistory] }>()
const title = computed(() => props.kind === 'awards' ? '获奖信息' : '继续教育记录')
const columns = computed<TableColumn<keyof PersonnelHistory>[]>(() => props.kind === 'awards' ? [{ key: 'name', label: '获奖名称' }, { key: 'project', label: '获奖项目' }, { key: 'date', label: '获奖日期' }, { key: 'issuer', label: '颁奖单位' }, { key: 'attachments', label: '上传附件' }] : [{ key: 'date', label: '培训时间' }, { key: 'place', label: '培训地点' }, { key: 'content', label: '培训内容' }, { key: 'result', label: '培训结果' }, { key: 'attachments', label: '上传附件' }])
</script>
<template>
  <section :aria-label="title">
    <div class="d-flex align-items-center justify-content-between mb-3"><h6 class="mb-0">{{ title }} <span class="badge bg-light text-body">{{ rows.length }}</span></h6><button v-if="!readonly" type="button" class="btn btn-primary" :disabled="busy" @click="$emit('open', 'new')"><i class="ti ti-plus me-1" aria-hidden="true"></i>新增</button></div>
    <DataTable :label="title" :rows="rows" :columns="columns" :row-key="r => r.id" :row-label="r => kind === 'awards' ? r.name : r.content">
      <template #cell-attachments="{ row }"><button v-if="row.attachments.length" type="button" class="btn btn-link p-0" @click="$emit('open', 'attachments', row)">{{ row.attachments.length }} 个附件</button><span v-else>—</span></template>
      <template #actions="{ row }"><button v-if="!readonly" class="dropdown-item" role="menuitem" :disabled="busy" @click="$emit('open', 'edit', row)">修改</button><button class="dropdown-item" role="menuitem" @click="$emit('open', 'view', row)">查看</button><button v-if="!readonly" class="dropdown-item" role="menuitem" :disabled="busy" @click="$emit('open', 'delete', row)">删除</button><button class="dropdown-item" role="menuitem" @click="$emit('open', 'attachments', row)">附件管理</button></template>
    </DataTable>
  </section>
</template>
