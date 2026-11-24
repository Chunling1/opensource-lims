<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { clientYearRange } from '../../services/common/date'
import TemplateDateRange from '../common/TemplateDateRange.vue'
import QueryFormLayout from '../common/QueryFormLayout.vue'
import { commissionStates } from '../../services/commissions/registrationService'
import type { RegistrationKind, RegistrationQuery } from '../../types/commissions/registration'
import { commissionSearchFields, sampleSearchFields, sampleDataStates, sampleTypes } from '../../types/commissions/registration'
const props = defineProps<{ reportGroupOptions?: readonly {value: string; label: string}[]; kind: RegistrationKind; query: RegistrationQuery; showAdvancedSearch?: boolean; advancedActive?: boolean; sampleSearchFields?: readonly { value: NonNullable<RegistrationQuery['searchField']>; label: string }[]; dataStatusOptions?: readonly { value: string; label: string }[] }>()
const emit = defineEmits<{ search: [RegistrationQuery]; 'advanced-search': [] }>()
const draft = reactive<RegistrationQuery>({})
const defaultDates = clientYearRange()
const dateRange = ref<InstanceType<typeof TemplateDateRange>>()
function submit() {
  if (dateRange.value && !dateRange.value.validate()) return
  emit('search', { ...draft })
}
watch(() => JSON.stringify(props.query), () => { Object.keys(draft).forEach(k => delete draft[k as keyof RegistrationQuery]); Object.assign(draft, props.query); draft.searchField ||= 'all' }, { immediate: true })
const commission = computed(() => props.kind === 'commissions')
const dataStatuses = computed(() => props.dataStatusOptions ?? [{ value: '', label: '全部状态' }, ...sampleDataStates.map(value => ({ value, label: value }))])
const legacySampleFields = [{ key: 'keyword', label: '样品编号或名称' }, { key: 'sampleCode', label: '样品编号' }, { key: 'reportCode', label: '报告编号' }, { key: 'owner', label: '样品登记人' }] as const
const statuses = commissionStates.map(s => ({ value: s, label: s }))
</script>
<template>
  <form class="card-body border-bottom" :aria-label="commission ? '委托查询' : '样品查询'" @submit.prevent="submit">
    <QueryFormLayout>
    <template v-if="commission">
      <div class="row g-3 align-items-start">
        <div class="col-12 col-md-6 col-xl"><label class="form-label" for="commission-filter-field">查询内容</label><select id="commission-filter-field" v-model="draft.searchField" class="form-select"><option v-for="field in commissionSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
        <div class="col-12 col-md-6 col-xl"><label class="form-label" for="commission-filter-contains">包含</label><input id="commission-filter-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-md-6 col-xl"><label class="form-label" for="commission-filter-status">委托状态</label><select id="commission-filter-status" v-model="draft.status" class="form-select"><option value="">全部状态</option><option v-for="s in statuses" :key="s.value" :value="s.value">{{ s.label }}</option></select></div>
        <div class="col-12 col-md-6 col-xl-4"><label class="form-label" for="commission-filter-date">委托日期</label><TemplateDateRange id="commission-filter-date" ref="dateRange" :from="draft.from || defaultDates.from" :to="draft.to || defaultDates.to" @change="Object.assign(draft, $event)" /></div>
      </div>
      <div v-if="draft.commissionCode" class="d-flex align-items-center gap-2 mt-3"><span class="text-muted text-break">委托编号包含：{{ draft.commissionCode }}</span><button class="btn btn-sm btn-light" type="button" aria-label="移除委托编号条件" @click="draft.commissionCode = ''"><i class="ti ti-x" aria-hidden="true"></i></button></div>
    </template>
    <template v-else>
      <div class="query-fields">
        <div v-if="reportGroupOptions?.length" class="query-field query-field--group"><label for="sample-report-group" class="form-label">数据分组</label><select id="sample-report-group" v-model="draft.reportGroup" class="form-select"><option v-for="group in reportGroupOptions" :key="group.value" :value="group.value">{{ group.label }}</option></select></div>
        <div class="query-field query-field--search"><label class="form-label" for="sample-filter-field">查询内容</label><select id="sample-filter-field" v-model="draft.searchField" class="form-select"><option v-for="field in props.sampleSearchFields ?? sampleSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
        <div class="query-field query-field--keyword"><label class="form-label" for="sample-filter-contains">包含</label><input id="sample-filter-contains" v-model="draft.contains" class="form-control" maxlength="200" /></div>
        <div class="query-field query-field--status"><label class="form-label" for="sample-filter-data-status">数据状态</label><select id="sample-filter-data-status" v-model="draft.dataStatus" class="form-select"><option v-for="state in dataStatuses" :key="state.value" :value="state.value">{{ state.label }}</option></select></div>
        <div class="query-field query-field--type"><label class="form-label" for="sample-filter-type">样品类型</label><select id="sample-filter-type" v-model="draft.sampleType" class="form-select"><option value="">全部类型</option><option v-for="type in sampleTypes" :key="type" :value="type">{{ type }}</option></select></div>
        <div class="query-field query-field--date"><label class="form-label" for="sample-filter-date">委托日期</label><TemplateDateRange id="sample-filter-date" ref="dateRange" :from="draft.commissionFrom || defaultDates.from" :to="draft.commissionTo || defaultDates.to" @change="draft.commissionFrom = $event.from; draft.commissionTo = $event.to" /></div>
      </div>
      <template v-for="field in legacySampleFields" :key="field.key"><div v-if="draft[field.key]" class="d-flex align-items-center gap-2 mt-3"><span class="text-muted text-break">{{ field.label }}包含：{{ draft[field.key] }}</span><button class="btn btn-sm btn-light" type="button" :aria-label="`移除${field.label}条件`" @click="draft[field.key] = ''"><i class="ti ti-x" aria-hidden="true"></i></button></div></template>
    </template>
    <template #actions><button class="btn btn-primary text-nowrap" type="submit"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button><button v-if="showAdvancedSearch" class="btn text-nowrap" :class="advancedActive ? 'btn-primary' : 'btn-light'" type="button" aria-haspopup="dialog" @click="emit('advanced-search')"><i class="ti ti-filter me-1" aria-hidden="true"></i>高级</button></template>
    </QueryFormLayout>
  </form>
</template>


