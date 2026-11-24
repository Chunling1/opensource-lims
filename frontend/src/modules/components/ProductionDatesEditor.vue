<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ProductionDatePicker from './ProductionDatePicker.vue'
import { dateBoundary } from '../composables/sampleDateRules'
import { productionDatesIssues, productionDatesText, singleProductionDate, type ProductionDateRow, type ProductionDateLimits } from '../composables/productionDates'
const props = withDefaults(defineProps<{ modelValue?: string; rows?: ProductionDateRow[]; disabled?: boolean; limits?: ProductionDateLimits; language?: string }>(), {modelValue:'', rows:()=>[], limits:()=>({}), language:'CN'})
const emit = defineEmits<{ 'update:modelValue':[string]; 'update:rows':[ProductionDateRow[]] }>()
const entries = ref<ProductionDateRow[]>([])
watch(() => [props.rows, props.modelValue], () => {
  entries.value = props.rows.length ? props.rows.map(row=>({...row, precision: row.precision || singleProductionDate(row.value).precision})) : [singleProductionDate(props.modelValue)]
}, {deep:true, immediate:true})
const issues = computed(() => productionDatesIssues(entries.value, props.limits))
const preview = computed(() => productionDatesText(entries.value, props.language, true))
const nextDate = computed(() => dateBoundary(Object.values(props.limits), 'min'))
function publish(rows: ProductionDateRow[]) {
  if (props.disabled) return
  entries.value = rows
  emit('update:rows', rows)
  emit('update:modelValue', productionDatesText(rows))
}
function edit(i: number, field: keyof ProductionDateRow, value: string) {
  publish(entries.value.map((row,index) => index === i ? {...row,[field]:value} : {...row}))
}
function add() { publish([...entries.value.map(row=>({...row})), singleProductionDate()]) }
function splitUnits() {
  const rows = entries.value.map(row=>({...row}))
  if (rows.length === 1 && !rows[0]!.name) rows[0]!.name = '室外机'
  for (const name of ['室外机','室内机']) if (!rows.some(row=>row.name === name)) rows.push({...singleProductionDate(),name})
  publish(rows)
}
function remove(i: number) { publish(entries.value.filter((_,index)=>index !== i)) }
</script>
<template>
  <div>
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <span class="small text-body-secondary">日期按部件分别校验，说明文字会随日期输出。</span>
      <div v-if="!disabled" class="d-flex gap-2">
        <button type="button" class="btn btn-sm btn-outline-primary" @click="splitUnits">室内机／室外机</button>
        <button type="button" class="btn btn-sm btn-light" @click="add"><i class="ti ti-plus" aria-hidden="true"></i> 添加一项</button>
      </div>
    </div>
    <div v-for="(row,i) in entries" :key="i" class="row g-3 py-3 border-top">
      <label class="col-12 col-sm-6 col-lg-3 mb-0">对象／部件<input :value="row.name" :disabled="disabled" class="form-control mt-1" :aria-label="`第${i+1}项对象或部件`" placeholder="整机可留空，如：室内机1" @input="edit(i,'name',($event.target as HTMLInputElement).value)" /></label>
      <div class="col-12 col-sm-6 col-lg-4"><div class="mb-1">生产日期</div><ProductionDatePicker :model-value="row.value" :date-precision="row.precision" :disabled="disabled" :next-date="nextDate" @update:model-value="edit(i,'value',$event)" @update:date-precision="edit(i,'precision',$event)" /></div>
      <label class="col-12 col-sm-10 col-lg-4 mb-0">说明（选填）<input :value="row.note" :disabled="disabled" class="form-control mt-1" :aria-label="`第${i+1}项说明`" placeholder="如：以铭牌为准" @input="edit(i,'note',($event.target as HTMLInputElement).value)" /></label>
      <div class="col-12 col-sm-2 col-lg-1"><button v-if="!disabled && entries.length > 1" type="button" class="btn btn-sm btn-light" :aria-label="`删除第${i+1}项`" @click="remove(i)">删除</button></div>
    </div>
    <div aria-live="polite" class="small mt-2">
      <p v-for="error in issues.errors" :key="error" class="text-danger mb-1">{{ error }}</p>
      <p v-for="warning in issues.warnings" :key="warning" class="text-body-secondary mb-1">{{ warning }}</p>
    </div>
    <div v-if="preview" class="bg-body-tertiary rounded p-3 mt-3 text-break"><span class="small text-body-secondary">委托单／报告文字预览</span><div class="mt-1"><div v-for="(line,index) in preview.split('\n')" :key="index">{{ line }}</div></div></div>
  </div>
</template>
