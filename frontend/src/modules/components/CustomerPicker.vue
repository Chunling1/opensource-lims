<template>
  <div class="w-100">
    <div class="input-group">
    <el-input :model-value="modelValue" :readonly="!allowManual || disabled" :clearable="allowManual && !disabled" :aria-label="label" maxlength="500" :placeholder="allowManual ? '可选择客户，也可直接填写单位名称' : '请从客户数据库选择'" @update:model-value="onManualInput" />
    <el-button :disabled="disabled" :aria-label="`选择${label}`" @click="open">选择客户</el-button>
    <el-button v-if="modelValue && !disabled" :aria-label="`清除${label}`" @click="clearValue">清除</el-button>
    </div>
    <el-dialog v-model="visible" :title="`${label} · 客户数据库`" width="1100px" top="6vh" append-to-body :close-on-click-modal="false" @closed="stopRefresh">
      <p class="text-muted small">按名称或编码搜索，每页显示20家起；{{ multiple ? '可跨页多选，最多20家' : '只能选择一家' }}。</p>
      <form class="d-flex flex-wrap gap-2 mb-3" @submit.prevent="search">
        <div class="flex-grow-1">
        <el-input v-model="query" aria-label="客户名称或编码" placeholder="客户名称 / 客户编码" clearable />
        </div>
        <el-button native-type="submit" type="primary">搜索客户</el-button>
        <el-button @click="refresh">刷新客户库</el-button>
      </form>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <p role="status" class="text-muted small my-3">共 {{ total }} 家客户 · 已选 {{ selected.length }} 家 <span v-if="loading">· 正在更新</span><span v-else-if="updatedAt">· 最近刷新 {{ updatedAt }}</span></p>
      <div class="d-flex flex-wrap align-items-center gap-2 mb-3" aria-label="已选客户">
        <el-button v-if="selected.length" size="small" :disabled="disabled" @click="selected = []">清空已选</el-button>
        <el-tag v-for="c in selected" :key="c.code || c.name" :closable="!disabled" :close-label="`移除 ${c.name}`" @close="remove(c.name)">{{ c.name }}</el-tag>
      </div>
      <el-table :data="rows" border height="380" v-loading="loading">
        <el-table-column label="选择" width="72">
          <template #default="{ row }">
            <el-checkbox :model-value="selected.some(c => c.name === row.name)" :aria-label="`选择客户 ${row.code}`" :disabled="disabled" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="code" label="客户编码" min-width="170" />
        <el-table-column prop="name" label="客户名称" min-width="260" show-overflow-tooltip />
        <el-table-column prop="type" label="客户类型" min-width="130" show-overflow-tooltip />
        <el-table-column prop="dept" label="所属部门" min-width="160" show-overflow-tooltip />
        <el-table-column prop="addr" label="地址" min-width="210" show-overflow-tooltip />
        <template #empty>{{ error ? '加载失败，请刷新重试' : '没有符合条件的客户' }}</template>
      </el-table>
      <el-pagination :current-page="page" :page-size="size" :total="total" :page-sizes="pageSizes" layout="total, sizes, prev, pager, next" @current-change="changePage" @size-change="changeSize" />
      <template #footer>
        <el-button @click="visible = false">取消选择</el-button>
        <el-button type="primary" :disabled="disabled || loading || !!error" @click="confirm">确认选择</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { useLiveSearch } from '@/composables/liveSearch'
import { ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import type { Customer } from '@/services/pipeline'
import { fetchCustomerPage, splitCustomerNames } from '@/services/customerDirectory'

const props = withDefaults(defineProps<{ modelValue: string; label: string; multiple?: boolean; disabled?: boolean; allowManual?: boolean }>(), { multiple: false, disabled: false, allowManual: false })
const emit = defineEmits<{ 'update:modelValue': [string]; picked: [Customer[]] }>()
const pageSizes = [20, 50, 100]
const visible = ref(false), query = ref(''), activeQuery = ref(''), page = ref(1), size = ref(20), total = ref(0)
const rows = ref<Customer[]>([]), selected = ref<Customer[]>([]), loading = ref(false), error = ref(''), updatedAt = ref('')
let generation = 0
let controller: AbortController | undefined
function stopRefresh() { controller?.abort(); generation++; loading.value = false }
watch(visible, value => { if (!value) { stopRefresh(); liveSearch.cancel() } })
watch(() => props.disabled, value => { if (value) visible.value = false })
onBeforeUnmount(stopRefresh)

function clearValue() {
  if (props.disabled) return
  emit('update:modelValue', '')
  emit('picked', [])
}

function onManualInput(value: string) {
  if (!props.allowManual || props.disabled) return
  // Free text belongs to this form only: no directory writes or contact autofill.
  emit('update:modelValue', value)
}

async function load(fresh = false) {
  if (!visible.value || query.value.trim() !== activeQuery.value) return
  controller?.abort()
  const requestController = new AbortController()
  controller = requestController
  const timeout = setTimeout(() => requestController.abort(), 12000)
  const id = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = await fetchCustomerPage(activeQuery.value, page.value, size.value, fresh, requestController.signal)
    if (id !== generation || !visible.value) return
    total.value = result.total
    const lastPage = Math.max(1, Math.ceil(result.total / size.value))
    if (page.value > lastPage) { page.value = lastPage; await load(); return }
    rows.value = result.rows
    // Refresh selected metadata without altering selection, even across pages.
    selected.value = selected.value.map(c => result.rows.find(r => r.name === c.name) || c)
    updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    if (id !== generation || !visible.value) return
    error.value = '客户搜索失败或超时，请重试；原表单和已选客户未改变。'
    rows.value = []
  } finally { clearTimeout(timeout); if (id === generation) loading.value = false }
}
function open() {
  if (props.disabled) return
  stopRefresh()
  selected.value = splitCustomerNames(props.modelValue).map(name => ({ code: '', name }))
  query.value = ''; activeQuery.value = ''; page.value = 1; rows.value = []; total.value = 0
  visible.value = true
  void load(true)
}
function search() { liveSearch.cancel(); activeQuery.value = query.value.trim(); page.value = 1; void load(true) }
function refresh() { search() }
function changePage(value: number) { if (value !== page.value) { page.value = value; void load() } }
function changeSize(value: number) { size.value = value; page.value = 1; void load() }
function remove(name: string) { selected.value = selected.value.filter(c => c.name !== name) }
function toggle(row: Customer) {
  if (props.disabled) return
  if (selected.value.some(c => c.name === row.name)) { remove(row.name); return }
  if (!props.multiple) { selected.value = [row]; return }
  if (selected.value.length >= 20) { ElMessage.warning('委托单位最多选择20家客户'); return }
  selected.value = [...selected.value, row]
}
function confirm() {
  if (props.disabled || loading.value || error.value) return
  const value = selected.value
  // Unresolved historical values are preserved, not used to invent new records.
  emit('update:modelValue', value.map(c => c.name).join('、'))
  emit('picked', value)
  visible.value = false
}
watch(query, () => { generation++; controller?.abort(); loading.value = false }, { flush: 'sync' })
const liveSearch = useLiveSearch(query, () => { activeQuery.value = query.value.trim(); page.value = 1; void load() }, () => visible.value)
</script>


