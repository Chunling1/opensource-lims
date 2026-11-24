<script setup lang="ts">
import ConfirmationModal from '../common/ConfirmationModal.vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { sampleCopyTypes, availableSampleCopyStates, sampleCopyNextState, sampleCopyReportSuffix, type SampleCopyRow } from '../../types/testing/sampleCopy'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'

const props = defineProps<{ sample: SampleCopyRow }>()
const emit = defineEmits<{ close: []; copied: [code: string] }>()
const types = sampleCopyTypes
const sampleType = ref<typeof types[number]>('分项/阶段性报告样品')
const status = ref('委托登记中'), department = ref(''), suffix = ref(''), confirming = ref(false)
const editable = computed(() => sampleType.value === types[0])
const targetStates = computed(() => availableSampleCopyStates(props.sample.dataStatus))
const departments = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
const saving = ref(false), submitError = ref<ErrorValue>(''), requestId = crypto.randomUUID()
let active = true
async function loadDepartments() {
  loading.value = true; error.value = ''
  try {
    const result = await registrationDemo.sampleDefaults()
    if (active) departments.value = result.choices.testingDepartment || []
  } catch (issue) { if (active) error.value = normalizeError(issue) }
  finally { if (active) loading.value = false }
}
const effectiveDepartment = computed(() => editable.value ? department.value || props.sample.testingDepartment : props.sample.testingDepartment)
const reportCode = computed(() => props.sample.reportCode + sampleCopyReportSuffix(sampleType.value, suffix.value))
function review() { if (loading.value || error.value) return; suffix.value = suffix.value.trim(); if (editable.value && !suffix.value) return; submitError.value = ''; confirming.value = true }
function close() { if (saving.value) return; if (confirming.value) confirming.value = false; else emit('close') }
async function submit() {
  if (saving.value) return
  saving.value = true; submitError.value = ''
  try {
    const result = await registrationDemo.copySample(props.sample.id, { requestId, version: props.sample.version, sampleType: sampleType.value,
      dataStatus: status.value, testingDepartment: editable.value ? department.value : '', reportSuffix: sampleCopyReportSuffix(sampleType.value, suffix.value) })
    if (active) emit('copied', result.code)
  } catch (issue) { if (active) submitError.value = normalizeError(issue) }
  finally { if (active) saving.value = false }
}
onMounted(loadDepartments)
onBeforeUnmount(() => { active = false })
</script>
<template>
  <BootstrapModal :loading="loading" open title="复制样品" :busy="saving" size="lg" @close="close">
    <template v-if="!error">
      <p class="text-muted text-break">{{ sample.code }} · {{ sample.name }}</p>
      <form id="sample-copy-options" @submit.prevent="review">
        <fieldset class="mb-4">
          <legend class="visually-hidden">样品类型</legend>
          <div class="d-flex flex-wrap gap-3">
            <div v-for="(type, index) in types" :key="type" class="form-check">
              <input :id="`copy-kind-${index}`" v-model="sampleType" class="form-check-input" type="radio" name="copy-kind" :value="type" />
              <label :for="`copy-kind-${index}`" class="form-check-label">{{ type }}</label>
            </div>
          </div>
        </fieldset>
        <div class="row g-3 align-items-center">
          <div class="col-sm-4"><label for="copy-data-status" class="form-label mb-0">指定样品数据状态</label></div>
          <div class="col-sm-8"><select id="copy-data-status" v-model="status" class="form-select"><option v-for="state in targetStates" :key="state">{{ state }}</option></select></div>
          <div class="col-sm-4"><label for="copy-department" class="form-label mb-0">指定样品检测部门</label></div>
          <div class="col-sm-8"><select id="copy-department" :value="editable ? department : sample.testingDepartment" class="form-select" :disabled="!editable || loading || !!error" @change="department = ($event.target as HTMLSelectElement).value"><option value="">沿用原样品检测部门</option><option v-if="!editable && sample.testingDepartment && !departments.includes(sample.testingDepartment)" :value="sample.testingDepartment">{{ sample.testingDepartment }}</option><option v-for="name in departments" :key="name">{{ name }}</option></select></div>
          <div class="col-sm-4"><label for="copy-report-suffix" class="form-label mb-0">复制样品报告编号后缀<span v-if="editable" class="text-danger ms-1" aria-hidden="true">*</span></label></div>
          <div class="col-sm-8"><input id="copy-report-suffix" :value="editable ? suffix : sampleCopyReportSuffix(sampleType, '')" class="form-control" :disabled="!editable" :required="editable" maxlength="40" @input="suffix = ($event.target as HTMLInputElement).value" /></div>
        </div>

      </form>
    </template>
    <ErrorNotice :error="error" retry :busy="loading" @retry="loadDepartments" />
    <template #footer><button type="button" class="btn btn-light" :disabled="saving" @click="close">返回</button><button type="submit" form="sample-copy-options" class="btn btn-primary" :disabled="loading || saving || !!error" >确定</button></template></BootstrapModal>
  <ConfirmationModal v-if="confirming" title="确认复制样品" :busy="saving" @close="confirming = false">
    <div class="d-flex gap-3">
      <i class="ti ti-help text-primary fs-1" aria-hidden="true"></i>
      <div class="flex-grow-1 text-break">
        <p class="text-danger fw-semibold">请确认以下复制样品信息，确定后将无法修改！</p>
        <dl class="row mb-0">
          <dt class="col-sm-4">样品类型</dt><dd class="col-sm-8">{{ sampleType }}</dd>
          <dt class="col-sm-4">当前数据状态</dt><dd class="col-sm-8">{{ status }}</dd>
          <dt class="col-sm-4">待处理状态</dt><dd class="col-sm-8">{{ sampleCopyNextState(status) }}</dd>
          <dt class="col-sm-4">检测部门</dt><dd class="col-sm-8">{{ effectiveDepartment || '未指定' }}</dd>
          <dt class="col-sm-4">报告编号</dt><dd class="col-sm-8">{{ reportCode }}</dd>
        </dl>
        <ErrorNotice v-if="submitError" :error="submitError" />
      </div>
    </div>

    <template #footer><button type="button" class="btn btn-light" :disabled="saving" @click="confirming = false">取消</button><button type="button" class="btn btn-primary" :disabled="saving" @click="submit">{{ saving ? '正在复制…' : '确定' }}</button></template>
  </ConfirmationModal>
</template>
