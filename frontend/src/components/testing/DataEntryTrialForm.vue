<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import SchemaForm from '../forms/SchemaForm.vue'
import TemplateDate from '../common/TemplateDate.vue'
import DataEntryDates from './DataEntryDates.vue'
import DataEntryPersonPicker from './DataEntryPersonPicker.vue'
import DataEntryEquipmentPicker from './DataEntryEquipmentPicker.vue'
import { entryConclusions, trialEquipmentText, type TrialForm, type EntryDetail, type EntryPerson, type EntryPersonRole, type EntryPeopleScope } from '../../types/testing/dataEntryDetail'
import type { FormField, FormSchema } from '../../types/forms'
const props = defineProps<{ form: TrialForm; detail: EntryDetail; readonly: boolean; errors: Record<string, string>; peopleScopes: Partial<Record<EntryPersonRole, EntryPeopleScope>> }>()
const emit = defineEmits<{ 'people-scope': [value: { role: EntryPersonRole; scope: EntryPeopleScope }]; 'equipment-config': [EntryDetail] }>()
const personFields = [
  { key: 'tester1Id', label: '试验人1', role: 'tester', required: true },
  { key: 'tester2Id', label: '试验人2', role: 'tester', required: false },
  { key: 'reviewerId', label: '指定审核人', role: 'reviewer', required: false },
  { key: 'approverId', label: '指定批准人', role: 'approver', required: false },
] as const
const picking = ref<typeof personFields[number]>(), chosen = ref<Record<string, EntryPerson>>({})
function personValue(field: typeof personFields[number]): EntryPerson | undefined {
  const id = props.form[field.key]
  if (!id) return undefined
  const options = field.role === 'tester' ? props.detail.options.people : field.role === 'reviewer' ? props.detail.options.reviewers : props.detail.options.approvers
  return chosen.value[id] || options.find(row => row.id === id) || { id, name: '人员已不可选' }
}
function personText(field: typeof personFields[number]) { const row = personValue(field); return row ? `${row.name}（${row.id}）` : '' }
function selectPerson(person: EntryPerson) {
  if (picking.value && !props.readonly) { props.form[picking.value.key] = person.id; chosen.value[person.id] = person }
  picking.value = undefined
}
const equipmentOpen = ref(false)
const equipmentText = computed(() => trialEquipmentText(props.form, props.detail.options.equipment))
function selectEquipment(ids: string[]) { if (!props.readonly) props.form.equipmentIds = ids; equipmentOpen.value = false }
watch(() => props.readonly, value => { if (value) { picking.value = undefined; equipmentOpen.value = false } })

