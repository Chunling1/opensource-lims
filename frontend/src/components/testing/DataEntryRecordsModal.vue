<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import FormTabs from '../forms/FormTabs.vue'
import TablePagination from '../common/table/TablePagination.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import type { EntryRecordKind, EntryRecordsPage } from '../../types/testing/dataEntryRecords'

const props = defineProps<{ sampleId: string; mode?: 'changes' | 'issues' }>()
const emit = defineEmits<{ close: [] }>()
const kind = ref<EntryRecordKind>('commission'), result = ref<EntryRecordsPage>(), loading = ref(false), error = ref<ErrorValue>(''), page = ref(1), pageSize = ref(10)
const displayedMode = ref<'changes' | 'issues'>('changes')
const title = computed(() => displayedMode.value === 'issues' ? '问题记录' : '修改记录')
const tabs = [{ key: 'commission', label: '委托更改记录', tabId: 'entry-history-commission', panelId: 'entry-history-panel' }, { key: 'testing', label: '检测更改记录', tabId: 'entry-history-testing', panelId: 'entry-history-panel' }]
const columns = computed(() => displayedMode.value === 'issues' ? [
  ['submitterId', '提交人账号'], ['submitter', '提交人'], ['description', '问题描述'], ['type', '问题类型'], ['destination', '退回方向'], ['submittedAt', '提交日期'], ['handlerId', '处理人账号'], ['handler', '处理人'], ['opinion', '处理意见'], ['handledAt', '处理日期'], ['sequence', '第几次问题'],
] : [['actor', '修改人员'], ['at', '修改日期'], ['field', '修改信息项'], ['before', '改前值'], ['after', '改后值'], ['type', '修改类型'], ['sequence', '第几次修改']])
let sequence = 0, controller: AbortController | undefined
// Keep each visited page for this dialog session. Reopening fetches fresh records.
const pages = new Map<string, EntryRecordsPage>()
async function load() {
  const token = ++sequence; controller?.abort(); error.value = ''
  if (!props.mode) { loading.value = false; return }
  const key = `${kind.value}:${page.value}:${pageSize.value}`
  result.value = pages.get(key)
  if (result.value) { page.value = result.value.page; loading.value = false; return }
  const abort = controller = new AbortController(); loading.value = true
  try {
    const response = await registrationDemo.entryRecords(props.sampleId, { kind: kind.value, page: page.value, pageSize: pageSize.value }, abort.signal)
    if (token === sequence) { pages.set(key, response); result.value = response; page.value = response.page }
  } catch (issue) { if (token === sequence && !abort.signal.aborted) error.value = normalizeError(issue) }
  finally { if (token === sequence) loading.value = false }
}
function selectTab(value: string) { if (value === kind.value) return; kind.value = value as EntryRecordKind; page.value = 1; void load() }
function changePage(value: number) { page.value = value; void load() }
function changeSize(value: number) { pageSize.value = value; changePage(1) }
function cell(row: object, key: string) { const value = (row as Record<string, unknown>)[key]; return value === '' || value == null ? '—' : String(value) }
watch(() => [props.mode, props.sampleId], () => {
  if (props.mode) { pages.clear(); result.value = undefined; displayedMode.value = props.mode; kind.value = props.mode === 'issues' ? 'issues' : 'commission'; page.value = 1 }
  void load()
}, { immediate: true })
watch(currentActor, () => { sequence++; controller?.abort(); pages.clear(); result.value = undefined; emit('close') })
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<template>
  <BootstrapModal :loading="loading" :open="!!mode" :title="title" size="xl" scrollable fullscreen-mobile fill-height body-class="p-0 mx-3 overflow-auto" @close="$emit('close')">
    <template #toolbar><div v-if="displayedMode === 'changes'" class="mx-3"><FormTabs :model-value="kind" :tabs="tabs" label="修改记录分类" @update:model-value="selectTab" /></div></template>
    <div id="entry-history-panel" :role="displayedMode === 'changes' ? 'tabpanel' : undefined" :aria-labelledby="displayedMode === 'changes' ? `entry-history-${kind}` : undefined" :aria-busy="loading">
      <ErrorNotice :error="error" retry :busy="loading" @retry="load" />
      <table class="table table-striped table-hover table-nowrap align-middle mb-0"><thead class="table-light"><tr><th v-for="[key, label] in columns" :key="key" scope="col">{{ label }}</th></tr></thead><tbody>
        <tr v-for="row in result?.items || []" :key="`${kind}-${row.id}`"><td v-for="[key] in columns" :key="key" :class="['field', 'before', 'after', 'description', 'opinion'].includes(key!) ? 'text-wrap text-break' : ''">{{ cell(row, key!) }}</td></tr>
        <tr v-if="loading"><td :colspan="columns.length" class="text-center text-muted py-4"><span role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载记录…</span></td></tr>
        <tr v-else-if="result && !result.items.length"><td :colspan="columns.length" class="text-center text-muted py-4">暂无{{ displayedMode === 'issues' ? '问题' : kind === 'testing' ? '检测更改' : '委托更改' }}记录</td></tr>
      </tbody></table>
    </div>
    <template #pagination><fieldset :disabled="loading || !result"><TablePagination :label="title" :total="result?.total || 0" :page="page" :page-size="pageSize" :sizes="[10, 20, 50]" extended @page="changePage" @size="changeSize" /></fieldset></template>
    <template #footer><button type="button" class="btn btn-light" @click="$emit('close')">返回</button></template>
  </BootstrapModal>
</template>
