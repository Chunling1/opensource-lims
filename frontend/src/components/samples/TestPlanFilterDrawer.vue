<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BootstrapOffcanvas from '../common/BootstrapOffcanvas.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import RegistrationTestPlanBranch from '../commissions/RegistrationTestPlanBranch.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { useTestPlanCache } from '../../services/common/testPlanCache'
import { localPlanSelection } from '../../services/common/localPlanSelection'
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { emptyPlanSelection, type PlanSelectionCatalogue, type PlanSelection, type PlanSelectionState, type PlanSelectionToggle } from '../../types/samples/inbound'
const props = withDefaults(defineProps<{ open: boolean; value: PlanSelection; sampleScope?: 'inbound' | 'outbound' | 'disposal' | 'flow' | 'assignment' | 'pickup' | 'task-query' | 'data-entry' | 'data-check' | 'sample-copy' | 'data-changes' | 'report-check' | 'report-review' | 'report-approval' | 'report-print' | 'report-signing' | 'report-distribution' | 'report-archive' | 'report-query' }>(), { sampleScope: 'inbound' })
const emit = defineEmits<{ close: []; change: [PlanSelectionState]; busy: [boolean]; error: [ErrorValue] }>()
const state = ref<PlanSelectionState>(), keyword = ref(''), applied = ref(''), revision = ref(0), expanded = ref(true)
const busy = ref(false), error = ref<ErrorValue>('')
const showAll = ref(false), catalogue = ref<PlanSelectionCatalogue>(), dirty = ref(false)
const displayedSelection = computed(() => !showAll.value && state.value?.populated ? state.value.populated : state.value)
const cache = useTestPlanCache()
let controller: AbortController | undefined, sequence = 0
async function loadSelection() {
  if (busy.value || !props.open) return
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  const cacheKey = `selection:${props.sampleScope}`, cacheRevision = cache?.revision
  const cached = cache?.get<PlanSelectionCatalogue>(cacheKey)
  error.value = ''; emit('error', '')
  if (cached) { catalogue.value = cached; state.value = localPlanSelection(cached, props.value || emptyPlanSelection()); return }
  busy.value = true
  try {
    const result = await registrationDemo.testPlanSelection(props.value || emptyPlanSelection(), undefined, active.signal, props.sampleScope)
    if (token === sequence && props.open) { cache?.set(cacheKey, result.catalogue, cacheRevision!); catalogue.value = result.catalogue; state.value = localPlanSelection(result.catalogue, result.selection) }
  } catch (issue) { if (token === sequence && !active.signal.aborted) { error.value = normalizeError(issue); emit('error', error.value) } }
  finally { if (token === sequence) busy.value = false }
}
function toggleSelection(toggle: PlanSelectionToggle) {
  if (!catalogue.value || !state.value || busy.value) return
  state.value = localPlanSelection(catalogue.value, state.value.selection, { ...toggle, populatedOnly: toggle.populatedOnly ?? !showAll.value })
  dirty.value = true
}
function close() {
  if (!props.open) return
  if (dirty.value && state.value) { dirty.value = false; emit('change', state.value) }
  sequence++; controller?.abort(); busy.value = false; error.value = ''; emit('error', '')
  emit('close')
}
function chooseAll(event: Event) {
  const input = event.target as HTMLInputElement, next = input.checked
  input.checked = !!displayedSelection.value?.total && displayedSelection.value.count === displayedSelection.value.total
  input.indeterminate = !!displayedSelection.value && displayedSelection.value.count > 0 && displayedSelection.value.count < displayedSelection.value.total
  toggleSelection({ kind: 'all', id: '', checked: next })
}
function search() { applied.value = keyword.value.trim(); expanded.value = true; revision.value++ }
function toggleDisplay() { showAll.value = !showAll.value; expanded.value = true }
watch(() => props.open, open => {
  sequence++; controller?.abort(); busy.value = false
  if (open) {
    keyword.value = ''; applied.value = ''; expanded.value = true; revision.value++
    dirty.value = false; state.value = undefined; catalogue.value = undefined; void loadSelection()
  }
}, { immediate: true })
watch(busy, value => emit('busy', value), { flush: 'sync' })
watch(() => JSON.stringify(currentActor.value), () => { sequence++; controller?.abort(); state.value = undefined; busy.value = false; error.value = ''; showAll.value = false; emit('error', ''); emit('close') })
onBeforeUnmount(() => { sequence++; controller?.abort() })
defineExpose({ retry: loadSelection })
</script>
<template>
  <BootstrapOffcanvas :open="open" :loading="busy" title="筛选检测方案" @close="close">
    <template #toolbar>
      <form class="row g-2" aria-label="筛选检测方案查询" @submit.prevent="search">
        <div class="col-12 d-flex align-items-center justify-content-between gap-2"><label for="filter-plan-keyword" class="form-label mb-0">方案名称或代码</label><button type="button" class="btn btn-link p-0 text-nowrap" :aria-pressed="showAll" :title="showAll ? `切换为仅显示有${sampleScope === 'report-query' ? '报告查询' : sampleScope === 'report-archive' ? '报告归档' : sampleScope === 'report-distribution' ? '报告发放' : sampleScope === 'report-signing' ? '报告签章' : sampleScope === 'report-print' ? '报告打印' : sampleScope === 'report-review' ? '报告审核' : sampleScope === 'report-approval' ? '报告批准' : sampleScope === 'report-check' ? '报告校核' : sampleScope === 'data-changes' ? '检测更改' : sampleScope === 'sample-copy' ? '可查询' : sampleScope === 'data-check' ? '数据校核' : sampleScope === 'data-entry' ? '数据录入' : sampleScope === 'task-query' ? '检测任务' : sampleScope === 'assignment' ? '任务分配' : sampleScope === 'pickup' ? '领取' : sampleScope === 'flow' ? '流转' : sampleScope === 'disposal' ? '处置' : sampleScope === 'outbound' ? '出库' : '入库'}样品的类别` : '切换为显示全部检测方案类别'" @click="toggleDisplay">{{ showAll ? '仅显示有样品' : '全部显示' }}</button></div>
        <div class="col"><input id="filter-plan-keyword" v-model="keyword" class="form-control" maxlength="200" /></div><div class="col-auto"><button type="submit" class="btn btn-primary">搜索</button></div>
      </form>
      <div class="d-flex align-items-center justify-content-between mt-3"><span v-if="state" class="text-muted" role="status">已选 {{ state.count }} 项</span><span v-else></span><button type="button" class="btn btn-link p-0" :disabled="busy || !state" @click="toggleSelection({ kind: 'all', id: '', checked: false, populatedOnly: false })">清空选择</button></div>
    </template>
    <ErrorNotice :error="error" retry :busy="busy" @retry="loadSelection" />
    <template v-if="open && state">
      <div v-if="!applied" class="d-flex align-items-center gap-1 mb-2">
        <input class="form-check-input ms-2 mt-0 flex-shrink-0" type="checkbox" aria-label="选择所有项目" :checked="!!displayedSelection?.total && displayedSelection.count === displayedSelection.total" :indeterminate="!!displayedSelection && displayedSelection.count > 0 && displayedSelection.count < displayedSelection.total" :disabled="busy" @change="chooseAll($event)" />
        <button type="button" class="btn text-start d-flex align-items-center gap-2" :aria-expanded="expanded" aria-controls="filter-plan-tree" @click="expanded = !expanded"><i :class="expanded ? 'ti ti-chevron-down' : 'ti ti-chevron-right'" aria-hidden="true"></i><i :class="expanded ? 'ti ti-folder-open' : 'ti ti-folder'" class="text-warning fs-3" aria-hidden="true"></i>所有项目</button>
      </div>
      <div v-show="expanded" id="filter-plan-tree"><RegistrationTestPlanBranch :key="revision" :keyword="applied" multiple :selection="state" :disabled="busy" :hide-empty="!showAll" :sample-scope="sampleScope" @toggle="toggleSelection" /></div>
    </template>
    <template #footer><button type="button" class="btn btn-light ms-auto" @click="close">关闭</button></template>
  </BootstrapOffcanvas>
</template>
