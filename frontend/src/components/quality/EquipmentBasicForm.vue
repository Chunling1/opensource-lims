<script setup lang="ts">
import TemplateDate from '../common/TemplateDate.vue'
import TemplateEditableSelect from '../common/TemplateEditableSelect.vue'
import { equipmentStates } from '../../types/quality/equipmentLedger'
import { equipmentAttachmentKinds, type EquipmentDraft, type EquipmentFormOptions, type EquipmentAttachmentKind } from '../../types/quality/equipmentForm'
const props = defineProps<{ draft: EquipmentDraft; options: EquipmentFormOptions; disabled: boolean; busy?: boolean }>()
defineEmits<{ attachment: [EquipmentAttachmentKind] }>()
const sections = [
  { title: '设备信息', fields: [['code', '档案号'], ['name', '仪器设备名称'], ['model', '规格型号'], ['accuracy', '准确度'], ['range', '量程'], ['equipmentType', '设备类型'], ['status', '设备状态']] },
  { title: '购置与保管', fields: [['purchasedAt', '购入日期'], ['price', '购入价格'], ['keeper', '仪器保管人'], ['manufacturer', '生产厂家'], ['serial', '仪器出厂号'], ['location', '放置单位']] },
  { title: '检定信息', fields: [['testOrganization', '检定/测试单位'], ['tester', '检定人'], ['cycle', '周期'], ['validity', '有效期'], ['lastTestDate', '最近检定/测试日期'], ['plannedTestDate', '计划检定/测试日期'], ['actualTestDate', '实际检定/测试日期'], ['departmentId', '所属部门']] },
] as const
type Key = typeof sections[number]['fields'][number][0]
const profileKeys = ['equipmentType', 'tester', 'validity'] as const
const dates = ['purchasedAt', 'lastTestDate', 'plannedTestDate', 'actualTestDate']
function value(key: Key) { return profileKeys.includes(key as typeof profileKeys[number]) ? props.draft.profile[key as typeof profileKeys[number]] : props.draft[key as keyof EquipmentDraft] as string | number | null }
function set(key: Key, value: string) {
  if (profileKeys.includes(key as typeof profileKeys[number])) props.draft.profile[key as typeof profileKeys[number]] = value
  else if (key === 'price') props.draft.price = value === '' ? null : Number(value)
  else Object.assign(props.draft, { [key]: value })
}
</script>
<template>
  <section v-for="section in sections" :key="section.title" :aria-label="section.title" class="mb-3">
    <h6 class="border-bottom pb-2 mb-2">{{ section.title }}</h6>
    <div class="row g-2">
      <div v-for="[key, label] in section.fields" :key="key" class="col-12" :class="key === 'name' ? 'col-lg-8' : 'col-lg-4'">
        <label :for="`equipment-${key}`" class="form-label mb-1">{{ label }}<span v-if="key === 'code' || key === 'name'" class="text-danger ms-1" aria-hidden="true">*</span></label>
        <TemplateDate v-if="dates.includes(key)" :id="`equipment-${key}`" :data-validation-key="key" :model-value="String(value(key) || '')" :disabled="disabled" within-modal @update:model-value="set(key, $event)" />
        <select v-else-if="key === 'status'" :id="`equipment-${key}`" :data-validation-key="key" v-model="draft.status" class="form-select" :disabled="disabled"><option v-for="state in equipmentStates" :key="state">{{ state }}</option></select>
        <select v-else-if="key === 'departmentId'" :id="`equipment-${key}`" :data-validation-key="key" v-model="draft.departmentId" class="form-select" :disabled="disabled || !options.departments.length"><option value="">请选择</option><option v-for="department in options.departments" :key="department.id" :value="department.id">{{ department.name }}</option></select>
        <TemplateEditableSelect v-else-if="key === 'equipmentType'" :id="`equipment-${key}`" :data-validation-key="key" :label="label" v-model="draft.profile.equipmentType" :options="options.equipmentTypes" :readonly="disabled" :maxlength="1000" />
        <input v-else :aria-label="label" :id="`equipment-${key}`" :data-validation-key="key" :value="value(key)" :type="key === 'price' ? 'number' : 'text'" :min="key === 'price' ? 0 : undefined" :max="key === 'price' ? 1000000000000 : undefined" :step="key === 'price' ? '0.01' : undefined" class="form-control" :disabled="disabled" :required="key === 'code' || key === 'name'" maxlength="1000" @input="set(key, ($event.target as HTMLInputElement).value)" />
      </div>
    </div>
  </section>
  <section aria-label="设备附件" class="mb-3"><h6 class="border-bottom pb-2 mb-2">附件</h6><div class="row g-2"><div v-for="kind in equipmentAttachmentKinds" :key="kind.key" class="col-12 col-sm-6 col-lg-3"><div class="d-flex align-items-center justify-content-between border rounded p-2 gap-2"><span>{{ kind.label }} <span class="badge bg-light text-body">{{ draft.profile.attachments[kind.key].length }}</span></span><button type="button" class="btn btn-light btn-sm text-nowrap" :disabled="busy" :aria-label="`管理${kind.label}附件`" @click="$emit('attachment', kind.key)">{{ disabled ? '查看' : '管理' }}</button></div></div></div></section>
  <label for="equipment-notes" class="form-label">备注</label><textarea id="equipment-notes" data-validation-key="notes" v-model="draft.notes" rows="2" class="form-control" maxlength="1000" :disabled="disabled"></textarea>
</template>
