<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import TestEnvironmentPlanTable from './TestEnvironmentPlanTable.vue'
import TablePagination from '../common/table/TablePagination.vue'
import { type EnvironmentPlan } from '../../types/quality/testEnvironments'
const props = defineProps<{ options: EnvironmentPlan[]; value: EnvironmentPlan[]; query: string }>()
const emit = defineEmits<{ select: [EnvironmentPlan[]] }>()
const selected = ref([...props.value]), leftChecked = ref<string[]>([]), rightChecked = ref<string[]>([])
const leftPage = ref(1), rightPage = ref(1), leftSize = ref(10), rightSize = ref(10)
const available = computed(() => props.options.filter(row => !selected.value.some(item => item.id === row.id) && `${row.name} ${row.code}`.toLocaleLowerCase().includes(props.query)))
const canSelect = (row: EnvironmentPlan) => props.options.some(item => item.id === row.id)
const slice = (rows: EnvironmentPlan[], page: number, size: number) => rows.slice((page - 1) * size, page * size)
function moveIn() { selected.value.push(...props.options.filter(row => leftChecked.value.includes(row.id) && !selected.value.some(item => item.id === row.id))); leftChecked.value = [] }
function moveOut() { selected.value = selected.value.filter(row => !canSelect(row) || !rightChecked.value.includes(row.id)); rightChecked.value = [] }
watch([() => available.value.length, leftSize], () => { leftPage.value = Math.min(leftPage.value, Math.max(1, Math.ceil(available.value.length / leftSize.value))) })
watch([() => selected.value.length, rightSize], () => { rightPage.value = Math.min(rightPage.value, Math.max(1, Math.ceil(selected.value.length / rightSize.value))) })
watch(() => props.query, () => { leftPage.value = 1; leftChecked.value = [] })
const selectedCount = computed(() => selected.value.length)
defineExpose({ selectedCount, confirm: () => emit('select', [...selected.value]) })
</script>
<template>
  <fieldset class="h-100">
  <div class="row g-2 h-100 flex-lg-nowrap">
    <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="未关联检测方案">
      <div class="card border shadow-none h-100 mb-0">
        <div class="card-header py-2 flex-shrink-0"><h6 class="mb-0">未关联检测方案 <span class="badge bg-light text-body">{{ available.length }}</span></h6></div>
        <div class="overflow-auto flex-grow-1"><TestEnvironmentPlanTable label="未关联检测方案" :rows="slice(available, leftPage, leftSize)" v-model:checked="leftChecked" /></div>
        <TablePagination class="flex-shrink-0" label="未关联检测方案" :total="available.length" :page="leftPage" :page-size="leftSize" :sizes="[10, 20, 50]" @page="leftPage = $event" @size="leftSize = $event; leftPage = 1" />
      </div>
    </section>
    <div class="col-12 col-lg-auto flex-shrink-0 d-flex flex-lg-column align-items-center justify-content-center gap-2">
      <button type="button" class="btn btn-primary btn-sm btn-icon" aria-label="移入" title="移入" :disabled="!leftChecked.length" @click="moveIn"><i class="ti ti-arrow-right d-none d-lg-inline" aria-hidden="true"></i><i class="ti ti-arrow-down d-lg-none" aria-hidden="true"></i></button>
      <button type="button" class="btn btn-light btn-sm btn-icon" aria-label="移出" title="移出" :disabled="!rightChecked.length" @click="moveOut"><i class="ti ti-arrow-left d-none d-lg-inline" aria-hidden="true"></i><i class="ti ti-arrow-up d-lg-none" aria-hidden="true"></i></button>
    </div>
    <section class="col-12 col-lg-6 flex-shrink-1 overflow-hidden" aria-label="已关联检测方案">
      <div class="card border shadow-none h-100 mb-0">
        <div class="card-header py-2 flex-shrink-0"><h6 class="mb-0">已关联检测方案 <span class="badge bg-light text-body">{{ selected.length }}</span></h6></div>
        <div class="overflow-auto flex-grow-1"><TestEnvironmentPlanTable label="已关联检测方案" :rows="slice(selected, rightPage, rightSize)" v-model:checked="rightChecked" :selectable="canSelect" /></div>
        <TablePagination class="flex-shrink-0" label="已关联检测方案" :total="selected.length" :page="rightPage" :page-size="rightSize" :sizes="[10, 20, 50]" @page="rightPage = $event" @size="rightSize = $event; rightPage = 1" />
      </div>
    </section>
  </div>
  </fieldset>
</template>
