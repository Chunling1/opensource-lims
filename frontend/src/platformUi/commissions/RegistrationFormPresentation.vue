<script setup lang="ts">
import SourceReportSelect from './SourceReportSelect.vue'
import RegistrationReviewModal from '../../components/commissions/RegistrationReviewModal.vue'
import FormTabs from '../../components/forms/FormTabs.vue'
import RegistrationReportSettings from '../../components/commissions/RegistrationReportSettings.vue'
import RegistrationCommissionFields from './RegistrationCommissionFields.vue'
import RegistrationSampleFields from './RegistrationSampleFields.vue'
import RegistrationTestPlanPicker from './RegistrationTestPlanPicker.vue'
import RegistrationTestBasisField from './RegistrationTestBasisField.vue'
import RegistrationTestBasisPicker from './RegistrationTestBasisPicker.vue'
import PageHeading from '../../components/common/PageHeading.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import LoadState from '../../components/common/LoadState.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TemplateToast from '../../components/common/TemplateToast.vue'
import RegistrationCommissionPicker from './RegistrationCommissionPicker.vue'
import TemplateEditableSelect from '../../components/common/TemplateEditableSelect.vue'
import SchemaForm from '../../components/forms/SchemaForm.vue'
import { toRefs } from 'vue'
import { createRegistrationFormPresentation, ControllerReturnLink as RouterLink } from './registrationFormPresentation'
const props = defineProps<{context: any}>()
const state=createRegistrationFormPresentation(props.context)
const {busy,candidateCommissions,chooseOrder,chooseTestBasis,chooseTestPlan,clearSampleFieldError,clearTestBasis,commissionRecord,confirmLeave,context,creating,currentActor,editing,error,errorToast,fixedCommission,form,id,isCommission,kind,leave,load,loadError,loadReportConfig,loading,pickerOpen,projectChoices,registrationCanLink,reportConfig,reportConfigError,reportConfigLoading,returnTo,reviewActions,reviewRecord,reviewSaved,reviewing,sampleFieldErrors,sampleFormElement,sampleFormTabs,sampleOptions,sampleRecord,sampleTab,sampleUploadPending,showBusyIndicator,submitCommission,submitSample,success,successToast,testBasisOpen,testBasisPending,testPlanError,testPlanOpen,title,validationError}=toRefs(state)
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
            <div class="col-md-6"><RegistrationTestBasisField :readonly="!editing" :text-value="form.details!.testBasis" :plan-id="form.details?.testPlanId || ''" :ids="form.details?.testBasisIds || []" :separators="form.details?.testBasisSeparators || []" :english-book-marks="!!form.details?.englishBookMarks" @select="chooseTestBasis" @open="testBasisOpen = true" @clear="clearTestBasis" @pending="testBasisPending = $event" /></div>
          </div></div>
        </section>
        <FormTabs :tabs="sampleFormTabs" :model-value="sampleTab" label="样品表单分区" @update:model-value="!sampleUploadPending && (sampleTab = $event === 'order' ? 'order' : 'sample')" />
        <div v-show="sampleTab === 'order'" id="sample-order-panel" role="tabpanel" aria-labelledby="sample-order-tab"><RegistrationCommissionFields v-if="sampleTab === 'order'" :form="form.commissionInfo!" :code="form.commissionInfo?.code" :owner="form.commissionInfo?.owner" sample :readonly="!editing" :can-choose-commission="creating && !fixedCommission && registrationCanLink(currentActor)" @choose-commission="pickerOpen = true" @pending="sampleUploadPending = $event" /></div>
        <div v-show="sampleTab === 'sample'" id="sample-info-panel" role="tabpanel" aria-labelledby="sample-info-tab"><RegistrationSampleFields :errors="sampleFieldErrors" :readonly="!editing" :form="form" :options="sampleOptions" :code="sampleRecord?.code" :report-code="sampleRecord?.reportCode" :commission-code="form.commissionInfo?.code" :projects="projectChoices" :can-choose-commission="creating && !fixedCommission && registrationCanLink(currentActor)" @choose-commission="pickerOpen = true" @pending="sampleUploadPending = $event"><template #report-settings><RegistrationReportSettings :readonly="!editing" v-model="form.details!.reportSettings" :config="reportConfig" :loading="reportConfigLoading" :error="reportConfigError" @retry="loadReportConfig" /></template></RegistrationSampleFields></div>
        <SchemaForm :schema="state.backendSchema" :model="context" :readonly="!editing">
          <template #baseReport><SourceReportSelect v-model="state.controller.s.baseReportNo" @selected="state.controller.sourceSample = { reportNo: $event.mainReportNo || $event.reportNo, sampleNo: $event.sampleNo }" :category="state.controller.s.reportCategory" :disabled="!editing || busy || state.controller.s.reportCategory === '普通' || state.controller.schemeLocked" /></template>
          <template #capability><TemplateEditableSelect id="registration-capability" label="资质参数" :model-value="state.capabilityText" :options="state.capabilityLabels" :loading="state.controller.capabilityLoading" :readonly="!editing || !form.details?.testBasisIds.length" multiple @update:model-value="state.chooseCapabilities" /><ErrorNotice :error="state.controller.capabilityError" retry @retry="state.controller.loadCapabilityItems()" /></template>
          <template #technical><TemplateEditableSelect id="registration-technical" label="检测技术子项目" :model-value="state.technicalText" :options="state.technicalLabels" :loading="state.technicalLoading" :readonly="!editing" multiple @update:model-value="state.chooseTechnical" /><ErrorNotice :error="state.technicalError" retry @retry="state.loadTechnical()" /></template>
        </SchemaForm>
      </fieldset>
      <div v-if="editing" class="d-flex align-items-center justify-content-end flex-wrap gap-2 mb-4 pe-5"><span class="spinner-border spinner-border-sm text-primary" :class="{ invisible: !showBusyIndicator }" role="status" aria-label="正在处理" :aria-hidden="!showBusyIndicator"></span><RouterLink class="btn btn-light" :to="returnTo">取消</RouterLink><button class="btn btn-outline-primary" type="submit" value="return" :aria-disabled="busy || testBasisPending || sampleUploadPending" :disabled="testBasisPending || sampleUploadPending">保存并返回</button><button class="btn btn-primary" type="submit" value="stay" :aria-disabled="busy || testBasisPending || sampleUploadPending" :disabled="testBasisPending || sampleUploadPending">保存</button></div>
    </form>
    <template v-else-if="commissionRecord">
      <RegistrationCommissionFields :form="form" :code="commissionRecord.code" :owner="commissionRecord.owner" readonly />
    </template>
    <div v-if="reviewing && sampleRecord" class="d-flex align-items-center justify-content-end flex-wrap gap-2 mb-4 pe-5">
      <RouterLink class="btn btn-light" :to="returnTo">返回</RouterLink>
      <button v-if="reviewActions.some((action: any) => action.id === 'review')" class="btn btn-primary" type="button" @click="reviewRecord = sampleRecord">评审</button>
    </div>
  </template>
  <RegistrationReviewModal :record="reviewRecord" @close="reviewRecord = undefined" @saved="reviewSaved" />
  <TemplateToast v-if="editing" ref="successToast" :message="success" tone="success" />
  <TemplateToast v-if="editing" ref="errorToast" message="" :title="validationError ? '操作提示' : '系统提示'" :tone="validationError ? 'warning' : 'danger'" :autohide="false"><ErrorNotice compact :error="error" :latest-to="!creating ? `${context.root}/${kind}/${id}` : undefined" :busy="busy" @reload="load" /></TemplateToast>
  <RegistrationCommissionPicker :open="pickerOpen" :ids="candidateCommissions" @close="pickerOpen = false" @select="chooseOrder" />
  <RegistrationTestPlanPicker v-if="creating && !isCommission" :open="testPlanOpen" :value-id="form.details?.testPlanId" :value="form.details?.testPlan" :value-code="form.details?.testPlanCode" @close="testPlanOpen = false" @select="chooseTestPlan" />
  <RegistrationTestBasisPicker :open="testBasisOpen" :plan-id="form.details?.testPlanId || ''" :ids="form.details?.testBasisIds || []" :separators="form.details?.testBasisSeparators || []" :english-book-marks="!!form.details?.englishBookMarks" @close="testBasisOpen = false" @select="chooseTestBasis" />
  <BootstrapModal :open="confirmLeave" title="离开当前页面？" @close="leave(false)"><p class="mb-0">尚有未保存的资料，离开后这些修改将丢失。</p><template #footer><button class="btn btn-light" @click="leave(false)">继续编辑</button><button class="btn btn-danger" @click="leave(true)">放弃修改并离开</button></template></BootstrapModal>
</template>


