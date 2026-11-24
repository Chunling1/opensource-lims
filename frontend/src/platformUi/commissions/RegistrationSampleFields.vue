<script setup lang="ts">
import ProductionDatesEditor from '@/components/ProductionDatesEditor.vue'
import { computed, ref, watch, inject } from 'vue'
import RegistrationTestBasisField from './RegistrationTestBasisField.vue'
import RegistrationTestBasisPicker from './RegistrationTestBasisPicker.vue'
import type { TestBasisSelection } from '../../types/commissions/testBasis'
import RegistrationTrademarkField from '../../components/commissions/RegistrationTrademarkField.vue'
import RegistrationSampleSubprojects from './RegistrationSampleSubprojects.vue'
import RegistrationManufacturerPicker from './RegistrationManufacturerPicker.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TemplateEditableSelect from '../../components/common/TemplateEditableSelect.vue'
import { clientToday } from '../../services/common/date'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import { sampleSchema, optionalSampleDates } from '../../views/commissions/forms/sampleSchema'
import type { RegistrationSampleInput } from '../../types/commissions/registration'
import type { SampleFormOptions } from '../../types/commissions/sampleForm'

const props = defineProps<{ errors?: Readonly<Record<string, string>>; form: RegistrationSampleInput; options: SampleFormOptions; code?: string; reportCode?: string; commissionCode?: string; projects: string[]; readonly?: boolean; canChooseCommission?: boolean }>()
const emit = defineEmits<{ chooseCommission: []; pending: [boolean] }>()
const details = computed(() => props.form.details!)
const assessmentOpen = ref(false), assessmentPending = ref(false), uploadPending = ref(false)
watch([assessmentPending, uploadPending], ([assessment, upload]) => emit('pending', assessment || upload))
function clearAssessment() {
  Object.assign(details.value, { assessmentStandard: '', assessmentStandardIds: [], assessmentStandardSeparators: [], assessmentEnglishBookMarks: false })
}
function chooseAssessment(selection: TestBasisSelection) {
  Object.assign(details.value, { assessmentStandard: selection.text, assessmentStandardIds: [...selection.ids], assessmentStandardSeparators: [...selection.separators], assessmentEnglishBookMarks: selection.englishBookMarks })
  assessmentOpen.value = false
}
watch(() => details.value.useAssessmentStandard, enabled => { if (!props.readonly && !enabled) { assessmentOpen.value = false; clearAssessment() } })
watch(() => details.value.testPlanId, () => { assessmentOpen.value = false })
const manufacturerOpen = ref(false)
const projectOpen = ref(false), projectDraft = ref<string[]>([])
function openProjects() { projectDraft.value = [...props.form.projects]; projectOpen.value = true }
const context=inject<any>('platform-registration-context')!
const production=inject<any>('platform-production-dates')!
const schema = computed(() => { const result = sampleSchema(props.options); const disabled = new Set(['sample-appearanceNotes','sample-taskRecipient','sample-inspectorPhone','sample-inspector','sample-requestedTestDate','sample-testingDepartment']); for (const section of result.sections) for (const field of section.fields || []) {if(field.id==='sample-productionDate'){Object.assign(field,{control:'custom',slot:'production-dates',width:'col-12'})} if(field.id==='sample-quantity'){Object.assign(field,{label:'样品数量（含单位）',control:'text',placeholder:'如：3台、2台及3套',min:undefined,step:undefined,binding:{get:()=>String(props.form.quantity ?? ''),set:(_:unknown,value:string)=>{(props.form as unknown as {quantity:string}).quantity=value}}})} if (disabled.has(field.id)) field.disabled = true; if(field.id==='sample-category' && field.control==='select') field.options=context.testCategories.map((value:string)=>({value,label:value}));} return result })
function toggleDate(id: string, checked: boolean) {
  const field = optionalSampleDates[id]!
  details.value[field.toggle] = checked
  if (checked && !details.value[field.key]) details.value[field.key] = clientToday()
}
watch(() => props.readonly, () => { assessmentOpen.value = false; projectOpen.value = false; manufacturerOpen.value = false })
</script>
<template>
  <SchemaForm :schema="schema" :model="props" :readonly="readonly" :errors="errors">
    <template #production-dates><ProductionDatesEditor v-model="production.s.produceDate" v-model:rows="production.s.productionDates" :disabled="readonly" :language="production.s.reportLanguage" :limits="{sampleTime:production.s.sampleTime,sendDate:production.s.sendDate,entrustDate:production.selectedEntrustDate}" /></template>
    <template #commission><div class="input-group"><input id="sample-commission" class="form-control" :class="{ 'bg-body-tertiary': readonly || !canChooseCommission }" :value="commissionCode" readonly /><button v-if="canChooseCommission && !readonly" class="btn btn-light" type="button" aria-label="选择委托" @click="emit('chooseCommission')"><i class="ti ti-search" aria-hidden="true"></i></button></div></template>
    <template #projects><div class="input-group"><textarea id="sample-projects" class="form-control" :class="{ 'bg-body-tertiary': readonly }" rows="3" :value="form.projects.join('；')" readonly></textarea><button v-if="!readonly" class="btn btn-light" type="button" aria-label="选择检测项目" @click="openProjects"><i class="ti ti-search" aria-hidden="true"></i></button></div></template>
    <template #assessment><RegistrationTestBasisField :text-value="details.assessmentStandard" label="评定标准" field-id="sample-assessment" :textarea-rows="3" :plan-id="details.testPlanId" :ids="details.assessmentStandardIds" :separators="details.assessmentStandardSeparators" :english-book-marks="details.assessmentEnglishBookMarks" :disabled="!details.useAssessmentStandard" :readonly="readonly" @open="assessmentOpen = true" @clear="clearAssessment" @select="chooseAssessment" @pending="assessmentPending = $event"><template #label="{ labelId }"><div class="form-check mb-2"><input id="sample-use-assessment" v-model="details.useAssessmentStandard" class="form-check-input" type="checkbox" aria-label="是否使用评定标准" :disabled="readonly" /><label :id="labelId" class="form-check-label" for="sample-use-assessment">是否使用评定标准</label></div></template></RegistrationTestBasisField></template>
    <template #manufacturer><div class="input-group"><input id="sample-manufacturer" v-model="details.manufacturer" class="form-control" :class="{ 'bg-body-tertiary': readonly }" maxlength="2000" :readonly="readonly" /><button v-if="!readonly" class="btn btn-light" type="button" aria-label="选择生产单位" disabled @click="manufacturerOpen = true"><i class="ti ti-search" aria-hidden="true"></i></button></div></template>
    <template #testing-location><TemplateEditableSelect id="sample-testingLocation" v-model="details.testingLocation" label="检测地点" :options="options.choices.testingLocation || []" placeholder="请选择或输入检测地点" :maxlength="2000" :readonly="true" multiple /></template>
    <template #trademark><input id="sample-trademark" v-model="details.trademark" class="form-control" :class="{ 'bg-body-tertiary': readonly }" maxlength="2000" :readonly="readonly" /><RegistrationTrademarkField v-model="details.trademarkImage" :readonly="readonly || context.sampleImageBlocked" @pending="uploadPending = $event" /></template>
    <template #optional-date-label="{ field }"><div class="form-check mb-2"><input :id="`sample-toggle-${optionalSampleDates[field.id]!.key}`" class="form-check-input" type="checkbox" :checked="details[optionalSampleDates[field.id]!.toggle]" :disabled="readonly" @change="toggleDate(field.id, ($event.target as HTMLInputElement).checked)" /><label class="form-check-label" :for="`sample-toggle-${optionalSampleDates[field.id]!.key}`">{{ field.label }}</label></div><label :for="field.id" class="visually-hidden">{{ field.label }}</label></template>
    <template #report-settings><slot name="report-settings" /></template>
    <template #subprojects><RegistrationSampleSubprojects v-model="details.subprojects" :options="options.subprojectOptions" :readonly="readonly" /></template>
  </SchemaForm>
  <RegistrationTestBasisPicker :open="assessmentOpen" label="评定标准" :plan-id="details.testPlanId" :ids="details.assessmentStandardIds" :separators="details.assessmentStandardSeparators" :english-book-marks="details.assessmentEnglishBookMarks" @close="assessmentOpen = false" @select="chooseAssessment" />
  <BootstrapModal :open="projectOpen" title="选择检测项目" @close="projectOpen = false"><div v-for="(project, index) in projects" :key="project" class="form-check mb-3"><input :id="`sample-project-choice-${index}`" v-model="projectDraft" class="form-check-input" type="checkbox" :value="project" /><label :for="`sample-project-choice-${index}`" class="form-check-label">{{ project }}</label></div><template #footer><button class="btn btn-light" type="button" @click="projectOpen = false">返回</button><button class="btn btn-primary" type="button" @click="form.projects = [...projectDraft]; projectOpen = false">确定</button></template></BootstrapModal>
  <RegistrationManufacturerPicker :open="manufacturerOpen" :value="details.manufacturer" @close="manufacturerOpen = false" @select="details.manufacturer = $event; manufacturerOpen = false" />
</template>
