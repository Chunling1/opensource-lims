<script setup lang="ts">
import TemplateDate from '../common/TemplateDate.vue'
import { equipmentCheckMeasurements, type EquipmentDraft, type EquipmentHistory } from '../../types/quality/equipmentForm'
defineProps<{ equipment: EquipmentDraft; record: EquipmentHistory; readonly: boolean }>()
const fields = [
  { key: 'equipmentDate', label: '设备检定日期', date: true },
  { key: 'accuracyRequirement', label: '精度要求' },
  { key: 'standard', label: '计量参考标准名称' },
  { key: 'standardDate', label: '计量参考标准检定日期', date: true },
  { key: 'person', label: '期间核查人员' },
  { key: 'date', label: '检查日期', date: true },
  { key: 'project', label: '期间核查项目' },
]
</script>
<template>
  <div v-for="[key, label] in ([['name', '设备名称'], ['model', '规格型号']] as const)" :key="key" class="col-12 col-md-6">
    <label :for="`check-equipment-${key}`" class="form-label">{{ label }}</label>
    <input :id="`check-equipment-${key}`" :value="equipment[key]" class="form-control bg-light" type="text" readonly />
  </div>
  <div v-for="field in fields" :key="field.key" class="col-12" :class="field.key === 'project' ? '' : 'col-md-6'">
    <label :for="`equipment-history-${field.key}`" class="form-label">{{ field.label }}</label>
    <TemplateDate v-if="field.date" :id="`equipment-history-${field.key}`" v-model="record[field.key]!" :disabled="readonly" within-modal />
    <input v-else :id="`equipment-history-${field.key}`" v-model="record[field.key]" class="form-control" maxlength="1000" :disabled="readonly" />
  </div>
  <div class="col-12">
    <div class="table-responsive">
      <table class="table table-sm table-bordered align-middle mb-0" aria-label="期间核查测量数据">
        <thead class="table-light"><tr><th scope="col" class="text-nowrap px-2 py-1">测量数据</th><th v-for="index in 5" :key="index" scope="col" class="text-nowrap px-2 py-1">核查点 {{ index }}</th></tr></thead>
        <tbody><tr v-for="field in equipmentCheckMeasurements" :key="field.key">
          <th scope="row" class="text-nowrap fw-medium px-2 py-1">{{ field.label }}</th>
          <td v-for="index in 5" :key="index" class="p-1"><input v-model="record[`${field.key}${index}`]" class="form-control form-control-sm w-auto" type="text" size="10" maxlength="1000" :aria-label="`核查点 ${index} ${field.label}`" :disabled="readonly" /></td>
        </tr></tbody>
      </table>
    </div>
  </div>
  <div class="col-12"><label for="equipment-history-conclusion" class="form-label">评审分析及结论</label><textarea id="equipment-history-conclusion" v-model="record.conclusion" class="form-control" rows="2" maxlength="1000" :disabled="readonly"></textarea></div>
</template>
