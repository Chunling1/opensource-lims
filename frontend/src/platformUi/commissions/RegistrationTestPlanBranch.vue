<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import LoadState from '../../components/common/LoadState.vue'
import SingleChoice from '../../components/common/SingleChoice.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import { inject } from 'vue'
const registrationDemo = inject<any>('platform-registration-services')!
if (!registrationDemo) throw Error('缺少平台表单服务')
import { useTestPlanCache } from '../../services/common/testPlanCache'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { TestPlanNode } from '../../types/commissions/sampleForm'
import type { PlanSelectionState, PlanSelectionToggle } from '../../types/samples/inbound'
import type { RegistrationPage } from '../../types/commissions/registration'

const props = defineProps<{ queryPlans?: typeof registrationDemo.testPlans; parentId?: string; keyword: string; selectedId?: string; multiple?: boolean; selection?: PlanSelectionState; disabled?: boolean; hideEmpty?: boolean; sampleScope?: 'inbound' | 'outbound' | 'disposal' | 'flow' | 'assignment' | 'pickup' | 'task-query' | 'data-entry' | 'data-check' | 'sample-copy' | 'data-changes' | 'report-check' | 'report-review' | 'report-approval' | 'report-print' | 'report-signing' | 'report-distribution' | 'report-archive' | 'report-query' }>()
const emit = defineEmits<{ select: [TestPlanNode]; toggle: [PlanSelectionToggle] }>()
const result = ref<RegistrationPage<TestPlanNode>>({ items: [], total: 0, page: 1, pageSize: 10 })
const expanded = ref<string[]>([]), loading = ref(false), error = ref<ErrorValue>('')
// Mount a branch only on its first expansion; hiding it preserves its request,
// loaded pages and page number for the lifetime of this catalogue query.
const visited = ref<string[]>([])
const filtered = computed(() => result.value.items.filter(node => !props.hideEmpty || ((props.sampleScope === 'report-query' ? node.reportQuerySampleCount : props.sampleScope === 'report-archive' ? node.reportArchiveSampleCount : props.sampleScope === 'report-distribution' ? node.reportDistributionSampleCount : props.sampleScope === 'report-signing' ? node.reportSigningSampleCount : props.sampleScope === 'report-print' ? node.reportPrintSampleCount : props.sampleScope === 'report-review' ? node.reportReviewSampleCount : props.sampleScope === 'report-approval' ? node.reportApprovalSampleCount : props.sampleScope === 'report-check' ? node.reportCheckSampleCount : props.sampleScope === 'data-changes' ? node.dataChangeSampleCount : props.sampleScope === 'sample-copy' ? node.sampleCopySampleCount : props.sampleScope === 'data-check' ? node.dataCheckSampleCount : props.sampleScope === 'data-entry' ? node.dataEntrySampleCount : props.sampleScope === 'task-query' ? node.taskQuerySampleCount : props.sampleScope === 'assignment' ? node.assignmentSampleCount : props.sampleScope === 'pickup' ? node.pickupSampleCount : props.sampleScope === 'flow' ? node.flowSampleCount : props.sampleScope === 'disposal' ? node.disposalSampleCount : props.sampleScope === 'outbound' ? node.outboundSampleCount : node.inboundSampleCount) || 0) > 0))
const groupSelection = computed(() => props.hideEmpty && props.selection?.populated ? props.selection.populated.groups : props.selection?.groups)
const total = computed(() => props.multiple ? filtered.value.length : result.value.total)
const visibleIds = computed(() => new Set((props.multiple ? filtered.value.slice((result.value.page - 1) * result.value.pageSize, result.value.page * result.value.pageSize) : filtered.value).map(node => node.id)))
const cache = useTestPlanCache()
let controller: AbortController | undefined, sequence = 0
async function load(page = 1) {
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  const cacheKey = JSON.stringify(['tree', props.queryPlans === registrationDemo.equipmentTestPlans ? 'equipment' : 'registration', props.sampleScope, props.parentId, props.keyword, !!props.multiple, props.multiple ? 1 : page])
  const cached = cache?.get<RegistrationPage<TestPlanNode>>(cacheKey), cacheRevision = cache?.revision
  error.value = ''; expanded.value = []; visited.value = []
  if (cached) { result.value = cached; loading.value = false; return }
  loading.value = true; result.value.items = []
  try {
    const query = { parentId: props.parentId, keyword: props.keyword, page: props.multiple ? 1 : page, pageSize: 10, sampleScope: props.sampleScope }
    const data = await (props.queryPlans || registrationDemo.testPlans)(query, active.signal)
    // Cache this expanded branch before filtering, so occupied items on later pages
    // remain reachable and changing the display scope needs no new request.
    if (props.multiple) {
      for (let next = 2; next <= Math.ceil(data.total / data.pageSize); next++) {
        const batch = await (props.queryPlans || registrationDemo.testPlans)({ ...query, page: next }, active.signal)
        data.items.push(...batch.items)
      }
    }
    if (token === sequence && !active.signal.aborted) { result.value = data; cache?.set(cacheKey, data, cacheRevision!) }
  } catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
function checked(node: TestPlanNode) {
  if (!props.multiple) return props.selectedId === node.id
  const selection = props.selection?.selection
  return !!selection && (selection.groupIds.includes(node.parentId || '') ? !selection.excludedPlanIds.includes(node.id) : selection.planIds.includes(node.id))
}
function choose(node: TestPlanNode, event: Event) {
  if (!props.multiple) { emit('select', node); return }
  const input = event.target as HTMLInputElement, next = input.checked
  input.checked = node.kind === 'group' ? !!groupSelection.value?.[node.id]?.checked : checked(node)
  input.indeterminate = node.kind === 'group' && !!groupSelection.value?.[node.id]?.indeterminate
  emit('toggle', { kind: node.kind, id: node.id, checked: next })
}
function toggle(id: string) {
  if (!visited.value.includes(id)) visited.value.push(id)
  expanded.value = expanded.value.includes(id) ? expanded.value.filter(value => value !== id) : [...expanded.value, id]
}
function changePage(page: number) { if (props.multiple) result.value.page = page; else void load(page) }
watch(() => props.hideEmpty, () => { result.value.page = 1 })
watch(() => [props.parentId, props.keyword], () => void load(), { immediate: true })
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>

<template>
  <ErrorNotice :error="error" retry @retry="load(result.page)" />
  <LoadState v-if="loading" loading />
  <template v-else-if="!error">
    <ul class="list-unstyled mb-0">
      <li v-for="node in result.items" v-show="visibleIds.has(node.id)" :key="node.id">
        <template v-if="node.kind === 'group'">
          <div class="d-flex align-items-center gap-1 bg-light rounded mb-1">
          <input v-if="multiple" class="form-check-input ms-2 mt-0 flex-shrink-0" type="checkbox" :aria-label="`选择分组 ${node.name}`" :checked="groupSelection?.[node.id]?.checked" :indeterminate="groupSelection?.[node.id]?.indeterminate" :disabled="disabled" @change="choose(node, $event)" />
          <button class="btn btn-light text-start w-100 d-flex align-items-center gap-2" type="button" :aria-expanded="expanded.includes(node.id)" :aria-controls="`plan-group-${node.id}`" @click="toggle(node.id)">
            <i :class="expanded.includes(node.id) ? 'ti ti-chevron-down' : 'ti ti-chevron-right'" aria-hidden="true"></i>
            <i :class="expanded.includes(node.id) ? 'ti ti-folder-open' : 'ti ti-folder'" class="text-warning fs-3 flex-shrink-0" aria-hidden="true"></i>
            <span class="text-break">{{ node.name }}</span>
          </button>
          </div>
          <div v-if="visited.includes(node.id)" v-show="expanded.includes(node.id)" :id="`plan-group-${node.id}`" class="ms-3 mb-2">
            <RegistrationTestPlanBranch :query-plans="queryPlans" :parent-id="node.id" keyword="" :selected-id="selectedId" :multiple="multiple" :selection="selection" :disabled="disabled" :hide-empty="hideEmpty" :sample-scope="sampleScope" @select="emit('select', $event)" @toggle="emit('toggle', $event)" />
          </div>
        </template>
        <label v-else class="d-flex align-items-center gap-2 p-2 mb-1 rounded" :class="{ 'bg-primary-subtle': checked(node) }">
          <input v-if="multiple" class="form-check-input mt-0 flex-shrink-0" type="checkbox" :disabled="disabled" :checked="checked(node)" :aria-label="`选择 ${node.name}`" @change="choose(node, $event)" />
          <SingleChoice v-else name="test-plan-choice" :disabled="disabled" :checked="checked(node)" :label="`选择 ${node.name}`" @change="choose(node, $event)" />
          <i class="ti ti-file-text text-primary fs-3 flex-shrink-0" aria-hidden="true"></i>
          <span class="text-break"><span>{{ node.name }}</span><span v-if="node.code" class="d-inline-block ms-2 text-muted small font-monospace">{{ node.code }}</span><small v-if="keyword" class="d-block text-muted">{{ node.groupName }}</small></span>
        </label>
      </li>
    </ul>
    <p v-if="!total" class="text-muted text-center py-4 mb-0">没有符合条件的检测方案</p>
    <TablePagination v-if="total > result.pageSize" :label="parentId ? '分组检测方案' : '检测方案'" :total="total" :page="result.page" :page-size="result.pageSize" :sizes="[10]" @page="changePage" />
  </template>
</template>
