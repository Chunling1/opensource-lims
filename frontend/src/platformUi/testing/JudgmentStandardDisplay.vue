<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { loadStandardDisplayNames } from '@/services/quality'
import ReportStandardDisplay from './ReportStandardDisplay.vue'
import { judgmentEntry, judgmentRows, type StandardDisplayRecord, type StandardDisplaySettings } from './reportTextDisplay'
const props = defineProps<{ id: string; source: string | readonly string[]; records?: StandardDisplayRecord[]; settings: StandardDisplaySettings; language: string; readonly: boolean }>()
const selection = computed(() => {
  if (typeof props.source !== 'string') return props.source.map(entry => ({...judgmentEntry(entry), entry}))
  const {codes, names} = judgmentRows(props.source)
  return codes.map(code => ({code, name: names[code] || '', entry: code}))
})
const options = ref<{code:string;name:string}[]>([]), loading = ref(false), error = ref('')
const lookup = computed(() => [...new Set(selection.value.filter(row => !row.name && /^[A-Za-z].*\d/.test(row.code)).map(row => row.code))])
watch(() => lookup.value.join('\n'), async (_, __, cleanup) => {
  let active = true
  cleanup(() => { active = false })
  error.value = ''; options.value = []; loading.value = true
  try {
    const codes = lookup.value
    const names: Record<string,string> = {}
    for (let start = 0; start < codes.length; start += 200) Object.assign(names, await loadStandardDisplayNames(codes.slice(start,start+200)))
    if (active) options.value = codes.map(code => ({code,name:names[code] || ''}))
  } catch { if (active) error.value = '标准名称读取失败，请重开页面重试；已选标准和显示设置保留。' }
  finally { if (active) loading.value = false }
}, { immediate:true })
const orderedRecords = computed(() => selection.value.flatMap(({code, name, entry}) => {
  if (name) return [{key:entry, code, name}]
  const selectedRecords = (props.records ?? []).filter(row => row.code === code)
  return selectedRecords.length ? selectedRecords : [{key:code, code, name:options.value.find(row => row.code === code)?.name || ''}]
}))
</script>
<template>
  <ReportStandardDisplay :id="id" label="判定依据" :codes="selection.map(row => row.code)" :records="orderedRecords" :settings="settings" :options="options" :language="language" :readonly="readonly" :loading="loading" />
  <p v-if="error" class="text-danger small mt-2" role="status">{{ error }}</p>
</template>