type TextKey = { [K in keyof TrialForm]: TrialForm[K] extends string ? K : never }[keyof TrialForm]
const displayFlags = [{ key: 'showEquipmentCode', label: '是否体现档案号' }, { key: 'showEquipmentModel', label: '是否体现规格型号' }, { key: 'showEquipmentManufacturer', label: '是否体现仪器厂商名称' }, { key: 'showEquipmentSerial', label: '是否体现仪器出厂编号' }] as const
function text(key: TextKey, label: string, control: 'text' | 'textarea' | 'date' = 'text', required = false): FormField<TrialForm> {
  if (control === 'date') return { id: `trial-${key}`, errorKey: key, label, control: 'custom', slot: key, required }
  return { id: `trial-${key}`, errorKey: key, label, control, required, ...(control === 'textarea' ? { width: 'col-12', rows: key === 'conclusion' ? 2 : 1, maxlength: 5000 } : { maxlength: 500 }), binding: { get: form => form[key], set: (form, value) => { form[key] = value } } }
}
function person(key: typeof personFields[number]['key']): FormField<TrialForm> {
  const field = personFields.find(field => field.key === key)!
  return { id: `trial-${key}`, errorKey: key, label: field.label, control: 'custom', slot: key, required: field.required }
}
const schema = computed<FormSchema<TrialForm>>(() => ({ sections: [
  { id: 'trial-conclusion-section', title: '结论与备注', fields: [text('conclusion', '结论', 'textarea', true), { id: 'trial-conclusionStatus', errorKey: 'conclusionStatus', label: '结论状态', control: 'select', required: true, emptyLabel: '请选择', options: entryConclusions.map(value => ({ value, label: value })), binding: { get: form => form.conclusionStatus, set: (form, value) => { form.conclusionStatus = value } } }, { ...text('failedParameters', '不合格参数'), width: 'col-12 col-md-8', placeholder: '请填写不合格参数，多个参数可用分号分隔' }, text('notes', '备注', 'textarea')] },
  { id: 'trial-people', title: '人员与日期', fields: [
    { id: 'trial-entry-person', label: '数据录入人', control: 'text', readonly: true, binding: { get: () => props.detail.sample.assignmentInfo?.dataEntryPerson || '未分配' } },
    person('tester1Id'), person('tester2Id'),
    person('reviewerId'), person('approverId'),
    { ...text('calibrationDate', '校准日期', 'date'), labelSlot: 'calibration-label', disabled: form => !form.calibrationEnabled },
    { id: 'trial-testDates', errorKey: 'testDates', label: '试验日期', control: 'custom', slot: 'test-dates', required: true, ownLabel: true, width: 'col-12 col-md-6 col-xl-8' },
    { ...text('reportDate', '报告日期', 'date'), labelSlot: 'report-label', disabled: form => !form.reportDateEnabled },
  ] },
  { id: 'trial-environment-section', title: '环境与设备', fields: [{ ...text('environment', '试验环境'), width: 'col-12 col-lg-4' }, { id: 'trial-equipmentIds', errorKey: 'equipmentIds', label: '试验设备', control: 'custom', slot: 'equipment', width: 'col-12' }] },
] }))
</script>
<template>
  <SchemaForm :model="form" :schema="schema" :readonly="readonly" :errors="errors">
    <template v-for="key in (['calibrationDate', 'reportDate'] as const)" :key="key" #[key]="{ disabled }"><TemplateDate :id="`trial-${key}`" v-model="form[key]" :disabled="readonly || disabled" /></template>
    <template v-for="field in personFields" :key="field.key" #[field.key]>
      <div class="input-group">
        <input :id="`trial-${field.key}`" class="form-control" :class="{ 'bg-body-tertiary': readonly, 'is-invalid': errors[field.key] }" :value="personText(field)" readonly :placeholder="`请选择${field.label}`" :aria-invalid="!!errors[field.key]" :aria-describedby="errors[field.key] ? `trial-${field.key}-error` : undefined" />
        <button class="btn btn-light" type="button" :aria-label="`选择${field.label}`" :disabled="readonly" @click="picking = field"><i class="ti ti-search" aria-hidden="true"></i></button>
        <button class="btn btn-light" type="button" :aria-label="`清除${field.label}`" :disabled="readonly || !form[field.key]" @click="form[field.key] = ''"><i class="ti ti-x" aria-hidden="true"></i></button>
      </div>
    </template>
    <template #test-dates><DataEntryDates v-model="form.testDates" :readonly="readonly" :errors="errors" /></template>
    <template #equipment>
      <div class="row g-3">
      <div class="col-12 col-xl-8"><div class="input-group h-100">
        <textarea id="trial-equipmentIds" class="form-control" :class="{ 'bg-body-tertiary': readonly, 'is-invalid': errors.equipmentIds }" :value="equipmentText" rows="4" readonly placeholder="请选择仪器设备，可多选" :aria-invalid="!!errors.equipmentIds" :aria-describedby="errors.equipmentIds ? 'trial-equipmentIds-error' : undefined"></textarea>
        <button class="btn btn-light" type="button" aria-label="选择仪器设备" :disabled="readonly" @click="equipmentOpen = true"><i class="ti ti-search" aria-hidden="true"></i></button>
        <button class="btn btn-light" type="button" aria-label="清除试验设备" :disabled="readonly || !form.equipmentIds.length" @click="form.equipmentIds = []"><i class="ti ti-x" aria-hidden="true"></i></button>
      </div></div>
      <div class="col-12 col-xl-4" role="group" aria-label="设备填充选项"><div class="d-flex flex-column gap-2"><div v-for="option in displayFlags" :key="option.key" class="form-check mb-0"><input :id="`trial-${option.key}`" v-model="form[option.key]" class="form-check-input" type="checkbox" :disabled="readonly" /><label :for="`trial-${option.key}`" class="form-check-label">{{ option.label }}</label></div></div></div>
      </div>
    </template>
    <template #calibration-label><div class="form-check mb-2"><input id="trial-calibration-enabled" v-model="form.calibrationEnabled" type="checkbox" class="form-check-input" :disabled="readonly" /><label for="trial-calibration-enabled" class="form-check-label">填写校准日期</label></div><label for="trial-calibrationDate" class="visually-hidden">校准日期</label></template>
    <template #report-label><div class="form-check mb-2"><input id="trial-report-enabled" v-model="form.reportDateEnabled" type="checkbox" class="form-check-input" :disabled="readonly" /><label for="trial-report-enabled" class="form-check-label">填写报告日期</label></div><label for="trial-reportDate" class="visually-hidden">报告日期</label></template>
  </SchemaForm>
  <DataEntryEquipmentPicker v-if="equipmentOpen" :detail="detail" :value="form.equipmentIds" @refreshed="emit('equipment-config', $event)" @close="equipmentOpen = false" @select="selectEquipment" />
  <DataEntryPersonPicker v-if="picking" :sample-id="detail.sample.id" :role="picking.role" :title="`选择${picking.label}`" :value="personValue(picking)" :initial-scope="peopleScopes[picking.role]" :exclude-id="picking.key === 'tester1Id' ? form.tester2Id : picking.key === 'tester2Id' ? form.tester1Id : undefined" @close="picking = undefined" @select="selectPerson" @scope="emit('people-scope', { role: picking.role, scope: $event })" />
</template>
