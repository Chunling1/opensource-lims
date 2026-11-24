<script setup lang="ts">
import { computed } from 'vue'
import AttachmentDraftStatus from '../common/AttachmentDraftStatus.vue'
import TemplateEditableSelect from '../common/TemplateEditableSelect.vue'
import TemplateDate from '../common/TemplateDate.vue'
import { personnelOptions, type PersonnelDraft, type PersonnelProfile, type PersonnelKey, type PersonnelAttachmentKind } from '../../types/quality/personnel'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { currentActor } from '../../stores/session'
import { clientToday } from '../../services/common/date'
const props = defineProps<{ draft: PersonnelDraft & { profile: PersonnelProfile }; readonly: boolean; busy: boolean }>()
defineEmits<{ person: []; attachment: [PersonnelAttachmentKind] }>()
interface Field { key: string; label: string; required?: boolean; date?: boolean; wide?: boolean; full?: boolean; area?: boolean; attachment?: PersonnelAttachmentKind }
const sections: { title: string; fields: Field[] }[] = [
  { title: '基本信息', fields: [
    { key: 'code', label: '人员编号', required: true }, { key: 'name', label: '姓名', required: true }, { key: 'formerName', label: '曾用名' },
    { key: 'gender', label: '性别', required: true }, { key: 'ethnicity', label: '民族' }, { key: 'politicalStatus', label: '政治面貌' },
    { key: 'birthDate', label: '出生日期', date: true }, { key: 'identityNumber', label: '身份证号码' }, { key: 'age', label: '年龄' },
    { key: 'nativePlace', label: '籍贯' }, { key: 'birthAddress', label: '出生地址', wide: true },
    { key: 'socialSecurityNumber', label: '社保号' }, { key: 'socialSecurityFile', label: '社保号附件', attachment: 'socialSecurity', wide: true },
  ] },
  { title: '教育情况', fields: [
    { key: 'school', label: '毕业院校' }, { key: 'major', label: '所学专业' }, { key: 'graduatedAt', label: '毕业时间', date: true },
    { key: 'education', label: '文化程度' }, { key: 'educationFile', label: '学历附件', attachment: 'education', wide: true },
    { key: 'degree', label: '学位' }, { key: 'degreeFile', label: '学位附件', attachment: 'degree', wide: true },
  ] },
  { title: '工作情况', fields: [
    { key: 'qualification', label: '职称/资格', required: true }, { key: 'qualificationFile', label: '职称附件', attachment: 'qualification', wide: true },
    { key: 'workStartedAt', label: '参加工作时间', date: true }, { key: 'joinedAt', label: '来单位时间', date: true, wide: true },
    { key: 'department', label: '所在部门', required: true }, { key: 'position', label: '岗位/职务', required: true, wide: true },
    { key: 'testingScope', label: '检测/业务范围', full: true, area: true }, { key: 'inspectionScope', label: '检查/业务范围', full: true, area: true }, { key: 'notes', label: '备注', full: true, area: true },
  ] },
]
const profileKeys = ['formerName', 'birthAddress', 'socialSecurityNumber', 'degree'] as const
const departments = computed(() => registrationDepartments.filter(d => currentActor.value.scope === 'all' || d.id === currentActor.value.departmentId))
const age = computed(() => {
  const birth = props.draft.birthDate, today = clientToday()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(birth) || birth > today) return ''
  return String(Number(today.slice(0, 4)) - Number(birth.slice(0, 4)) - Number(today.slice(5) < birth.slice(5)))
})
function value(key: string) { return key === 'age' ? age.value : profileKeys.includes(key as typeof profileKeys[number]) ? props.draft.profile[key as typeof profileKeys[number]] : props.draft[key as PersonnelKey] }
function set(key: string, text: string) {
  if (profileKeys.includes(key as typeof profileKeys[number])) props.draft.profile[key as typeof profileKeys[number]] = text
  else props.draft[key as PersonnelKey] = text
  if (key === 'name') props.draft.profile.accountId = ''
}
function options(key: string) { return personnelOptions[key as PersonnelKey | 'degree'] }
</script>
<template>
  <section v-for="section in sections" :key="section.title" :aria-label="section.title" class="mb-3">
    <h6 class="border-bottom pb-2 mb-2">{{ section.title }}</h6>
    <div class="row g-2">
      <div v-for="f in section.fields" :key="f.key" class="col-12" :class="f.full ? '' : f.wide ? 'col-lg-8' : 'col-lg-4'">
        <div class="row g-2 align-items-center">
          <label :for="`personnel-${f.key}`" class="col-12 col-sm-auto col-form-label w-auto">{{ f.label }}<span v-if="f.required" class="text-danger ms-1" aria-hidden="true">*</span></label>
          <div class="col">
            <div v-if="f.attachment" class="d-flex align-items-center gap-2"><span class="text-muted">{{ draft.profile.attachments[f.attachment].length }} 个附件</span><button :id="`personnel-${f.key}`" :data-validation-key="f.key" type="button" class="btn btn-light" :disabled="busy" :aria-label="`管理${f.label}`" @click="$emit('attachment', f.attachment)">{{ readonly ? '查看' : '浏览' }}</button></div>
            <select v-else-if="f.key === 'department' || f.key === 'gender'" :id="`personnel-${f.key}`" :data-validation-key="f.key" :aria-label="f.label" :value="value(f.key)" class="form-select" :disabled="readonly || busy" :required="f.required" @change="set(f.key, ($event.target as HTMLSelectElement).value)"><template v-if="f.key === 'department'"><option value="">请选择</option><option v-for="d in departments" :key="d.id">{{ d.name }}</option></template><template v-else><option>男</option><option>女</option></template></select>
            <TemplateEditableSelect v-else-if="options(f.key)" :id="`personnel-${f.key}`" :data-validation-key="f.key" :label="f.label" :model-value="value(f.key)" :options="options(f.key)!" :readonly="readonly || busy" :required="f.required" :maxlength="1000" @update:model-value="set(f.key, $event)" />
            <textarea v-else-if="f.area" :id="`personnel-${f.key}`" :data-validation-key="f.key" :aria-label="f.label" :value="value(f.key)" class="form-control" rows="2" maxlength="1000" :disabled="readonly || busy" @input="set(f.key, ($event.target as HTMLTextAreaElement).value)"></textarea>
            <TemplateDate v-else-if="f.date" :id="`personnel-${f.key}`" :data-validation-key="f.key" :aria-label="f.label" :model-value="value(f.key)" :required="f.required" :disabled="readonly || busy" within-modal @update:model-value="set(f.key, $event)" />
            <div v-else class="d-flex gap-2" data-field-control>
              <input :id="`personnel-${f.key}`" :data-validation-key="f.key" :aria-label="f.label" :value="value(f.key)" type="text" class="form-control" size="1" maxlength="1000" :required="f.required" :readonly="f.key === 'age'" :disabled="readonly || busy" @input="set(f.key, ($event.target as HTMLInputElement).value)" />
              <button v-if="f.key === 'name'" id="personnel-select-name" type="button" class="btn btn-light text-nowrap" :disabled="readonly || busy" aria-label="选择人员" @click="$emit('person')">选择</button>
            </div>
            <AttachmentDraftStatus v-if="f.attachment" :files="draft.profile.attachments[f.attachment]" />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
