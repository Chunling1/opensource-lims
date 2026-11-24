<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import EquipmentSchemeEditor from './EquipmentSchemeEditor.vue'
import { equipmentSchemes, type SchemeCatalogue, type SchemeResolution } from './equipmentSchemes'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { TrialDate } from '../../types/testing/dataEntryDetail'
const props = defineProps<{ reportNo: string; dates: TrialDate[]; selected: string[]; disabled?: boolean }>()
const emit = defineEmits<{ applied: [SchemeResolution]; busy: [boolean] }>()
const catalogue = ref<SchemeCatalogue>(), choice = ref(''), busy = ref(false), error = ref<ErrorValue>(''), editing = ref<false | 'new' | 'edit'>(false)
const outcome = ref<SchemeResolution>(), added = ref(0)
let epoch = 0
const chosen = computed(() => catalogue.value?.schemes.find(row => String(row.id) === choice.value))
const schemes = computed(() => [...(catalogue.value?.schemes || [])].sort((a, b) => Number(!!b.recommended) - Number(!!a.recommended)))
const completeDates = computed(() => props.dates.length && props.dates.every(d => d.from && (d.kind === 'single' || d.to)))
async function load() {
  const token = ++epoch; busy.value = true; error.value = ''
  try {
    const value = await equipmentSchemes.catalogue(props.reportNo)
    if (token !== epoch) return
    catalogue.value = value
    if (!value.schemes.some(s => String(s.id) === choice.value)) choice.value = String(value.schemes.find(s => s.enabled && s.recommended)?.id || '')
  } catch (issue) { if (token === epoch) error.value = normalizeError(issue) }
  finally { if (token === epoch) busy.value = false }
}
async function apply() {
  if (busy.value || props.disabled || !chosen.value?.enabled || !completeDates.value) return
  const token = epoch, key = JSON.stringify([props.reportNo, props.dates]), id = chosen.value.id
  busy.value = true; error.value = ''; outcome.value = undefined; emit('busy', true)
  try {
    const value = await equipmentSchemes.resolve(id, props.reportNo, props.dates.map(d => ({ start: d.from, end: d.kind === 'single' ? d.from : d.to })))
    if (token !== epoch || key !== JSON.stringify([props.reportNo, props.dates]) || props.disabled) return
    added.value = value.rows.filter(row => !props.selected.includes(String(row.id))).length
    outcome.value = value; emit('applied', value)
  } catch (issue) { if (token === epoch) error.value = normalizeError(issue) }
  finally { if (token === epoch) busy.value = false; emit('busy', false) }
}
async function saved() { editing.value = false; await load() }
watch(() => props.reportNo, () => { catalogue.value = undefined; choice.value = ''; outcome.value = undefined; editing.value = false; void load() }, { immediate: true })
watch(() => JSON.stringify(props.dates), () => { outcome.value = undefined })
onBeforeUnmount(() => { epoch++ })
</script>
<template>
  <section class="mb-3" aria-label="部门仪器方案">
    <ErrorNotice :error="error" />
    <div class="d-flex flex-wrap gap-2 align-items-center">
      <label for="equipment-scheme" class="col-form-label">仪器方案</label>
      <select id="equipment-scheme" v-model="choice" class="form-select w-auto mw-100" :disabled="busy || disabled"><option value="">{{ catalogue?.schemes.length ? '请选择部门方案' : '本部门暂无仪器方案' }}</option><option v-for="row in schemes" :key="row.id" :value="String(row.id)">{{ row.name }}{{ row.recommended ? '（当前项目推荐）' : '' }}{{ row.enabled ? '' : '（已停用）' }}</option></select>
      <button type="button" class="btn btn-primary" :disabled="busy || disabled || !chosen?.enabled || !completeDates" @click="apply">套用方案</button>
      <button v-if="catalogue?.canManage" type="button" class="btn btn-light" :disabled="busy || disabled" @click="editing = 'new'">将已选保存为方案</button>
      <button v-if="catalogue?.canManage" type="button" class="btn btn-light" :disabled="busy || disabled || !chosen" @click="editing = 'edit'">维护方案</button>
      <button type="button" class="btn btn-link" :disabled="busy || disabled" @click="load">刷新方案</button>
    </div>
    <p v-if="!completeDates" class="text-muted mt-2 mb-0">先填写完整试验日期，才能核对并套用仪器方案。</p>
    <div v-if="outcome" class="alert mt-2 mb-0" :class="outcome.skipped.length ? 'alert-warning' : 'alert-success'" role="status">
      <p class="mb-1">已加入 {{ added }} 台，已选中 {{ outcome.rows.length - added }} 台；跳过 {{ outcome.skipped.length }} 台。原方案保留不变。</p>
      <ul v-if="outcome.skipped.length" class="mb-0"><li v-for="row in outcome.skipped" :key="row.id">{{ row.code }} {{ row.name }}：{{ row.reason }}，未带入。</li></ul>
    </div>
    <EquipmentSchemeEditor v-if="editing && catalogue" :catalogue="catalogue" :scheme="editing === 'edit' ? chosen : undefined" :initial-ids="selected" @close="editing = false" @saved="saved" />
  </section>
</template>
