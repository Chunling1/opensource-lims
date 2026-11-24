<script setup lang="ts">
import { computed, ref, watch, inject } from 'vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import ReportStandardDisplay from './ReportStandardDisplay.vue'
import JudgmentStandardDisplay from './JudgmentStandardDisplay.vue'
import ReportTextPreview from './ReportTextPreview.vue'
import { equipmentPreview } from './reportTextDisplay'
import TemplateDate from './EntryDate.vue'
import DataEntryDates from './EntryDates.vue'
import DataEntryPersonPicker from './EntryPersonPicker.vue'
import DataEntryEquipmentPicker from './EntryEquipmentPicker.vue'
import { entryConclusions, trialEquipmentText, type TrialForm, type EntryDetail, type EntryPerson, type EntryPersonRole, type EntryPeopleScope } from '../../types/testing/dataEntryDetail'
import type { FormField, FormSchema } from '../../types/forms'
const bridge = inject<any>('platform-entry-presentation')!
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
const equipmentText = computed(() => equipmentPreview(bridge.textSettings.equipmentIds || [], bridge.reportEquipment || [], bridge.textSettings.equipmentDisplay || {}, bridge.textSettings.equipmentSeparatorText ?? '；'))
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
  { id: 'trial-conclusion-section', title: '结论与备注', fields: [text('conclusion', '结论', 'textarea', true), { id: 'trial-conclusionStatus', errorKey: 'conclusionStatus', label: '结论状态', control: 'select', required: true, emptyLabel: '请选择', options: bridge.conclusions, binding: { get: form => form.conclusionStatus, set: (form, value) => { form.conclusionStatus = value } } }, { ...text('failedParameters', '不合格参数'), width: 'col-12 col-md-8', placeholder: '请填写不合格参数，多个参数可用分号分隔' }, text('notes', '备注', 'textarea')] },
  { id: 'trial-people', title: '人员与日期', fields: [
    { id: 'trial-entry-person', label: '数据录入人', control: 'text', readonly: true, binding: { get: () => props.detail.sample.assignmentInfo?.dataEntryPerson || '未分配' } },
    person('tester1Id'), person('tester2Id'),
    person('reviewerId'), person('approverId'),
    { ...text('calibrationDate', '校准日期', 'date'), labelSlot: 'calibration-label', disabled: form => !form.calibrationEnabled },
    { id: 'trial-testDates', errorKey: 'testDates', label: '试验日期', control: 'custom', slot: 'test-dates', required: true, ownLabel: true, width: 'col-12 col-md-6 col-xl-8' },
  ] },
  { id: 'trial-environment-section', title: '环境与设备', fields: [...bridge.environmentFields, { id: 'trial-equipmentIds', errorKey: 'equipmentIds', label: '试验设备', control: 'custom', slot: 'equipment', width: 'col-12' }] },
...bridge.extraSections,
] }))
</script>
<template>
  <SchemaForm :model="form" :schema="schema" :readonly="readonly" :errors="errors">
    <template v-for="key in (['calibrationDate'] as const)" :key="key" #[key]="{ disabled }"><TemplateDate :id="`trial-${key}`" v-model="form[key]" :disabled="readonly || disabled" /></template>
    <template v-for="field in personFields" :key="field.key" #[field.key]>
      <div class="input-group">
        <input :id="`trial-${field.key}`" class="form-control" :class="{ 'bg-body-tertiary': readonly, 'is-invalid': errors[field.key] }" :value="personText(field)" readonly :placeholder="`请选择${field.label}`" :aria-invalid="!!errors[field.key]" :aria-describedby="errors[field.key] ? `trial-${field.key}-error` : undefined" />
        <button class="btn btn-light" type="button" :aria-label="`选择${field.label}`" :disabled="readonly" @click="picking = field"><i class="ti ti-search" aria-hidden="true"></i></button>
        <button class="btn btn-light" type="button" :aria-label="`清除${field.label}`" :disabled="readonly || !form[field.key]" @click="form[field.key] = ''"><i class="ti ti-x" aria-hidden="true"></i></button>
      </div>
    </template>
    <template #test-dates><DataEntryDates v-model="form.testDates" :readonly="readonly" :errors="errors" /></template>
    <template #standard-display><ReportStandardDisplay :settings="bridge.textSettings" :options="bridge.standardOptions" :language="bridge.reportLanguage" :loading="bridge.standardLoading" :readonly="readonly" /></template>
    <template #judgment-display><JudgmentStandardDisplay v-if="bridge.textSettings.judgmentDisplay" id="report-judgment" :source="bridge.judgmentSource" :records="bridge.textSettings.standardRecords" :settings="bridge.textSettings.judgmentDisplay" :language="bridge.reportLanguage" :readonly="readonly" /></template>
    <template #equipment>
      <div class="row g-3">
        <div class="col-12 col-xl-5">
          <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
            <button class="btn btn-light" type="button" :disabled="readonly" @click="equipmentOpen = true"><i class="ti ti-search me-1" aria-hidden="true"></i>选择仪器设备</button>
            <button class="btn btn-light" type="button" :disabled="readonly || !form.equipmentIds.length" @click="form.equipmentIds = []">清空设备</button>
            <span class="small text-muted">已选 {{ form.equipmentIds.length }} 台</span>
          </div>
          <div class="row g-2" role="group" aria-label="设备填充选项"><div v-for="option in displayFlags" :key="option.key" class="col-12 col-sm-6"><div class="form-check mb-0"><input :id="`trial-${option.key}`" v-model="form[option.key]" class="form-check-input" type="checkbox" :disabled="readonly" /><label :for="`trial-${option.key}`" class="form-check-label">{{ option.label.replace('是否体现', '显示') }}</label></div></div></div>
        </div>
        <div class="col-12 col-xl-7">
          <ReportTextPreview id="trial-equipmentIds" label="设备文字效果" :text="equipmentText" :separator="bridge.textSettings.equipmentSeparatorText ?? '；'" :readonly="readonly" :hide-separator="bridge.isCalibrationReport" @update:separator="bridge.textSettings.equipmentSeparatorText = $event" />
          <p v-if="bridge.isCalibrationReport" class="small text-muted mt-1 mb-0">校准报告按模板分列展示设备信息。</p>
        </div>
      </div>
    </template>
    <template #calibration-label><div class="form-check mb-2"><input id="trial-calibration-enabled" v-model="form.calibrationEnabled" type="checkbox" class="form-check-input" :disabled="true" title="由平台报告类型确定，校准报告必须填写校准时间" /><label for="trial-calibration-enabled" class="form-check-label">填写校准日期</label></div><label for="trial-calibrationDate" class="visually-hidden">校准日期</label></template>
  </SchemaForm>
  <DataEntryEquipmentPicker v-if="equipmentOpen" :detail="detail" :value="form.equipmentIds" @refreshed="emit('equipment-config', $event)" @close="equipmentOpen = false" @select="selectEquipment" />
  <DataEntryPersonPicker v-if="picking" :sample-id="detail.sample.id" :role="picking.role" :title="`选择${picking.label}`" :value="personValue(picking)" :initial-scope="peopleScopes[picking.role]" :exclude-id="picking.key === 'tester1Id' ? form.tester2Id : picking.key === 'tester2Id' ? form.tester1Id : undefined" @close="picking = undefined" @select="selectPerson" @scope="emit('people-scope', { role: picking.role, scope: $event })" />
</template>
