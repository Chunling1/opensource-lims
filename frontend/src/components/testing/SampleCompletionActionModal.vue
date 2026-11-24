<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import type { ErrorValue } from '../../services/common/errors'
import type { SampleCompletionAction, SampleCompletionRow, SampleCompletionSubmission } from '../../types/testing/sampleCompletion'

const props = defineProps<{ operation?: { row: SampleCompletionRow; action: SampleCompletionAction }; busy: boolean; error: ErrorValue }>()
const emit = defineEmits<{ close: []; submit: [SampleCompletionSubmission]; refresh: [] }>()
const result = ref(''), resultError = ref('')
const systemError = computed(() => props.error && !props.error.fieldErrors?.result ? props.error : '')
const stale = computed(() => !!props.error && ['BUSINESS_RULE'].includes(props.error.code))
watch(() => props.operation, () => { result.value = ''; resultError.value = '' })
watch(() => props.error, async error => {
  resultError.value = error && error.fieldErrors?.result || ''
  if (resultError.value) { await nextTick(); document.getElementById('completion-result')?.focus() }
})
watch(result, () => { resultError.value = '' })
function submit() {
  if (!props.operation || props.busy || stale.value) return
  if (props.operation.action === 'process') {
    if (!result.value.trim()) { resultError.value = '请填写处置结果。'; document.getElementById('completion-result')?.focus(); return }
    emit('submit', { action: 'process', result: result.value.trim() })
  } else emit('submit', { action: 'undo' })
}
</script>

<template>
  <BootstrapModal :open="!!operation" :title="operation?.action === 'undo' ? '撤销样品处理' : '检毕样品处理'" :busy="busy" scrollable @close="!busy && emit('close')">
    <ErrorNotice :error="systemError" />
    <button v-if="stale" type="button" class="btn btn-outline-primary btn-sm mb-3" :disabled="busy" @click="emit('refresh')">刷新列表</button>
    <form v-if="operation" id="sample-completion-operation" @submit.prevent="submit">
      <p class="text-break text-muted"><strong>{{ operation.row.code }}</strong> · {{ operation.row.name }}</p>
      <fieldset v-if="operation.action === 'process'" :disabled="busy || stale" class="row g-3">
        <div class="col-12"><label for="completion-requirement" class="form-label">本样品客户处置要求</label><input id="completion-requirement" :value="operation.row.customerRequirement || '未填写'" class="form-control bg-light" readonly /></div>
        <div class="col-12"><label for="completion-retention" class="form-label">留置时间</label><input id="completion-retention" :value="operation.row.retentionTime?.slice(0, 10) || '未填写'" class="form-control" disabled /></div>
        <div class="col-12">
          <label for="completion-result" class="form-label">处置结果 <span class="text-danger">*</span></label>
          <input id="completion-result" v-model="result" class="form-control" :class="{ 'is-invalid': resultError }" :aria-invalid="!!resultError" :aria-describedby="resultError ? 'completion-result-error' : undefined" required maxlength="500" />
          <div v-if="resultError" id="completion-result-error" class="invalid-feedback" role="alert">{{ resultError }}</div>
        </div>
      </fieldset>
      <p v-else class="mb-0">确认撤销该样品的处理？撤销后恢复为“样品待处理”。</p>
    </form>
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button>
      <button type="submit" form="sample-completion-operation" class="btn btn-primary" :disabled="busy || stale || !operation"><span v-if="busy" class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>{{ busy ? '正在提交…' : '确定' }}</button>
    </template>
  </BootstrapModal>
</template>
