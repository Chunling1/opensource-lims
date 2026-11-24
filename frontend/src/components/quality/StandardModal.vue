<script setup lang="ts">
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyStandard, canManageStandards, standardExtensionDays, standardQualifications, type StandardRow, type StandardOptions } from '../../types/quality/standards'
import TemplateDate from '../common/TemplateDate.vue'
import { clientToday } from '../../services/common/date'
import { currentActor } from '../../stores/session'
const props = defineProps<{ mode: 'new' | 'edit' | 'view' | 'delete'; row?: StandardRow }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const record = ref(props.row), loading = ref(false), busy = ref(false), loaded = ref(props.mode === 'delete'), error = ref<ErrorValue>('')
const draft = reactive({ ...emptyStandard(), implementedAt: clientToday(), departmentIds: [currentActor.value.departmentId] })
const extensionDays = computed(() => standardExtensionDays(draft.abolished, draft.abolishedAt, clientToday()))
const choices = ref<StandardOptions>({ departments: [], locations: [] })
const readonly = computed(() => props.mode === 'view' || !canManageStandards(currentActor.value) || busy.value)
const title = computed(() => `${{ new: '新增', edit: '编辑', view: '查看', delete: '删除' }[props.mode]}检测标准基础信息`)
const leave = useFormLeaveGuard(() => draft, () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value, () => busy.value)
async function closeForm() { if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (busy.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; error.value = ''; loaded.value = false
  try {
    const [options, result] = await Promise.all([registrationDemo.standardOptions(request.signal), props.row ? registrationDemo.standardDetail(props.row.id, request.signal) : Promise.resolve(undefined)])
    if (alive && !request.signal.aborted) { choices.value = options; if (result) { record.value = result; Object.assign(draft, result) }; loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save() {
  if (!canManageStandards(currentActor.value) || busy.value || loading.value || !loaded.value || props.mode === 'view') return

  busy.value = true; error.value = ''
  try {
    if (props.mode === 'delete') await registrationDemo.deleteStandard(record.value!.id, record.value!.version)
    else await registrationDemo.saveStandard({ ...draft, quantity: draft.quantity === null || String(draft.quantity) === '' ? null : Number(draft.quantity), ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) })
    if (alive) { leave.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode !== 'delete') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal guard-close open :title="title" :size="mode === 'delete' ? undefined : 'lg'" :busy="busy" :loading="loading" scrollable :body-class="mode === 'delete' ? 'py-2' : undefined" @close="closeForm">
    <p v-if="mode === 'delete'" class="mb-0 text-break">确认删除检测标准基础信息“{{ record?.name }}”？</p>
    <form v-else-if="loaded" id="standard-form" @submit.prevent="save">
      <fieldset :disabled="readonly" class="row g-3">
        <div class="col-12 col-md-6"><label for="standard-controlNumber" class="form-label">受控号</label><input id="standard-controlNumber" v-model="draft.controlNumber" data-validation-key="controlNumber" class="form-control" maxlength="200"  /></div>
        <div class="col-12 col-md-6"><label for="standard-code" class="form-label">标准编号<span class="text-danger ms-1" aria-hidden="true">*</span></label><input id="standard-code" v-model="draft.code" data-validation-key="code" class="form-control" maxlength="200" required /></div>
        <div class="col-12 col-md-8"><label for="standard-name" class="form-label">标准名称<span class="text-danger ms-1" aria-hidden="true">*</span></label><input id="standard-name" v-model="draft.name" data-validation-key="name" class="form-control" maxlength="200" required /></div>
        <div class="col-12 col-md-4 d-flex align-items-end pb-md-2"><label class="form-check mb-0"><input v-model="draft.outsideScope" type="checkbox" class="form-check-input" /><span class="form-check-label">是否在资质范围外</span></label></div>
        <div class="col-12 col-md-6"><label for="standard-category" class="form-label">类别</label><input id="standard-category" v-model="draft.category" data-validation-key="category" maxlength="200" class="form-control" /></div>
        <div class="col-12 col-md-6"><label for="standard-location" class="form-label">存放地点</label><input id="standard-location" v-model="draft.location" data-validation-key="location" class="form-control" maxlength="200"  /></div>
        <div class="col-12 col-md-6"><label for="standard-quantity" class="form-label">发放数量</label><input id="standard-quantity" v-model.number="draft.quantity" data-validation-key="quantity" class="form-control" type="number" min="0" max="1000000" step="1" /></div>
        <div class="col-12 col-md-6"><label for="standard-issuer" class="form-label">发放人</label><input id="standard-issuer" v-model="draft.issuer" data-validation-key="issuer" class="form-control" maxlength="200"  /></div>
        <div class="col-12 col-md-6"><label for="standard-implementedAt" class="form-label">实施日期<span class="text-danger ms-1" aria-hidden="true">*</span></label><TemplateDate id="standard-implementedAt" v-model="draft.implementedAt" data-validation-key="implementedAt" required within-modal :disabled="readonly" /></div>
        <div class="col-12 col-md-6"><label class="form-check mb-2"><input v-model="draft.abolished" class="form-check-input" type="checkbox" /><span class="form-check-label">作废日期</span></label><TemplateDate id="standard-abolishedAt" v-model="draft.abolishedAt" data-validation-key="abolishedAt" :required="draft.abolished" within-modal :disabled="readonly || !draft.abolished" aria-label="作废日期" /></div>
        <div class="col-12 col-md-6"><label for="standard-extensionDays" class="form-label">延期时间（天）</label><input id="standard-extensionDays" :value="extensionDays ?? ''" class="form-control bg-light" readonly /></div>
        <div class="col-12 col-md-6"><label for="standard-replacementCode" class="form-label">替换标准号</label><input id="standard-replacementCode" v-model="draft.replacementCode" data-validation-key="replacementCode" class="form-control" maxlength="200" :disabled="!draft.abolished" /></div>
        <div class="col-12 col-md-6"><label for="standard-qualification" class="form-label">标准资质类别</label><select id="standard-qualification" v-model="draft.qualification" data-validation-key="qualification" class="form-select"><option value="">请选择</option><option v-for="value in standardQualifications" :key="value" :value="value">{{ value }}</option></select></div>
        <div class="col-12 col-md-6"><label for="standard-english" class="form-label">是否英文标准</label><select id="standard-english" v-model="draft.english" class="form-select"><option :value="false">否</option><option :value="true">是</option></select></div>
        <div class="col-12"><label for="standard-notes" class="form-label">备注</label><input id="standard-notes" v-model="draft.notes" data-validation-key="notes" class="form-control" maxlength="2000" /></div>
        <div class="col-12"><span id="standard-departments-label" class="form-label d-block">使用部门</span><div class="border rounded p-3" role="group" aria-labelledby="standard-departments-label" data-validation-key="departmentIds"><div class="row g-2"><div v-for="department in choices.departments" :key="department.id" class="col-12 col-sm-6 col-lg-4"><label class="form-check mb-0"><input v-model="draft.departmentIds" :value="department.id" type="checkbox" class="form-check-input" /><span class="form-check-label">{{ department.name }}</span></label></div></div></div></div>
      </fieldset>
    </form>
    <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" :class="{ 'mt-3': loaded && error }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="closeForm">{{ mode === 'view' ? '返回' : '取消' }}</button>
      <button v-if="mode === 'delete'" type="button" class="btn btn-danger" :disabled="busy || loading || !loaded" @click="save"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在删除…' : '确认删除' }}</button>
      <button v-else-if="mode !== 'view'" type="submit" form="standard-form" class="btn btn-primary" :disabled="busy || loading || !loaded"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在保存…' : '保存' }}</button>
    </template>
  </BootstrapModal>
  <FormLeaveConfirmation :guard="leave" />
</template>
