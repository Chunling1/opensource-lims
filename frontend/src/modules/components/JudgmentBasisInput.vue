<template>
  <div>
    <ul v-if="entries.length" class="list-group mb-2" aria-label="已添加判定标准">
      <li v-for="(entry, index) in entries" :key="entry" class="list-group-item d-flex flex-wrap align-items-center justify-content-between gap-2">
        <span class="text-break">{{ entry }}</span>
        <div v-if="!disabled" class="d-flex gap-2">
          <button type="button" class="btn btn-sm btn-light" :aria-label="`编辑第 ${index + 1} 条判定标准`" @click="edit(index)">编辑</button>
          <button type="button" class="btn btn-sm btn-light" :aria-label="`移除第 ${index + 1} 条判定标准`" @click="remove(index)">移除</button>
        </div>
      </li>
    </ul>
    <div v-if="!disabled" class="d-flex flex-column flex-sm-row align-items-sm-start gap-2">
      <div class="flex-grow-1">
        <el-autocomplete :key="inputVersion" v-model="draft" :fetch-suggestions="suggest" :debounce="250"
          aria-label="输入一条判定标准" placeholder="输入一条标准，或搜索标准库；无需判定填 /"
          @select="add($event.value)" @keydown.enter.prevent.stop="add(draft)" />
      </div>
      <div class="d-flex gap-2">
        <button type="button" class="btn btn-light text-nowrap" :disabled="!draft.trim()" @click="add(draft)">
          {{ editing ? '更新此条' : '添加' }}
        </button>
        <button v-if="editing || draft" type="button" class="btn btn-link text-nowrap" @click="reset">取消输入</button>
      </div>
    </div>
    <div v-if="error" role="status" class="text-danger small d-block mt-1">{{ error }}</div>
    <div v-if="!disabled" class="text-muted small mt-1">从标准库选中即加入。手写时每次添加一条，可保留名称中的标点。</div>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { searchJudgmentStandards } from '@/services/quality'
import { judgmentEntries } from '../../platformUi/testing/reportTextDisplay'
const props = defineProps<{ modelValue: readonly string[] | undefined; legacy: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const entries = computed(() => props.modelValue ?? [...new Set(judgmentEntries(props.legacy))])
const draft = ref('')
const editing = ref<string>()
const inputVersion = ref(0)
const error = ref('')
let sequence = 0
type Suggestion = { value: string }
defineExpose({ hasPending: computed(() => !!draft.value.trim() && draft.value.trim() !== editing.value) })

function reset() {
  ++sequence
  inputVersion.value++
  draft.value = ''
  editing.value = undefined
  error.value = ''
}
function edit(index: number) {
  reset()
  editing.value = entries.value[index]
  draft.value = editing.value
}
function remove(index: number) {
  if (entries.value[index] === editing.value) reset()
  emit('update:modelValue', entries.value.filter((_, current) => current !== index))
}
function add(value: string) {
  const entry = value.trim()
  if (!entry) return
  if (entries.value.includes(entry) && entry !== editing.value) {
    error.value = '这条判定标准已添加。'
    return
  }
  const updated = editing.value === undefined
    ? [...entries.value, entry]
    : entries.value.map(item => item === editing.value ? entry : item)
  emit('update:modelValue', updated)
  reset()
}
async function suggest(query: string, callback: (rows: Suggestion[]) => void) {
  const request = ++sequence
  const keyword = query.trim()
  error.value = ''
  if (!keyword || keyword === '/') { callback([]); return }
  try {
    const result = await searchJudgmentStandards(keyword)
    if (request !== sequence) return
    if (result.total > result.rows.length) error.value = `匹配 ${result.total} 项，显示前 ${result.rows.length} 项，请补充关键词缩小范围。`
    callback(result.rows.map(row => ({ value: row.name ? `${row.code} 《${row.name}》` : row.code })))
  } catch {
    if (request !== sequence) return
    error.value = '标准库读取失败，可手写添加，或重新输入关键词重试。'
    callback([])
  }
}
onBeforeUnmount(() => { ++sequence })
</script>

