<script setup lang="ts">
import TemplateDateRange from '../common/TemplateDateRange.vue'
import type { TrialDate } from '../../types/testing/dataEntryDetail'
const props = defineProps<{ modelValue: TrialDate[]; readonly: boolean; errors: Record<string, string> }>()
const emit = defineEmits<{ 'update:modelValue': [TrialDate[]] }>()
const keys = new WeakMap<TrialDate, number>(); let sequence = 0
function key(row: TrialDate) { if (!keys.has(row)) keys.set(row, ++sequence); return keys.get(row)! }
function add() { if (!props.readonly && props.modelValue.length < 50) emit('update:modelValue', [...props.modelValue, { kind: 'range', from: '', to: '' }]) }
function remove(index: number) { if (!props.readonly && props.modelValue.length > 1) emit('update:modelValue', props.modelValue.filter((_, i) => i !== index)) }
function change(row: TrialDate, dates: { from: string; to: string }) { if (!props.readonly) Object.assign(row, dates) }
</script>
<template>
  <div id="trial-testDates" role="group" aria-label="试验日期">
    <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
      <span class="form-label mb-0">试验日期<span v-if="!readonly" class="text-danger"> *</span></span>
      <button type="button" class="btn btn-link p-0" :disabled="readonly || modelValue.length >= 50" @click="add"><i class="ti ti-plus me-1" aria-hidden="true"></i>添加日期</button>
    </div>
    <div v-for="(row, index) in modelValue" :key="key(row)" class="mb-2" role="group" :aria-label="`试验日期第${index + 1}项`" :aria-describedby="errors[`testDates.${index}`] ? `trial-date-error-${index}` : undefined">
      <div class="row g-2 align-items-start">
        <div class="col">
          <label :for="`trial-date-${index}`" class="visually-hidden">第{{ index + 1 }}项日期范围</label>
          <TemplateDateRange :id="`trial-date-${index}`" :from="row.from" :to="row.to" :disabled="readonly" allow-partial @change="change(row, $event)" />
        </div>
        <div class="col-auto"><button type="button" class="btn btn-light" :disabled="readonly || modelValue.length <= 1" :aria-label="`删除第${index + 1}项试验日期`" @click="remove(index)"><i class="ti ti-trash me-1" aria-hidden="true"></i>删除</button></div>
      </div>
      <div v-if="errors[`testDates.${index}`]" :id="`trial-date-error-${index}`" class="invalid-feedback d-block" role="alert">{{ errors[`testDates.${index}`] }}</div>
    </div>
    <p v-if="!modelValue.length" class="text-muted mb-2">暂无试验日期</p>
  </div>
</template>
