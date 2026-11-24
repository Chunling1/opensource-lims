<script setup lang="ts">
import RegistrationReviewModal from '../../components/commissions/RegistrationReviewModal.vue'
import FormTabs from '../../components/forms/FormTabs.vue'
import { formIssues, isValidatableControl } from '../../components/forms/formValidation'
import { sampleFormTabs } from './forms/sampleSchema'
import RegistrationReportSettings from '../../components/commissions/RegistrationReportSettings.vue'
import type { ReportSettingsConfig } from '../../types/commissions/reportSettings'
import { isReportSettingsConfig, matchesReportSettings } from '../../services/commissions/reportSettings'
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import RegistrationCommissionFields from '../../components/commissions/RegistrationCommissionFields.vue'
import RegistrationSampleFields from '../../components/commissions/RegistrationSampleFields.vue'
import RegistrationTestPlanPicker from '../../components/commissions/RegistrationTestPlanPicker.vue'
import RegistrationTestBasisField from '../../components/commissions/RegistrationTestBasisField.vue'
import RegistrationTestBasisPicker from '../../components/commissions/RegistrationTestBasisPicker.vue'
import type { TestBasisSelection } from '../../types/commissions/testBasis'
import type { TestPlanNode } from '../../types/commissions/sampleForm'
import { emptySampleDetails, sampleDateKeys, type SampleFormOptions } from '../../types/commissions/sampleForm'
import { clientToday } from '../../services/common/date'
import { copySampleCommission, emptySampleCommission } from '../../types/commissions/sampleCommission'
import { commissionDetailKeys, emptyCommissionDetails } from '../../types/commissions/commissionForm'
import PageHeading from '../../components/common/PageHeading.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import RegistrationCommissionPicker from '../../components/commissions/RegistrationCommissionPicker.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { registrationContext, registrationReturn, registrationCanWrite, registrationCanLink, registrationCanAddSample, workspaceCanEdit, workspaceActions, demoProjects } from '../../services/commissions/registrationService'
import { currentActor } from '../../stores/session'
import { AppError, isOperationalError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { notifyUploadLeaveBlocked } from '../../components/common/useFileUpload'
import { useUnsavedChanges } from '../../components/common/useUnsavedChanges'
import type { RegistrationKind, RegistrationCommission, RegistrationSample, RegistrationCommissionInput, RegistrationSampleInput } from '../../types/commissions/registration'

const route = useRoute(), router = useRouter()
const context = computed(() => registrationContext(route.path))
const kind = computed(() => route.params.kind as RegistrationKind), isCommission = computed(() => kind.value === 'commissions'), id = computed(() => String(route.params.id)), creating = computed(() => id.value === 'new'), editing = computed(() => creating.value || route.path.endsWith('/edit'))
const returnTo = computed(() => registrationReturn(route.query.returnTo, context.value.root)), fixedCommission = computed(() => creating.value && !isCommission.value && typeof route.query.commissionId === 'string' ? route.query.commissionId : '')
const candidateCommissions = computed(() => creating.value && !isCommission.value && typeof route.query.commissionIds === 'string' ? [...new Set(route.query.commissionIds.split(',').filter(Boolean))] : undefined)
const reviewing = computed(() => context.value.review && !isCommission.value && route.path.endsWith('/assess'))
const reviewRecord = ref<RegistrationSample>()
const reviewActions = computed(() => sampleRecord.value ? workspaceActions(currentActor.value, 'samples', sampleRecord.value, 'review') : [])
const title = computed(() => reviewing.value ? '评审样品' : `${editing.value ? creating.value ? '新增' : context.value.review ? '编辑' : '修改' : ''}${isCommission.value ? '委托' : '样品'}${editing.value ? '' : '详情'}`)
const record = ref<RegistrationCommission | RegistrationSample>(), order = ref<RegistrationCommission>(), pickerOpen = ref(false)
const commissionRecord = computed(() => record.value && !('category' in record.value) ? record.value : undefined)
const sampleRecord = computed(() => record.value && 'category' in record.value ? record.value : undefined)
const empty = (): RegistrationCommissionInput & RegistrationSampleInput => ({ ...emptyCommissionDetails(), commissionInfo: emptySampleCommission(), details: emptySampleDetails(), handlingDepartmentId: currentActor.value.departmentId, name: '', customer: '', contract: '', dueDate: '', requirements: '', contact: '', phone: '', projects: [], notes: '', source: '客户送样', settlement: '预付', discount: 0, taxRate: 0, commissionId: '', category: '', quantity: 1, unit: '份', storage: '' })
const sampleTab = ref<'sample' | 'order'>('sample')
const testPlanOpen = ref(false), sampleFormElement = ref<HTMLFormElement>()
const sampleFieldErrors = ref<Record<string, string>>({})
const testPlanError = computed(() => sampleFieldErrors.value['sample-testPlan'] || '')
const testBasisOpen = ref(false), testBasisPending = ref(false), sampleUploadPending = ref(false)
function clearTestBasis() {
  form.details!.testBasisSeparators = []; form.details!.testBasisIds = []; form.details!.testBasis = ''; form.details!.englishBookMarks = false
}
function chooseTestPlan(plan?: TestPlanNode) {
  if (!creating.value || busy.value || !editable.value) return
  delete sampleFieldErrors.value['sample-testPlan']
  if (form.details!.testPlanId !== (plan?.id || '')) {
    clearTestBasis()
    Object.assign(form.details!, { assessmentStandard: '', assessmentStandardIds: [], assessmentStandardSeparators: [], assessmentEnglishBookMarks: false })
  }
  form.details!.testPlanId = plan?.id || ''; form.details!.testPlan = plan?.name || ''; form.details!.testPlanCode = plan?.code || ''
  testPlanOpen.value = false; testBasisOpen.value = false
}
function chooseTestBasis(selection: TestBasisSelection) {
  form.details!.testBasisSeparators = [...selection.separators]; form.details!.testBasisIds = [...selection.ids]; form.details!.testBasis = selection.text
  form.details!.englishBookMarks = selection.englishBookMarks; testBasisOpen.value = false
}
const sampleOptions = ref<SampleFormOptions>({ choices: {}, subprojectOptions: [] })
const form = reactive(empty()), baseline = ref(''), loading = ref(false), busy = ref(false), loadError = ref<ErrorValue>(''), error = ref<ErrorValue>(''), success = ref('')
const validationError = computed(() => isOperationalError(error.value) ? error.value : undefined)
const reportConfig = ref<ReportSettingsConfig>(), reportConfigLoading = ref(false), reportConfigError = ref<ErrorValue>('')
let reportRequest = 0, reportDefaultsPending = false
async function loadReportConfig() {
  const request = ++reportRequest, page = sequence
  reportConfigLoading.value = true; reportConfigError.value = ''; reportConfig.value = undefined
  try {
    const config = await registrationDemo.reportSettingsConfig()
    if (request !== reportRequest || page !== sequence) return
    if (!isReportSettingsConfig(config)) throw new AppError('UNAVAILABLE', '报告设置配置不可用，请重试。')
    reportConfig.value = config
    if (reportDefaultsPending) {
      const untouched = !baseline.value || baseline.value === JSON.stringify(form)
      form.details!.reportSettings = { ...config.defaults }; reportDefaultsPending = false
      if (untouched && baseline.value) baseline.value = JSON.stringify(form)
    }
  } catch (e) { if (request === reportRequest && page === sequence) reportConfigError.value = normalizeError(e) }
  finally { if (request === reportRequest && page === sequence) reportConfigLoading.value = false }
}
const dirty = computed(() => editing.value && !!baseline.value && baseline.value !== JSON.stringify(form))
const projectChoices = computed(() => !isCommission.value && creating.value && order.value?.projects.length ? order.value.projects : [...new Set([...demoProjects, ...form.projects])])
const canEdit = computed(() => !!record.value && workspaceCanEdit(currentActor.value, kind.value, record.value, context.value.workspace))
const editable = computed(() => creating.value ? !context.value.review && !context.value.inquiry && !context.value.changing && registrationCanWrite(currentActor.value, kind.value) : canEdit.value)
const successToast = ref<InstanceType<typeof TemplateToast>>()
const errorToast = ref<InstanceType<typeof TemplateToast>>()
const showBusyIndicator = ref(false)
let busyIndicatorTimer: ReturnType<typeof setTimeout> | undefined
watch(busy, value => {
  clearTimeout(busyIndicatorTimer)
  showBusyIndicator.value = false
  if (value) busyIndicatorTimer = setTimeout(() => { showBusyIndicator.value = true }, 400)
})
useUnsavedChanges(computed(() => dirty.value || sampleUploadPending.value))
let sequence = 0
let savedFormPath = ''
async function load(startReview = true) {
  const token = ++sequence; loading.value = true; busy.value = false; loadError.value = ''; error.value = ''; success.value = ''; baseline.value = ''; record.value = undefined; order.value = undefined; reviewRecord.value = undefined; pickerOpen.value = false; Object.assign(form, empty())
  try {
    sampleTab.value = 'sample'; testPlanOpen.value = false; testBasisOpen.value = false; sampleFieldErrors.value = {}
    reportRequest++; reportConfig.value = undefined; reportConfigError.value = ''; reportConfigLoading.value = false; reportDefaultsPending = !isCommission.value && creating.value
    if (!isCommission.value) {
      const options = await registrationDemo.sampleDefaults()
      if (token !== sequence) return
      sampleOptions.value = options
      if (creating.value) {
        const today = clientToday()
        for (const key of sampleDateKeys) form.details![key] = today
      }
    }
    if (creating.value && isCommission.value) {
      const defaults = await registrationDemo.commissionDefaults()
      if (token !== sequence) return
      form.commissionDate = defaults.commissionDate
    }
    let result = creating.value ? undefined : isCommission.value ? await registrationDemo.commission(id.value) : await registrationDemo.sample(id.value)
    if (token !== sequence) return
    if (startReview && reviewing.value && result && 'category' in result) {
      Object.assign(result, await registrationDemo.act('samples', result.id, 'start-review', result.version))
      if (token !== sequence) return
    }
    record.value = result
    if (result) for (const key of Object.keys(form)) { const v = result[key as keyof typeof result]; if (v !== undefined) Object.assign(form, { [key]: structuredClone(v) }) }
    if (isCommission.value && result) { form.commissionDate = 'commissionDate' in result ? result.commissionDate ?? result.createdAt.slice(0, 10) : result.createdAt.slice(0, 10); form.handlingDepartmentId = ('handlingDepartmentId' in result ? result.handlingDepartmentId : '') || result.departmentId }
    const linkedId = creating.value ? fixedCommission.value : ''
    const linked = linkedId ? await registrationDemo.commission(linkedId) : undefined
    if (token !== sequence) return
    order.value = linked
    if (creating.value && linked) { if (!registrationCanLink(currentActor.value)) throw new AppError('FORBIDDEN', '当前身份没有关联委托的权限。'); if (!registrationCanAddSample(currentActor.value, linked.status)) throw new AppError('BUSINESS_RULE', '已完成的委托不允许新增样品，请先取消完成。'); applyOrder(linked) }
    if (editing.value && !editable.value) throw new AppError('FORBIDDEN', '当前身份或记录状态不允许修改。')
    if (!isCommission.value) await loadReportConfig()
    if (token !== sequence) return
    baseline.value = JSON.stringify(form)
  } catch (e) { if (token === sequence) loadError.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
async function reviewSaved() { await router.push(returnTo.value) }
function applyOrder(next?: RegistrationCommission) {
  order.value = next; form.commissionId = next?.id ?? ''
  if (next) { form.commissionInfo = copySampleCommission(next); form.customer = next.customer; form.contact = next.contact; form.phone = next.phone; form.projects = [...next.projects] }
}
async function chooseOrder(id: string) {
  pickerOpen.value = false; busy.value = true; error.value = ''; const token = sequence
  try { const selected = await registrationDemo.commission(id); if (token === sequence) applyOrder(selected) }
  catch (e) { if (token === sequence) error.value = normalizeError(e) } finally { busy.value = false }
}
function submitCommission(event: Event) { void save((event as SubmitEvent).submitter?.getAttribute('value') === 'return') }
function clearSampleFieldError(event: Event) {
  const control = event.target
  if (isValidatableControl(control) && control.validity.valid) delete sampleFieldErrors.value[control.id]
}
async function validateSampleFields() {
  if (!sampleFormElement.value) return false
  const issues = formIssues(sampleFormElement.value, creating.value && !form.details?.testPlanId ? { 'sample-testPlan': '请选择检测方案。' } : {})
  sampleFieldErrors.value = Object.fromEntries(issues.map(({ control, message }) => [control.id, message]))
  const first = issues[0]?.control
  if (!first) return true
  const panel = first.closest('[role="tabpanel"]')
  if (panel) sampleTab.value = panel.id === 'sample-order-panel' ? 'order' : 'sample'
  await nextTick()
  first.focus({ preventScroll: true })
  first.scrollIntoView({ block: 'center', inline: 'nearest' })
  return false
}
async function submitSample(event: Event) {
  if (busy.value || testBasisPending.value || sampleUploadPending.value) return
  const action = (event as SubmitEvent).submitter?.getAttribute('value')
  await save(action === 'return')
}
async function save(returnToList = true) {
  if (!editing.value || busy.value || testBasisPending.value || sampleUploadPending.value || !editable.value) return false
  if (!isCommission.value && !await validateSampleFields()) return false
  if (busy.value || !editing.value || !editable.value) return false
  busy.value = true; error.value = ''; success.value = ''
  const token = sequence
  let submitted = false
  try {
    if (!isCommission.value) {
      if (reportConfigLoading.value || !reportConfig.value) throw new AppError('VALIDATION', '请先加载报告设置配置，可在报告设置区重试。')
      if (!matchesReportSettings(reportConfig.value, form.details!.reportSettings)) { sampleTab.value = 'sample'; throw new AppError('VALIDATION', '请检查报告设置中标记的选项后重新保存。') }
    }
    if (!isCommission.value && !form.commissionId) throw new AppError('VALIDATION', '请选择样品所属委托单。')
    if (candidateCommissions.value && !candidateCommissions.value.includes(form.commissionId)) throw new AppError('VALIDATION', '请选择已勾选委托中的一张委托。')
    const shared = { name: form.name, customer: isCommission.value ? form.customer : form.commissionInfo!.customer, contact: isCommission.value ? form.contact : form.commissionInfo!.contact, phone: isCommission.value ? form.phone : form.commissionInfo!.phone, projects: [...form.projects], notes: form.notes }
    submitted = true
    const saved = isCommission.value ? await registrationDemo.saveCommission({ ...Object.fromEntries(commissionDetailKeys.map(key => [key, form[key]])), ...shared, contract: form.contract, dueDate: form.dueDate, requirements: form.requirements, source: form.source, settlement: form.settlement, discount: typeof form.discount === 'number' ? form.discount : 0, taxRate: typeof form.taxRate === 'number' ? form.taxRate : 0 }, creating.value ? undefined : id.value, record.value?.version, context.value.workspace) : await registrationDemo.saveSample({ ...shared, commissionInfo: { ...form.commissionInfo! }, details: { ...form.details! }, commissionId: form.commissionId, category: form.category, quantity: form.quantity, unit: form.unit, storage: form.storage }, creating.value ? undefined : id.value, record.value?.version, reportConfig.value?.version, context.value.workspace)
    if (token !== sequence) return
    baseline.value = JSON.stringify(form); busy.value = false
    if (!returnToList) {
      record.value = saved
      for (const key of Object.keys(form)) {
        const value = saved[key as keyof typeof saved]
        if (value !== undefined) Object.assign(form, { [key]: structuredClone(value) })
      }
      baseline.value = JSON.stringify(form)
      if (creating.value) {
        savedFormPath = `${context.value.root}/${kind.value}/${saved.id}/edit`
        try { await router.replace({ path: savedFormPath, query: { returnTo: returnTo.value } }) }
        finally { savedFormPath = '' }
      }
      if (token === sequence) success.value = isCommission.value ? '委托已保存。' : '样品已保存。'
      return true
    }
    const destination = router.resolve(returnTo.value)
    await router.push({ path: destination.path, query: { ...destination.query, ...(isCommission.value || context.value.changing ? {} : { savedSample: saved.id }) } })
    return true
  } catch (e) {
    if (token === sequence) {
      const issue = normalizeError(e)
      if (submitted && !isCommission.value && issue.fieldErrors?.reportSettings) {
        sampleTab.value = 'sample'; await loadReportConfig()
        if (token === sequence) error.value = new AppError('VALIDATION', issue.message, { fieldErrors: issue.fieldErrors })
      } else error.value = issue
    }
    return false
  } finally { busy.value = false }
}
const confirmLeave = ref(false); let resolveLeave: ((leave: boolean) => void) | undefined
function guard() { if (busy.value || sampleUploadPending.value) { notifyUploadLeaveBlocked(); return false }; if (!dirty.value) return true; confirmLeave.value = true; return new Promise<boolean>(resolve => { resolveLeave = resolve }) }
function leave(value: boolean) { confirmLeave.value = false; if (value) baseline.value = ''; resolveLeave?.(value); resolveLeave = undefined }
onBeforeRouteLeave(guard); onBeforeRouteUpdate(guard)
watch(() => [route.params.kind, route.params.id, route.path], () => {
  if (savedFormPath === route.path && record.value?.id === id.value) return
  void load()
}, { immediate: true })
watch(currentActor, () => { success.value = ''; void load() })
watch([loading, error, success], () => {
  if (!editing.value || loading.value || loadError.value) { successToast.value?.hide(); errorToast.value?.hide(); return }
  if (error.value) errorToast.value?.show(); else errorToast.value?.hide()
  if (success.value && !error.value) successToast.value?.show(); else successToast.value?.hide()
}, { flush: 'post' })
onBeforeUnmount(() => { sequence++; clearTimeout(busyIndicatorTimer); resolveLeave?.(false) })
</script>

<template>
  <PageHeading :title="title" :parent-to="returnTo" />
  <LoadState :loading="loading" :error="loadError" :back-to="returnTo" @retry="load" />
  <template v-if="!loading && !loadError">
    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-3"><RouterLink class="btn btn-light" :to="returnTo"><i class="ti ti-arrow-left me-1" aria-hidden="true"></i>返回{{ context.title }}</RouterLink></div>
    <template v-if="!editing">
      <ErrorNotice :error="error" :latest-to="!creating ? `${context.root}/${kind}/${id}` : undefined" @reload="load" />
      <TemplateToast :message="success" tone="success" auto-show />
    </template>
    <form v-if="editing && isCommission" aria-label="委托表单" @submit.prevent="submitCommission">
      <fieldset :inert="busy" :aria-busy="busy">
        <RegistrationCommissionFields :form="form" :code="commissionRecord?.code" :owner="commissionRecord?.owner" />
      </fieldset>
      <div class="mb-4">
        <div class="d-flex align-items-center justify-content-end flex-wrap gap-2 pe-5"><span class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !showBusyIndicator }" role="status" aria-label="正在处理" :aria-hidden="!showBusyIndicator"></span><RouterLink class="btn btn-light" :to="returnTo">取消</RouterLink><button class="btn btn-outline-primary" type="submit" value="return" :aria-disabled="busy" :aria-busy="busy">保存并返回</button><button class="btn btn-primary" type="submit" value="stay" :aria-disabled="busy" :aria-busy="busy">保存</button></div>
      </div>
    </form>
    <form v-else-if="!isCommission" ref="sampleFormElement" aria-label="样品表单" novalidate @submit.prevent="submitSample" @input="clearSampleFieldError" @change="clearSampleFieldError">
      <fieldset :inert="busy" :aria-busy="busy">
        <section class="card" aria-label="检测设置">
          <div class="card-body"><div class="row g-3">
            <div class="col-md-6"><label for="sample-testPlan" class="form-label">检测方案<span v-if="creating" class="text-danger ms-1" aria-hidden="true">*</span></label><div class="input-group"><input id="sample-testPlan" :aria-required="creating" :aria-invalid="!!testPlanError" :aria-describedby="testPlanError ? 'sample-testPlan-error' : undefined" :class="{ 'is-invalid': testPlanError, 'bg-body-tertiary': !creating || !editing }" :value="form.details!.testPlanCode ? `${form.details!.testPlan}（${form.details!.testPlanCode}）` : form.details!.testPlan" class="form-control" readonly placeholder="请选择检测方案" /><button id="sample-testPlan-select" class="btn btn-light" v-if="creating && editing" type="button" aria-label="选择检测方案" @click="testPlanOpen = true"><i class="ti ti-search" aria-hidden="true"></i></button><button v-if="creating && editing && form.details!.testPlan" class="btn btn-light" type="button" aria-label="清除检测方案" @click="chooseTestPlan()"><i class="ti ti-x" aria-hidden="true"></i></button></div><div v-if="testPlanError" id="sample-testPlan-error" class="invalid-feedback d-block" role="alert">{{ testPlanError }}</div></div>
            <div class="col-md-6"><RegistrationTestBasisField :readonly="!editing" :text-value="form.details!.testBasis" :plan-id="form.details!.testPlanId" :ids="form.details!.testBasisIds" :separators="form.details!.testBasisSeparators" :english-book-marks="form.details!.englishBookMarks" @select="chooseTestBasis" @open="testBasisOpen = true" @clear="clearTestBasis" @pending="testBasisPending = $event" /></div>
          </div></div>
        </section>
        <FormTabs :tabs="sampleFormTabs" :model-value="sampleTab" label="样品表单分区" @update:model-value="!sampleUploadPending && (sampleTab = $event === 'order' ? 'order' : 'sample')" />
        <div v-show="sampleTab === 'order'" id="sample-order-panel" role="tabpanel" aria-labelledby="sample-order-tab"><RegistrationCommissionFields v-if="sampleTab === 'order'" :form="form.commissionInfo!" :code="form.commissionInfo?.code" :owner="form.commissionInfo?.owner" sample :readonly="!editing" :can-choose-commission="creating && !fixedCommission && registrationCanLink(currentActor)" @choose-commission="pickerOpen = true" @pending="sampleUploadPending = $event" /></div>
        <div v-show="sampleTab === 'sample'" id="sample-info-panel" role="tabpanel" aria-labelledby="sample-info-tab"><RegistrationSampleFields :errors="sampleFieldErrors" :readonly="!editing" :form="form" :options="sampleOptions" :code="sampleRecord?.code" :report-code="sampleRecord?.reportCode" :commission-code="form.commissionInfo?.code" :projects="projectChoices" :can-choose-commission="creating && !fixedCommission && registrationCanLink(currentActor)" @choose-commission="pickerOpen = true" @pending="sampleUploadPending = $event"><template #report-settings><RegistrationReportSettings :readonly="!editing" v-model="form.details!.reportSettings" :config="reportConfig" :loading="reportConfigLoading" :error="reportConfigError" @retry="loadReportConfig" /></template></RegistrationSampleFields></div>
      </fieldset>
      <div v-if="editing" class="d-flex align-items-center justify-content-end flex-wrap gap-2 mb-4 pe-5"><span class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !showBusyIndicator }" role="status" aria-label="正在处理" :aria-hidden="!showBusyIndicator"></span><RouterLink class="btn btn-light" :to="returnTo">取消</RouterLink><button class="btn btn-outline-primary" type="submit" value="return" :aria-disabled="busy || testBasisPending || sampleUploadPending" :disabled="testBasisPending || sampleUploadPending">保存并返回</button><button class="btn btn-primary" type="submit" value="stay" :aria-disabled="busy || testBasisPending || sampleUploadPending" :disabled="testBasisPending || sampleUploadPending">保存</button></div>
    </form>
    <template v-else-if="commissionRecord">
      <RegistrationCommissionFields :form="form" :code="commissionRecord.code" :owner="commissionRecord.owner" readonly />
    </template>
    <div v-if="reviewing && sampleRecord" class="d-flex align-items-center justify-content-end flex-wrap gap-2 mb-4 pe-5">
      <RouterLink class="btn btn-light" :to="returnTo">返回</RouterLink>
      <button v-if="reviewActions.some(action => action.id === 'review')" class="btn btn-primary" type="button" @click="reviewRecord = sampleRecord">评审</button>
    </div>
  </template>
  <RegistrationReviewModal :record="reviewRecord" @close="reviewRecord = undefined" @saved="reviewSaved" />
  <TemplateToast v-if="editing" ref="successToast" :message="success" tone="success" />
  <TemplateToast v-if="editing" ref="errorToast" message="" :title="validationError ? '操作提示' : '系统提示'" :tone="validationError ? 'warning' : 'danger'" :autohide="false"><ErrorNotice compact :error="error" :latest-to="!creating ? `${context.root}/${kind}/${id}` : undefined" :busy="busy" @reload="load" /></TemplateToast>
  <RegistrationCommissionPicker :open="pickerOpen" :ids="candidateCommissions" @close="pickerOpen = false" @select="chooseOrder" />
  <RegistrationTestPlanPicker v-if="creating && !isCommission" :open="testPlanOpen" :value-id="form.details?.testPlanId" :value="form.details?.testPlan" :value-code="form.details?.testPlanCode" @close="testPlanOpen = false" @select="chooseTestPlan" />
  <RegistrationTestBasisPicker :open="testBasisOpen" :plan-id="form.details!.testPlanId" :ids="form.details!.testBasisIds" :separators="form.details!.testBasisSeparators" :english-book-marks="form.details!.englishBookMarks" @close="testBasisOpen = false" @select="chooseTestBasis" />
  <BootstrapModal :open="confirmLeave" title="离开当前页面？" @close="leave(false)"><p class="mb-0">尚有未保存的资料，离开后这些修改将丢失。</p><template #footer><button class="btn btn-light" @click="leave(false)">继续编辑</button><button class="btn btn-danger" @click="leave(true)">放弃修改并离开</button></template></BootstrapModal>
</template>


