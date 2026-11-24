<script setup lang="ts">
import {computed, ref, watch} from 'vue'
import StorageSampleSummary from './StorageSampleSummary.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import {businessToday, normalizeWorkflowDate, isWorkflowDateValid} from '@/composables/workflowDate'
import {submitSampleInbound, type SampleRow} from '@/services/pipeline'
const props = defineProps<{row?: SampleRow}>()
const emit = defineEmits<{close: []; completed: []}>()
const date = ref(''), busy = ref(false), error = ref('')
const previous = computed(() => [props.row?.sendDate, props.row?.entrustDate].map(normalizeWorkflowDate).filter(Boolean).sort().at(-1) || '')
const validation = computed(() => !isWorkflowDateValid(date.value) ? '请选择有效的入库日期' : previous.value && date.value < previous.value ? `入库日期不得早于送样或委托日期 ${previous.value}` : '')
watch(() => props.row, row => {if (row) {date.value = businessToday(); error.value = ''}}, {immediate:true})
watch(date, () => {error.value = ''})
async function submit() {
  if (!props.row || busy.value) return
  if (validation.value) {error.value = validation.value; return}
  busy.value = true; error.value = ''
  try {await submitSampleInbound(props.row.reportNo, date.value); emit('completed')}
  catch (failure) {error.value = failure instanceof Error ? failure.message : '入库失败，请重试'}
  finally {busy.value = false}
}
</script>
<template>
  <BootstrapModal :open="!!row" title="样品入库" size="lg" scrollable fullscreen-mobile :busy="busy" @close="!busy && emit('close')">
    <form id="sample-inbound-date-form" @submit.prevent="submit">
      <StorageSampleSummary :row="row" />
      <section class="border-top mt-4 pt-4" aria-labelledby="inbound-details-heading">
        <h6 id="inbound-details-heading" class="mb-3">入库信息</h6>
        <div class="row g-3 mb-3">
          <div class="col-6"><span class="text-muted small d-block mb-1">送样日期</span><span>{{ row?.sendDate || '未填写' }}</span></div>
          <div class="col-6"><span class="text-muted small d-block mb-1">委托日期</span><span>{{ row?.entrustDate || '未填写' }}</span></div>
          <div class="col-12 col-sm-6">
            <label for="sample-inbound-date" class="form-label">入库日期 <span class="text-danger">*</span></label>
            <WorkflowDatePicker id="sample-inbound-date" v-model="date" strict-order :previous-date="previous" :disabled="busy" :clearable="false" aria-label="入库日期" aria-describedby="sample-inbound-date-help" />
          </div>
        </div>
        <p id="sample-inbound-date-help" class="form-text mb-0">可选择实际入库日期；不得早于送样及委托日期。</p>
      </section>
      <div v-if="error" class="alert alert-danger mt-3 mb-0" role="alert">{{ error }}</div>
    </form>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button type="submit" form="sample-inbound-date-form" class="btn btn-primary" :disabled="busy">{{ busy ? '正在入库…' : '确认入库' }}</button></template>
  </BootstrapModal>
</template>
