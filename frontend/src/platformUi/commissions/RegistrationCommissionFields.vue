<script setup lang="ts">
import { computed, ref, watch, inject } from 'vue'
import RegistrationContractPicker from './RegistrationContractPicker.vue'
import RegistrationOrganizationPicker from './RegistrationOrganizationPicker.vue'
import { currentActor } from '../../stores/session'
import { registrationDepartments, type RegistrationContract } from '../../types/commissions/commissionForm'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import { commissionSchema, commissionFieldKey, type CommissionFormModel } from '../../views/commissions/forms/commissionSchema'
import { bulkCommissionFields } from '../../types/commissions/commissionFields'
import type { CommissionFieldsInput } from '../../types/commissions/sampleCommission'

const props = defineProps<{ form: CommissionFieldsInput; code?: string; owner?: string; readonly?: boolean; sample?: boolean; canChooseCommission?: boolean; bulkFields?: string[]; mixedFields?: string[] }>()
const emit = defineEmits<{ chooseCommission: []; toggleField: [key: string, selected: boolean] }>()
const contractOpen = ref(false)
type OrganizationField = 'contractParty' | 'payer' | 'customer'
const organizationField = ref<OrganizationField>()
const organizationLabels = { contractParty: '合同甲方', payer: '其他甲方（付款方）', customer: '委托单位' }
function chooseOrganization(name: string) {
  if (organizationField.value) { props.form[organizationField.value] = name; context.organizationPicked(organizationField.value, name) }
  organizationField.value = undefined
}
const context = inject<any>('platform-registration-context')!
const departments = computed(() => context.departments)
function chooseContract(contract: RegistrationContract) {
  Object.assign(props.form, { contractId: contract.id, contract: contract.code, erpContract: contract.erpContract, erpProjectType: contract.erpProjectType })
  contractOpen.value = false
}
function clearContract() { Object.assign(props.form, { contractId: '', contract: '', erpContract: '', erpProjectType: '' }) }
watch(currentActor, () => { contractOpen.value = false; organizationField.value = undefined })
const model = computed<CommissionFormModel>(() => ({ ...props, displayOwner: props.sample ? props.owner || '' : props.owner || currentActor.value.name, departments: departments.value }))
const schema = computed(() => { const result = commissionSchema(model.value); for (const section of result.sections) for (const field of section.fields || []) if (field.id === 'commission-contractParty' && context.contractPartyLocked) field.disabled = true; return result })
function fieldDisabled(field: any) { return typeof field.disabled === 'function' ? !!field.disabled(model.value) : !!field.disabled }
const editable = new Set(bulkCommissionFields.map(field => `commission-${field.key}`))
</script>

<template>
  <SchemaForm :schema="schema" :model="model" :readonly="readonly">
    <template #before-field="{ field }"><div v-if="bulkFields && editable.has(field.id)" class="form-check mb-2"><input :id="`bulk-${commissionFieldKey(field.id)}`" class="form-check-input" type="checkbox" :checked="bulkFields.includes(commissionFieldKey(field.id))" @change="emit('toggleField', commissionFieldKey(field.id), ($event.target as HTMLInputElement).checked)" /><label :for="`bulk-${commissionFieldKey(field.id)}`" class="form-check-label">{{ field.label }}</label></div></template>
    <template #customer>
      <div class="input-group"><textarea id="commission-customer" v-model="form.customer" class="form-control" :class="{ 'bg-body-tertiary': readonly }" :readonly="readonly" rows="2" maxlength="500" placeholder="请选择或填写委托单位"></textarea><template v-if="!readonly"><button class="btn btn-light" type="button" aria-label="选择委托单位" title="选择委托单位" @click="organizationField = 'customer'"><i class="ti ti-search" aria-hidden="true"></i></button><button v-if="form.customer" class="btn btn-light" type="button" aria-label="清除委托单位" title="清除委托单位" @click="form.customer = ''"><i class="ti ti-x" aria-hidden="true"></i></button></template></div>
    </template>
    <template #commission-code><div class="input-group"><input id="commission-code" class="form-control" :class="{ 'bg-body-tertiary': readonly || !canChooseCommission }" :value="code" readonly /><button v-if="canChooseCommission" class="btn btn-light" type="button" aria-label="选择委托" @click="emit('chooseCommission')"><i class="ti ti-search" aria-hidden="true"></i></button></div></template>
    <template #contract><div class="input-group"><input id="commission-contract" class="form-control" :value="form.contract" placeholder="请选择合同" readonly /><button class="btn btn-light" type="button" aria-label="选择合同" title="选择合同" :disabled="readonly || sample" @click="contractOpen = true"><i class="ti ti-search" aria-hidden="true"></i></button><button v-if="form.contract" class="btn btn-light" type="button" aria-label="清除合同" title="清除合同" :disabled="readonly || sample" @click="clearContract"><i class="ti ti-x" aria-hidden="true"></i></button></div></template>
    <template v-for="key in (['contractParty', 'payer'] as const)" :key="key" #[key]="{ field }"><div class="input-group"><input :id="field.id" class="form-control" :value="form[key]" :readonly="readonly || fieldDisabled(field) || !context.manualParties" maxlength="500" :placeholder="context.manualParties ? '可选择客户，也可填写单位名称' : '请从客户库选择'" @input="!readonly && !fieldDisabled(field) && context.manualParties && (form[key] = ($event.target as HTMLInputElement).value)" /><button class="btn btn-light" type="button" :aria-label="`选择${field.label}`" :title="`选择${field.label}`" :disabled="readonly || fieldDisabled(field)" @click="organizationField = key"><i class="ti ti-search" aria-hidden="true"></i></button><button v-if="form[key]" class="btn btn-light" type="button" :aria-label="`清除${field.label}`" :title="`清除${field.label}`" :disabled="readonly || fieldDisabled(field)" @click="form[key] = ''"><i class="ti ti-x" aria-hidden="true"></i></button></div></template>
  </SchemaForm>
  <RegistrationContractPicker :open="contractOpen" @close="contractOpen = false" @select="chooseContract" />
  <RegistrationOrganizationPicker :open="!!organizationField" :title="`选择${organizationField ? organizationLabels[organizationField] : '委托单位'}`" :multiple="organizationField === 'customer'" :value="organizationField ? form[organizationField] : ''" @close="organizationField = undefined" @select="chooseOrganization" />
</template>
