<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import { currentActor } from '../../stores/session'
import { fetchRegistrarOptions, type RegistrarOption } from '@/services/registrarDirectory'

const props = defineProps<{ kind: 'people' | 'departments'; value: string; disabled: boolean }>()
const emit = defineEmits<{ picked: [RegistrarOption] }>()
const open = ref(false), keyword = ref(''), loading = ref(false), error = ref('')
const rows = ref<RegistrarOption[]>([]), total = ref(0), page = ref(1)
let sequence = 0, controller: AbortController | undefined, timer: ReturnType<typeof setTimeout> | undefined
function cancel() { clearTimeout(timer); sequence++; controller?.abort(); loading.value = false }
function close() { cancel(); open.value = false; rows.value = [] }
async function load(next = 1) {
  cancel()
  if (!open.value || props.disabled) return
  const token = sequence, active = controller = new AbortController()
  rows.value = []; error.value = ''; loading.value = true
  try {
    const data = await fetchRegistrarOptions(props.kind, keyword.value.trim(), next, active.signal)
    if (token === sequence && open.value) { rows.value = data.rows; total.value = data.total; page.value = data.page }
  } catch (e) {
    if (token === sequence && !active.signal.aborted) error.value = e instanceof Error ? e.message : '加载失败，请重试'
  } finally { if (token === sequence) loading.value = false }
}
function show() { if (props.disabled) return; keyword.value = ''; open.value = true; void load() }
function choose(row: RegistrarOption) { if (props.disabled || loading.value) return; emit('picked', row); close() }
watch(keyword, () => { if (!open.value) return; cancel(); rows.value = []; timer = setTimeout(() => void load(), 300) }, { flush: 'sync' })
watch(() => [props.disabled, props.kind, currentActor.value], close)
onBeforeUnmount(cancel)
</script>

<template>
  <div class="input-group">
    <input class="form-control" :value="value" readonly :disabled="disabled" :aria-label="kind === 'people' ? '样品登记人' : '样品登记部门'" />
    <button v-if="!disabled" type="button" class="btn btn-light text-nowrap" @click="show">{{ kind === 'people' ? '选择人员' : '选择部门' }}</button>
  </div>
  <BootstrapModal :open="open" :loading="loading" :title="kind === 'people' ? '选择样品登记人' : '选择样品登记部门'" size="lg" scrollable @close="close">
    <template #toolbar>
      <form class="d-flex gap-2 mb-3" @submit.prevent="load()">
        <input v-model="keyword" class="form-control" :aria-label="kind === 'people' ? '搜索登记人' : '搜索登记部门'" :placeholder="kind === 'people' ? '姓名、账号或部门' : '部门名称或编码'" maxlength="200" />
        <button type="submit" class="btn btn-primary text-nowrap">搜索</button>
      </form>
      <p v-if="kind === 'people'" class="text-muted">全院人员均可搜索，选择后带入所属部门。停用账号保留显示，便于更正历史登记。</p>
    </template>
    <div v-if="error" role="alert" class="alert alert-danger">{{ error }} <button type="button" class="btn btn-light" @click="load()">重试</button></div>
    <template v-else>
      <div class="list-group">
        <button v-for="row in rows" :key="row.id" type="button" class="list-group-item list-group-item-action" :disabled="loading" @click="choose(row)">
          <strong>{{ row.name }}</strong>
          <span class="ms-2 text-muted">{{ row.account || row.code }}<template v-if="kind === 'people' && !row.enabled"> · 已停用</template></span>
          <div v-if="kind === 'people'" class="text-break">{{ row.department || '未分配部门' }}</div>
        </button>
      </div>
      <p v-if="!loading && !rows.length" class="text-muted">没有符合条件的{{ kind === 'people' ? '人员' : '部门' }}。</p>
      <TablePagination label="组织机构选项" :total="total" :page="page" :page-size="20" :sizes="[20]" @page="load" @size="load(1)" />
    </template>
    <template #footer><button type="button" class="btn btn-light" @click="close">关闭</button></template>
  </BootstrapModal>
</template>
