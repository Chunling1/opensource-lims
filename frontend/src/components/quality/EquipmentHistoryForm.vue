<script setup lang="ts">
import { computed } from 'vue'
import TemplateDate from '../common/TemplateDate.vue'
import { equipmentHistoryFields, type EquipmentDraft, type EquipmentHistory, type EquipmentHistoryKind } from '../../types/quality/equipmentForm'
const props = defineProps<{ kind: EquipmentHistoryKind; equipment: EquipmentDraft; record: EquipmentHistory; readonly: boolean }>()
const fields = computed(() => props.kind === 'maintenance'
  ? ['date', 'person', 'reason', 'content', 'notes'].map(key => ({ ...equipmentHistoryFields.maintenance.find(field => field.key === key)!, area: ['reason', 'content', 'notes'].includes(key) }))
  : equipmentHistoryFields[props.kind])
const equipmentFields = [['code', '设备编号'], ['model', '规格型号'], ['name', '设备名称'], ['serial', '出厂编号'], ['manufacturer', '生产厂家']] as const
</script>
<template>
  <div v-for="[key, label] in equipmentFields" :key="key" class="col-12" :class="key === 'name' ? '' : 'col-md-6'">
    <label :for="`history-equipment-${key}`" class="form-label">{{ label }}</label>
    <input :id="`history-equipment-${key}`" :value="equipment[key]" class="form-control bg-light" type="text" readonly />
  </div>
  <div v-for="field in fields" :key="field.key" class="col-12" :class="field.area || ['conclusion', 'before', 'after'].includes(field.key) ? '' : 'col-md-6'">
    <label :for="`equipment-history-${field.key}`" class="form-label">{{ field.label }}</label>
    <TemplateDate v-if="field.date" :id="`equipment-history-${field.key}`" v-model="record[field.key]!" :disabled="readonly" within-modal />
    <textarea v-else-if="field.area" :id="`equipment-history-${field.key}`" v-model="record[field.key]" class="form-control" :rows="kind === 'maintenance' || kind === 'usage' ? 2 : 3" maxlength="1000" :disabled="readonly"></textarea>
    <input v-else :id="`equipment-history-${field.key}`" v-model="record[field.key]" class="form-control" type="text" maxlength="1000" :disabled="readonly" />
  </div>
</template>
