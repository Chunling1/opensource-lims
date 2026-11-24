<script setup lang="ts">
import { computed } from 'vue'
import ReportTextPreview from './ReportTextPreview.vue'
import StandardTitleChoices from '../StandardTitleChoices.vue'
import { standardRecordPreview, type StandardDisplayRecord, type TitleStyle } from './reportTextDisplay'
const props = withDefaults(defineProps<{ id?: string; label?: string; codes?: string[]; records?: StandardDisplayRecord[]; settings: { standards?: string[]; standardRecords?: StandardDisplayRecord[]; standardShowName?: boolean; standardNames?: Record<string,string>; standardTitleStyles?: Record<string,TitleStyle>; standardSeparatorText?: string }; options: {code:string;name?:string}[]; language: string; readonly: boolean; loading?: boolean }>(), {id:'report-standard',label:'检测依据'})
const selected = computed(() => props.codes ?? props.settings.standards ?? [])
const names = computed(() => ({...Object.fromEntries(props.options.filter(row => row.name).map(row => [row.code,row.name || ''])), ...props.settings.standardNames}))
const defaultStyle = computed(() => props.language === 'EN' ? 'EN' : 'CN')
const records = computed(() => {
  const selectedRecords = (props.records ?? props.settings.standardRecords ?? []).filter(row => selected.value.includes(row.code)).map(row => ({...row, key: row.id ? `id:${row.id}` : row.key}))
  return [...selectedRecords, ...selected.value.filter(code => !selectedRecords.some(row => row.code === code)).map(code => ({key: code, code, name: names.value[code] || ''}))]
})
const preview = computed(() => standardRecordPreview(records.value, !!props.settings.standardShowName, props.settings.standardTitleStyles || {}, defaultStyle.value, props.settings.standardSeparatorText ?? '；'))
function setStyles(value: Record<string,TitleStyle>) { if (!props.readonly) props.settings.standardTitleStyles = value }
</script>
<template>
  <div class="row g-3">
    <div class="col-12 col-xl-7">
      <div class="form-check mb-3"><input :id="`${id}-show-name`" v-model="settings.standardShowName" type="checkbox" class="form-check-input" :disabled="readonly" /><label :for="`${id}-show-name`" class="form-check-label">显示标准名称</label></div>
      <p v-if="loading" class="text-muted small" role="status">正在读取标准名称…</p>
      <StandardTitleChoices :id="id" :codes="records.map(row => row.key)" :names="Object.fromEntries(records.map(row => [row.key, row.name]))" :labels="Object.fromEntries(records.map(row => [row.key, row.code]))" :model-value="settings.standardTitleStyles || {}" :default-style="defaultStyle" :readonly="readonly" :disabled="!settings.standardShowName" @update:model-value="setStyles" />
    </div>
    <div class="col-12 col-xl-5"><ReportTextPreview :id="`${id}-preview`" :label="`${label}效果`" :text="preview" :separator="settings.standardSeparatorText ?? '；'" :readonly="readonly" @update:separator="settings.standardSeparatorText = $event" /></div>
  </div>
</template>
