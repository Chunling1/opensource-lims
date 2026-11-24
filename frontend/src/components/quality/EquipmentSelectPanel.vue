<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import QueryFormLayout from '../common/QueryFormLayout.vue'
import DataTable from '../common/table/DataTable.vue'
import SingleChoice from '../common/SingleChoice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { EquipmentLedgerRow } from '../../types/quality/equipmentLedger'
import type { InterimPlanEquipmentRow } from '../../types/quality/equipmentInterimPlan'
import { overallPlanSearchFields, overallPlanOperators, type OverallPlanQuery } from '../../types/quality/equipmentOverallPlan'
defineProps<{ value?: EquipmentLedgerRow }>()
const emit = defineEmits<{ select: [EquipmentLedgerRow | undefined] }>()
const draft = reactive<Required<Pick<OverallPlanQuery, 'field' | 'operator' | 'value'>>>({ field: 'code', operator: 'contains', value: '' }), filters = reactive({ ...draft })
const rows = ref<(InterimPlanEquipmentRow & { choice: string })[]>([]), total = ref(0), page = ref(1), size = ref(10), loading = ref(false), error = ref<ErrorValue>('')
const columns = [
  { key: 'choice', label: '选择' }, { key: 'code', label: '设备编号' }, { key: 'name', label: '设备名称', truncate: 18, fullTitle: true },
  { key: 'model', label: '规格型号' }, { key: 'manufacturer', label: '生产厂家', truncate: 18, fullTitle: true },
  { key: 'cycle', label: '检定周期' }, { key: 'validity', label: '有效日期' }, { key: 'notes', label: '备注', truncate: 24, fullTitle: true },
] as const
let controller: AbortController | undefined, epoch = 0
async function load() {
  controller?.abort(); const request = controller = new AbortController(), token = ++epoch
  loading.value = true; error.value = ''; emit('select', undefined)
  try {
    const result = await registrationDemo.interimPlanEquipmentChoices({ ...filters, page: page.value, pageSize: size.value }, request.signal)
    if (token === epoch) { rows.value = result.items.map(row => ({ ...row, choice: '' })); total.value = result.total; page.value = result.page }
  } catch (issue) { if (token === epoch && !request.signal.aborted) { error.value = normalizeError(issue); rows.value = [] } }
  finally { if (token === epoch) loading.value = false }
}
function search() { Object.assign(filters, draft); page.value = 1; void load() }
void load()
onBeforeUnmount(() => { epoch++; controller?.abort() })
</script>
<template>
  <form aria-label="选择设备查询" class="mb-3" @submit.prevent="search"><QueryFormLayout>
    <div class="row g-3">
      <div class="col-12 col-sm-6 col-xl-4"><label for="pick-equipment-field" class="form-label">查询字段</label><select id="pick-equipment-field" v-model="draft.field" class="form-select"><option v-for="field in overallPlanSearchFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
      <div class="col-12 col-sm-6 col-xl-4"><label for="pick-equipment-operator" class="form-label">匹配方式</label><select id="pick-equipment-operator" v-model="draft.operator" class="form-select"><option v-for="operator in overallPlanOperators" :key="operator.key" :value="operator.key">{{ operator.label }}</option></select></div>
      <div class="col-12 col-sm-6 col-xl-4"><label for="pick-equipment-value" class="form-label">查询值</label><input id="pick-equipment-value" v-model="draft.value" class="form-control" maxlength="200" /></div>
    </div>
    <template #actions><button type="submit" class="btn btn-primary text-nowrap" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></template>
  </QueryFormLayout></form>
  <DataTable label="可选设备" :rows="rows" :columns="columns" :row-key="row => row.id" :row-label="row => row.code" :loading="loading" :error="error" :pagination="{ total, page, pageSize: size, sizes: [10, 20, 50] }" @retry="load" @page="page = $event; load()" @size="size = $event; page = 1; load()">
    <template #cell-choice="{ row }"><SingleChoice name="interim-plan-equipment" :value="row.id" :label="`选择设备 ${row.code}`" :checked="value?.id === row.id" @change="emit('select', row)" /></template>
  </DataTable>
</template>
