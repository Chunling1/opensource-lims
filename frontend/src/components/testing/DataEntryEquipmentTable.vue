<script setup lang="ts">
import { computed } from 'vue'
import type { EntryEquipment } from '../../types/testing/dataEntryDetail'
const props = defineProps<{ label: string; rows: EntryEquipment[]; checked: string[]; defaults?: string[]; unavailable?: string[]; disabled?: boolean; catalogue?: boolean; enforceEligibility?: boolean }>()
const columns = computed<[keyof EntryEquipment, string][]>(() => props.catalogue ? [
  ['code', '档案号'], ['name', '设备名称'], ['model', '规格型号'], ['manufacturer', '生产厂家'], ['serial', '仪器出厂号'],
  ['cycle', '周期'], ['status', '设备状态'], ['departmentName', '所属部门'], ['location', '放置地点'], ['inspectionOrganization', '检定单位'], ['remarks', '备注'],
] : [['code', '档案号'], ['name', '设备名称'], ['departmentName', '所属部门'], ['status', '当前状态'], ['lastCalibrationDate', '最近校准日期'], ['validUntil', '有效期至'], ['validityNote', '本次试验适用性'], ['manufacturer', '厂商'], ['serial', '出厂号'], ['model', '规格型号']])
const emit = defineEmits<{ 'update:checked': [string[]]; unavailable: [EntryEquipment] }>()
const unavailable = (row: EntryEquipment) => props.unavailable?.includes(row.id) || (props.enforceEligibility && row.selectable === false)
const selectable = computed(() => props.rows.filter(row => !unavailable(row)))
const all = computed(() => !!selectable.value.length && selectable.value.every(row => props.checked.includes(row.id)))
const some = computed(() => selectable.value.some(row => props.checked.includes(row.id)))
function toggle(id: string, event: Event) {
  const row = props.rows.find(row => row.id === id)
  if (props.disabled || (row && unavailable(row))) {
    (event.target as HTMLInputElement).checked = props.checked.includes(id)
    if (!props.disabled && props.enforceEligibility && row?.selectable === false) emit('unavailable', row)
    return
  }
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
      <th v-for="[key, name] in columns" :key="key" scope="col">{{ name }}</th>
      <th v-if="defaults" scope="col">是否默认</th>
    </tr></thead>
    <tbody>
      <tr v-for="item in rows" :key="item.id" :class="{ 'table-active': checked.includes(item.id) }">
        <td><input type="checkbox" class="form-check-input" :checked="checked.includes(item.id)" :disabled="disabled || props.unavailable?.includes(item.id)" :title="enforceEligibility && item.selectable === false ? item.validityNote : undefined" :aria-label="`选择 ${item.code} ${item.name}`" @click.stop @change="toggle(item.id, $event)" /></td>
        <td v-for="[key] in columns" :key="key">{{ item[key] || (key === 'lastCalibrationDate' || key === 'status' ? '未登记' : '—') }}</td>
        <td v-if="defaults">{{ defaults.includes(item.id) ? '是' : '否' }}</td>
      </tr>
      <tr v-if="!rows.length"><td :colspan="1 + columns.length + (defaults ? 1 : 0)" class="text-muted text-center py-4">暂无{{ label }}</td></tr>
    </tbody>
  </table>
</template>
