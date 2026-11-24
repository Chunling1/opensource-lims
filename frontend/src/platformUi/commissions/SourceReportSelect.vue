<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import { currentActor } from '../../stores/session'
import { fetchDerivableReportPage, type DerivableReport, type DerivableReportPage } from '@/services/pipeline'

const props = defineProps<{ modelValue: string; category: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string]; selected: [DerivableReport] }>()
const open = ref(false), keyword = ref(''), loading = ref(false), error = ref('')
const selected = ref<DerivableReport>()
const result = ref<DerivableReportPage>({ rows: [], total: 0, page: 1, size: 20 })
const sourceNo = (row: DerivableReport) => row.mainReportNo || row.reportNo
const label = computed(() => selected.value && sourceNo(selected.value) === props.modelValue
  ? `${selected.value.sampleNo || selected.value.reportNo} · ${selected.value.projectName}` : props.modelValue)
let controller: AbortController | undefined, timer: ReturnType<typeof setTimeout> | undefined, sequence = 0
function cancel() { clearTimeout(timer); sequence++; controller?.abort(); loading.value = false }
function close() { cancel(); open.value = false; result.value.rows = [] }
async function load(page = 1) {
  cancel()
  if (!open.value || props.disabled) return
  const token = sequence, active = controller = new AbortController()
  loading.value = true; error.value = ''; result.value.rows = []
  try {
    const data = await fetchDerivableReportPage({ category: props.category, keyword: keyword.value.trim(), page, size: 20 }, active.signal)
    if (token === sequence && open.value) result.value = data
  } catch (e) {
    if (token === sequence && !active.signal.aborted) error.value = e instanceof Error ? e.message : '原样品加载失败，请重试'
  } finally { if (token === sequence) loading.value = false }
}
function show() { if (props.disabled) return; keyword.value = ''; open.value = true; void load() }
function choose(row: DerivableReport) {
  if (props.disabled || loading.value) return
  selected.value = row; emit('update:modelValue', sourceNo(row)); emit('selected', row); close()
}
watch(keyword, () => { if (!open.value) return; cancel(); result.value.rows = []; timer = setTimeout(() => void load(), 300) }, { flush: 'sync' })
watch(() => [props.category, props.disabled, currentActor.value] as const, close)
onBeforeUnmount(cancel)
</script>

<template>
  <div class="input-group">
    <input class="form-control" :value="label" readonly placeholder="按样品编号搜索选择原报告" aria-label="已选原报告" />
    <button type="button" class="btn btn-light" :disabled="disabled" @click="show">选择原样品</button>
    <button v-if="modelValue" type="button" class="btn btn-light" :disabled="disabled" @click="selected = undefined; emit('update:modelValue', '')">清空</button>
  </div>
  <BootstrapModal :open="open" :loading="loading" title="选择原样品 / 报告" size="lg" scrollable @close="close">
    <template #toolbar>
      <form class="d-flex gap-2 mb-3" aria-label="搜索原样品" @submit.prevent="load()">
        <input v-model="keyword" class="form-control" aria-label="样品编号搜索" placeholder="样品编号、报告编号、名称或客户" maxlength="200" />
        <button type="submit" class="btn btn-primary text-nowrap flex-shrink-0">搜索</button>
      </form>
      <p class="text-muted">{{ ['分项', '英文'].includes(category) ? '可搜索数据权限范围内各阶段的已有样品，已作废记录不可作为来源。' : '显示已录入检测标准的原报告。' }}</p>
    </template>
    <div v-if="error" role="alert" class="alert alert-danger">{{ error }} <button type="button" class="btn btn-light" @click="load()">重试</button></div>
    <template v-else>
      <div class="list-group">
        <button v-for="row in result.rows" :key="row.reportNo" type="button" class="list-group-item list-group-item-action" :disabled="loading" @click="choose(row)">
          <strong>{{ row.sampleNo || row.reportNo }}</strong><span class="ms-2 text-muted">{{ row.status }}</span>
          <div class="text-break">{{ row.projectName }} · {{ row.client }}</div>
          <small class="text-muted">报告编号：{{ row.reportNo }}<template v-if="sourceNo(row) !== row.reportNo"> · 分项沿用主报告：{{ sourceNo(row) }}</template></small>
        </button>
      </div>
      <p v-if="!loading && !result.rows.length" class="text-muted">没有符合条件的样品。</p>
      <TablePagination label="原样品" :total="result.total" :page="result.page" :page-size="20" :sizes="[20]" @page="load" @size="load(1)" />
    </template>
    <template #footer><button type="button" class="btn btn-light" @click="close">关闭</button></template>
  </BootstrapModal>
</template>
