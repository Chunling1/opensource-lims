<script setup lang="ts">
import { reportIssueTypes, type ReportCheckRejection } from '../../types/reports/reportCheck'
defineProps<{ form: ReportCheckRejection; busy: boolean; errors: Record<string, string> }>()
</script>
<template>
  <fieldset :disabled="busy" class="mb-0">
    <legend class="visually-hidden">问题处理信息</legend>
    <div class="row g-3">
      <div class="col-12">
        <fieldset class="mb-0">
          <legend class="form-label fs-6">问题类型<span class="text-danger ms-1">*</span></legend>
          <div class="d-flex flex-wrap gap-3"><div v-for="(value, index) in reportIssueTypes" :key="value" class="form-check"><input :id="`report-issue-type-${index}`" v-model="form.problemType" class="form-check-input" type="radio" name="report-issue-type" :value="value" /><label :for="`report-issue-type-${index}`" class="form-check-label">{{ value }}</label></div></div>
          <p v-if="errors.problemType" class="text-danger small mt-1 mb-0">{{ errors.problemType }}</p>
        </fieldset>
      </div>
      <div class="col-12">
        <label for="report-issue-reason" class="form-label">退回原因</label>
        <textarea id="report-issue-reason" v-model="form.reason" class="form-control" :class="{ 'is-invalid': errors.reason }" :aria-invalid="!!errors.reason" :aria-describedby="errors.reason ? 'report-issue-reason-error' : undefined" rows="3" maxlength="2000" placeholder="可填写发现的问题及退回原因"></textarea>
        <p v-if="errors.reason" id="report-issue-reason-error" class="text-danger small mt-1 mb-0">{{ errors.reason }}</p>
      </div>
      <div class="col-12 col-md-8">
        <fieldset class="mb-0">
          <legend class="form-label fs-6">退回方向</legend>
          <div class="d-flex flex-wrap gap-3 py-2">
            <div class="form-check"><input id="report-issue-commission" v-model="form.destination" type="radio" class="form-check-input" name="report-issue-destination" value="commission" /><label for="report-issue-commission" class="form-check-label">退回委托更改</label></div>
            <div class="form-check"><input id="report-issue-testing" v-model="form.destination" type="radio" class="form-check-input" name="report-issue-destination" value="testing" /><label for="report-issue-testing" class="form-check-label">退回检测数据更改</label></div>
          </div>
          <p v-if="errors.destination" class="text-danger small mt-1 mb-0">{{ errors.destination }}</p>
        </fieldset>
      </div>
      <div class="col-12 col-md-4">
        <label for="report-issue-handler" class="form-label">退回处理人</label>
        <input id="report-issue-handler" v-model="form.handler" class="form-control" maxlength="100" :class="{ 'is-invalid': errors.handler }" />
        <p v-if="errors.handler" class="text-danger small mt-1 mb-0">{{ errors.handler }}</p>
      </div>
      <div class="col-12">
        <label for="report-issue-opinion" class="form-label">处理意见</label>
        <textarea id="report-issue-opinion" v-model="form.opinion" class="form-control" :class="{ 'is-invalid': errors.opinion }" :aria-invalid="!!errors.opinion" :aria-describedby="errors.opinion ? 'report-issue-opinion-error' : undefined" rows="3" maxlength="2000" placeholder="可填写更正建议或处理要求"></textarea>
        <p v-if="errors.opinion" id="report-issue-opinion-error" class="text-danger small mt-1 mb-0">{{ errors.opinion }}</p>
      </div>
    </div>
  </fieldset>
</template>
