<script setup lang="ts">
import { computed, ref } from 'vue'
import { flushTablePreferences, preferenceError, preferenceSaving } from '../../../services/platform/tablePreferences'
import BootstrapModal from '../BootstrapModal.vue'
import AdaptiveTableActions, { type ToolbarAction } from './AdaptiveTableActions.vue'
import type { TableColumn } from '../../../types/common/table'
const props = withDefaults(defineProps<{ label: string; columns: readonly Pick<TableColumn, 'key' | 'label' | 'required' | 'group'>[]; selected: readonly string[]; count: number; exportDisabled: boolean; adaptiveActions?: readonly ToolbarAction[] }>(), { adaptiveActions: () => [] })
const emit = defineEmits<{ column: [key: string, checked: boolean]; reset: []; export: [selected: boolean]; action: [index: number] }>()
const columnsOpen = ref(false), columnSearch = ref(''), columnGroup = ref('')
const groups = computed(()=>[...new Set(props.columns.map(c=>c.group).filter((v):v is string=>!!v))])
const visibleColumns = computed(()=>props.columns.filter(c=>(!columnGroup.value||c.group===columnGroup.value)&&c.label.includes(columnSearch.value.trim())))
async function finishColumns() { if (await flushTablePreferences()) columnsOpen.value = false }
</script>
<template>
  <AdaptiveTableActions :label="label" :actions="adaptiveActions" :count="count" :export-disabled="exportDisabled" @action="emit('action', $event)" @export="emit('export', $event)" @columns="columnsOpen = true"><template v-if="$slots.default" #default><slot /></template></AdaptiveTableActions>
  <BootstrapModal :open="columnsOpen" :title="`${label}显示列`" size="lg" scrollable @close="finishColumns">
    <template v-if="groups.length">
      <div class="row g-3 mb-3">
        <div class="col-md-7"><label for="column-search" class="form-label">查找字段</label><input id="column-search" v-model="columnSearch" class="form-control" type="search" placeholder="例如：审核、入库、生产单位" /></div>
        <div class="col-md-5"><label for="column-group" class="form-label">业务分组</label><select id="column-group" v-model="columnGroup" class="form-select"><option value="">全部分组</option><option v-for="group in groups" :key="group" :value="group">{{ group }}</option></select></div>
      </div>
      <p class="text-muted small">已选 {{ selected.length }} 项。流程人员及操作时间显示最近一次成功办理记录；未办理或缺少历史记录的项目留空。</p>
      <p v-if="!visibleColumns.length" class="text-muted" role="status">没有匹配字段，请调整关键词或分组。</p>
    </template>
    <div class="row g-3"><div v-for="column in visibleColumns" :key="column.key" class="col-6 col-md-4"><label class="form-check mb-0"><input class="form-check-input" type="checkbox" :checked="selected.includes(column.key)" :disabled="column.required" @change="emit('column', column.key, ($event.target as HTMLInputElement).checked)" /><span class="form-check-label text-break">{{ column.label }}</span></label></div></div>
    <p v-if="preferenceError" class="text-danger mt-3 mb-0" role="alert">{{ preferenceError }} <button class="btn btn-sm btn-link" @click="flushTablePreferences">重试</button></p>
    <template #footer><span v-if="preferenceSaving" class="text-muted me-auto" role="status">正在保存…</span><button class="btn btn-light" @click="emit('reset')">恢复默认</button><button class="btn btn-primary" @click="finishColumns">完成</button></template>
  </BootstrapModal>
</template>
