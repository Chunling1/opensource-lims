<script setup lang="ts">
import { computed } from 'vue'
import type { ReportChangeCandidate } from '../../types/reports/reportChange'
const props = defineProps<{ label: string; rows: ReportChangeCandidate[]; checked: string[]; disabled?: boolean; unavailable?: string[] }>()
const emit = defineEmits<{ 'update:checked': [string[]] }>()
const selectable = computed(() => props.rows.filter(row => !props.unavailable?.includes(row.id)))
const all = computed(() => !!selectable.value.length && selectable.value.every(row => props.checked.includes(row.id)))
const some = computed(() => selectable.value.some(row => props.checked.includes(row.id)))
function toggle(id: string) {
  if (props.disabled || props.unavailable?.includes(id)) return
  emit('update:checked', props.checked.includes(id) ? props.checked.filter(value => value !== id) : [...props.checked, id])
}
function toggleAll() {
  if (props.disabled) return
  const ids = selectable.value.map(row => row.id)
  emit('update:checked', all.value ? props.checked.filter(id => !ids.includes(id)) : [...new Set([...props.checked, ...ids])])
}
</script>
<template>
  <table class="table table-striped table-hover table-nowrap align-middle mb-0" :aria-label="`${label}列表`">
    <thead class="table-light"><tr>
      <th scope="col"><input type="checkbox" class="form-check-input" :aria-label="`全选当前页${label}`" :checked="all" :indeterminate="some && !all" :disabled="disabled || !selectable.length" @change="toggleAll" /></th>
      <th scope="col">合同编号</th><th scope="col">报告编号</th><th scope="col">样品编号</th><th scope="col">委托编号</th>
    </tr></thead>
    <tbody>
      <tr v-for="item in rows" :key="item.id" :class="{ 'table-active': checked.includes(item.id) }">
        <td><input type="checkbox" class="form-check-input" :checked="checked.includes(item.id)" :disabled="disabled || unavailable?.includes(item.id)" :aria-label="`选择 ${item.code}`" @click.stop @change="toggle(item.id)" /></td>
        <td>{{ item.contractCode || '—' }}</td><td>{{ item.reportCode }}</td><td>{{ item.code }}</td><td>{{ item.commissionCode || '—' }}</td>
      </tr>
      <tr v-if="!rows.length"><td colspan="5" class="text-muted text-center py-4">暂无{{ label }}</td></tr>
    </tbody>
  </table>
</template>
