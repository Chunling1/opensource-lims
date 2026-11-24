<script setup lang="ts">
import { computed } from 'vue'
import type { EnvironmentPlan } from '../../types/quality/testEnvironments'
const props = defineProps<{ label: string; rows: EnvironmentPlan[]; checked: string[]; selectable?: (row: EnvironmentPlan) => boolean }>()
const emit = defineEmits<{ 'update:checked': [string[]] }>()
const canSelect = (row: EnvironmentPlan) => props.selectable?.(row) ?? true
const eligible = computed(() => props.rows.filter(canSelect))
const all = computed(() => !!eligible.value.length && eligible.value.every(row => props.checked.includes(row.id)))
const some = computed(() => eligible.value.some(row => props.checked.includes(row.id)))
function toggle(row: EnvironmentPlan) {
  if (!canSelect(row)) return
  emit('update:checked', props.checked.includes(row.id) ? props.checked.filter(id => id !== row.id) : [...props.checked, row.id])
}
function toggleAll() {
  const ids = eligible.value.map(row => row.id)
  emit('update:checked', all.value ? props.checked.filter(id => !ids.includes(id)) : [...new Set([...props.checked, ...ids])])
}
</script>
<template>
  <!-- Match DataEntryEquipmentTable: dense striped rows, page selection, and active selection styling. -->
  <table class="table table-striped table-hover table-nowrap align-middle mb-0" :aria-label="`${label}列表`">
    <thead class="table-light"><tr>
      <th scope="col"><input type="checkbox" class="form-check-input" :aria-label="`全选当前页${label}`" :checked="all" :indeterminate="some && !all" :disabled="!eligible.length" @change="toggleAll" /></th>
      <th scope="col">检测方案</th><th scope="col">方案代码</th>
    </tr></thead>
    <tbody>
      <tr v-for="row in rows" :key="row.id" :class="{ 'table-active': checked.includes(row.id) }">
        <td><input type="checkbox" class="form-check-input" :checked="checked.includes(row.id)" :disabled="!canSelect(row)" :aria-label="`选择 ${row.code} ${row.name}`" @click.stop @change="toggle(row)" /></td>
        <td>{{ row.name || '—' }}</td><td>{{ row.code || '—' }}</td>
      </tr>
      <tr v-if="!rows.length"><td colspan="3" class="text-muted text-center py-4">暂无{{ label }}</td></tr>
    </tbody>
  </table>
</template>
