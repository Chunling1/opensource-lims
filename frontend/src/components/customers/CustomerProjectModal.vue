<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TemplateEditableSelect from '../common/TemplateEditableSelect.vue'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyProject, projectFields, projectSections, type CustomerProject, type ProjectOptions, type ProjectField } from '../../types/customers/projects'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'batch' | 'delete'; row?: CustomerProject; ids?: string[] }>()
const emit = defineEmits<{ close: []; saved: [again: boolean] }>()
const draft = reactive(emptyProject(props.mode === 'batch')), checked = ref<string[]>([]), copied = ref(false)
const loading = ref(false), loaded = ref(false), busy = ref(false), error = ref<ErrorValue>(''), confirmBatch = ref(false)
const options = ref<ProjectOptions>({ organizations: [], regions: {} })
const record = ref(props.row)
// Explicit rows keep the screenshot's related fields together and fill the same grid.
type LayoutItem = string | [string, number]
const layoutRows: Record<string, LayoutItem[][]> = {
  '委托人信息': [['client', 'clientPhone']],
  '委托单位信息': [['customer', 'customerAddress'], ['customerLegal', 'customerPhone', 'customerPostcode']],
  '工程基本属性': [
    ['code', 'supervisionNumber', 'tradingCode'], ['name', 'subproject'], ['address', 'area'],
    ['province', 'city', 'district'], ['regionCode', 'buildingArea', 'floors'],
    ['projectType', 'buildingNature', 'structure'], ['director', 'manager'],
  ],
  '工程主体单位': ['developer', 'builder', 'supervisor', 'designer', 'surveyor'].flatMap(key => [[`${key}Code`, `${key}Contact`, `${key}Phone`], [key]]),
  '监督信息': [[['authorityCode', 4], ['authority', 8]], ['inspectorCode', 'inspector', 'inspectorPhone']],
  '见证取样信息': [['witnessUnit'], ['witness', 'witnessCode', 'witnessPhone'], ['samplingUnit'], [['sampler', 4], ['samplingPlace', 8]]],
}
const fieldMap = new Map<string, ProjectField>([...projectFields, { key: 'code', label: '工程编号' }].map(field => [field.key, field]))
const columnClasses: Record<number, string> = { 4: 'col-12 col-lg-4', 6: 'col-12 col-lg-6', 8: 'col-12 col-lg-8', 12: 'col-12' }
const labelClasses: Record<number, string> = { 4: 'col-4 col-lg-6', 6: 'col-4', 8: 'col-4 col-lg-3', 12: 'col-4 col-lg-2' }
const controlClasses: Record<number, string> = { 4: 'col-8 col-lg-6', 6: 'col-8', 8: 'col-8 col-lg-9', 12: 'col-8 col-lg-10' }
const formSections = computed(() => projectSections.map(section => ({
  title: section.title,
  rows: layoutRows[section.title]!.map(row => {
    const items = row.filter(item => props.mode !== 'batch' || item !== 'code')
    return items.map(item => {
      const key = typeof item === 'string' ? item : item[0]
      return { field: fieldMap.get(key)!, span: typeof item === 'string' ? 12 / items.length : item[1] }
    })
  }),
})))
const readonly = computed(() => props.mode === 'view')
const title = computed(() => copied.value ? '新增工程信息' : `${{ new: '新增', edit: '修改', view: '查看', batch: '批量修改', delete: '删除' }[props.mode]}工程${props.mode === 'delete' ? '' : '信息'}`)
const leave = useFormLeaveGuard(() => ({ draft, checked: checked.value, copied: copied.value }), () => !readonly.value && props.mode !== 'delete' && loaded.value && !loading.value, () => busy.value)
async function close() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  controller?.abort(); const request = controller = new AbortController(); loading.value = true; loaded.value = false; error.value = ''
  try {
    const [choices, row] = await Promise.all([registrationDemo.projectOptions(request.signal), props.row && props.mode !== 'delete' ? registrationDemo.customerProject(props.row.id, request.signal) : undefined])
    if (!alive || request.signal.aborted) return
    options.value = choices
    if (row) { record.value = row; for (const field of projectFields) draft[field.key] = row[field.key] || '' }
    loaded.value = true
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
function copy() { if (!loaded.value || busy.value) return; copied.value = true; error.value = '' }
async function save(again = false) {
  if (busy.value || !loaded.value || loading.value || readonly.value) return
  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteCustomerProject(record.value!.id)
    else if (props.mode === 'batch') await registrationDemo.batchCustomerProjects(props.ids || [], Object.fromEntries(checked.value.map(key => [key, draft[key] || ''])))
    else await registrationDemo.saveCustomerProject({ ...draft, ...(!copied.value && props.mode === 'edit' ? { id: record.value!.id } : {}) })
    if (alive) { leave.commit(); emit('saved', again) }
  } catch (issue) { if (alive) { confirmBatch.value = false; error.value = normalizeError(issue) } }
  finally { if (alive) busy.value = false }
}
function submit() { if (props.mode === 'batch') confirmBatch.value = true; else void save() }
void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal open guard-close :title="title" :size="mode === 'delete' ? undefined : 'xl'" scrollable fullscreen-mobile :busy="busy" :loading="loading" @close="close">
    <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除工程“{{ row?.name }}”（{{ row?.code }}）？此操作无法撤销。</p>
    <template v-else-if="loaded">
      <p v-if="mode === 'batch'" class="text-muted">已选择 {{ ids?.length }} 个工程。仅修改勾选字段；勾选后留空将清空该字段，工程名称不可清空。</p>
      <p v-if="copied" class="text-primary" role="status">已复制当前表单为新工程，保存时生成新的工程编号。</p>
      <form id="customer-project-form" novalidate @submit.prevent="submit">
        <fieldset :disabled="readonly || busy">
          <section v-for="section in formSections" :key="section.title" class="card mb-3" :aria-label="section.title">
            <div class="card-header"><h6 class="mb-0">{{ section.title }}</h6></div>
            <div class="card-body">
              <div class="vstack gap-3">
                <div v-for="(rowFields, rowIndex) in section.rows" :key="rowIndex" class="row g-3">
                  <div v-for="{ field, span } in rowFields" :key="field.key" :class="columnClasses[span]">
                    <div class="row g-2 align-items-start">
                      <div :class="labelClasses[span]" class="d-flex align-items-start justify-content-end gap-2">
                        <div v-if="mode === 'batch'" class="col-form-label flex-shrink-0"><input v-model="checked" :value="field.key" type="checkbox" class="form-check-input" :aria-label="`修改${field.label}`" /></div>
                        <label :for="`project-${field.key}`" class="col-form-label text-end">{{ field.label }}<span v-if="field.key === 'name' && !readonly" class="text-danger ms-1" aria-hidden="true">*</span></label>
                      </div>
                      <fieldset :class="controlClasses[span]" :disabled="mode === 'batch' && !checked.includes(field.key)">
                        <input v-if="field.key === 'code'" id="project-code" :value="copied ? '' : record?.code || ''" class="form-control" disabled placeholder="保存后自动生成" />
                        <TemplateEditableSelect v-else-if="field.kind === 'unit' || field.kind === 'region'" :id="`project-${field.key}`" v-model="draft[field.key]!" :label="field.label" :options="field.kind === 'unit' ? options.organizations : options.regions[field.key] || []" :readonly="readonly || busy || mode === 'batch' && !checked.includes(field.key)" :maxlength="500" :data-validation-key="field.key" />
                        <select v-else-if="field.kind === 'select'" :id="`project-${field.key}`" v-model="draft[field.key]" class="form-select" :data-validation-key="field.key"><option value="">请选择</option><option v-for="option in field.options" :key="option">{{ option }}</option></select>
                        <input v-else :aria-label="field.label" :id="`project-${field.key}`" v-model="draft[field.key]" class="form-control" :data-validation-key="field.key" :required="field.key === 'name'" :inputmode="field.kind === 'number' ? 'decimal' : undefined" maxlength="500" />
                      </fieldset>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </fieldset>
      </form>
    </template>
    <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ readonly ? '返回' : '取消' }}</button>
      <button v-if="!readonly && mode !== 'batch' && mode !== 'delete'" type="button" class="btn btn-light" :disabled="busy || !loaded || loading" @click="copy">复制</button>
      <button v-if="!readonly && mode !== 'batch' && mode !== 'delete'" type="button" class="btn btn-light" :disabled="busy || !loaded || loading" @click="save(true)">保存并新增</button>
      <button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || !loaded" @click="save()">{{ busy ? '正在删除…' : '确认删除' }}</button>
      <button v-else-if="!readonly" type="submit" form="customer-project-form" class="btn btn-primary" :disabled="busy || loading || !loaded || mode === 'batch' && !checked.length">{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="confirmBatch" title="确认批量修改工程" :busy="busy" @close="confirmBatch = false"><p>确定修改所选 {{ ids?.length }} 个工程的以下字段？</p><ul><li v-for="key in checked" :key="key">{{ projectFields.find(field => field.key === key)?.label }}：{{ draft[key] || '清空' }}</li></ul><ErrorNotice :error="error" /><template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="confirmBatch = false">取消</button><button type="button" class="btn btn-primary" :disabled="busy" @click="save()">{{ busy ? '正在保存…' : '确认修改' }}</button></template></ConfirmationModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
