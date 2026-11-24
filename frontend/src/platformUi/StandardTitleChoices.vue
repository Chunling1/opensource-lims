<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TitleStyle } from './testing/reportTextDisplay'
const props = defineProps<{ id: string; codes: string[]; labels?: Record<string,string>; names: Record<string,string>; modelValue: Record<string,TitleStyle>; defaultStyle: TitleStyle; readonly?: boolean; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: Record<string,TitleStyle>] }>()
const query = ref(''), page = ref(1), pageSize = 5
const filtered = computed(() => props.codes.filter(code => `${props.labels?.[code] || code} ${props.names[code] || ''}`.toLocaleLowerCase().includes(query.value.trim().toLocaleLowerCase())))
const pages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize)))
const visible = computed(() => filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize))
const locked = computed(() => props.readonly || props.disabled)
const choices: {value: TitleStyle; label: string}[] = [{value:'CN',label:'中文《》'},{value:'EN',label:'英文 <>'},{value:'none',label:'不加书名号'}]
watch(query, () => { page.value = 1 })
watch(() => props.codes.join('\n'), () => { query.value = ''; page.value = 1 })
watch(pages, count => { page.value = Math.min(page.value, count) })
function choose(code: string, style: string) {
  if (!locked.value && choices.some(choice => choice.value === style)) emit('update:modelValue', {...props.modelValue, [code]: style as TitleStyle})
}
function chooseAll(style: TitleStyle) {
  if (!locked.value) emit('update:modelValue', {...props.modelValue, ...Object.fromEntries(props.codes.map(code => [code, style]))})
}
</script>
<template>
  <div>
    <div v-if="codes.length" class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <span class="small text-muted">统一设置全部 {{ codes.length }} 条</span>
      <div class="btn-group btn-group-sm" role="group" aria-label="统一设置全部标准书名号">
        <button v-for="choice in choices" :key="choice.value" type="button" class="btn btn-light" :disabled="locked" @click="chooseAll(choice.value)">{{ choice.label }}</button>
      </div>
    </div>
    <div v-if="codes.length > pageSize" class="mb-3">
      <label :for="`${id}-search`" class="visually-hidden">查找已选标准</label>
      <div class="input-group input-group-sm"><input :id="`${id}-search`" v-model="query" class="form-control" type="search" placeholder="输入标准编号或名称查找" /><button v-if="query" class="btn btn-light" type="button" @click="query = ''">清除</button></div>
    </div>
    <div class="d-flex flex-column gap-3" role="group" aria-label="每条标准的书名号">
      <div v-for="(code, index) in visible" :key="code" class="row g-2 align-items-center">
        <div class="col-12 col-md-8"><label :for="`${id}-style-${index}`" class="form-label mb-0 text-break">{{ labels?.[code] || code }}</label><div class="small text-muted text-truncate" :title="names[code] || '未找到标准名称，将仅显示编号'">{{ names[code] || '未找到标准名称，将仅显示编号' }}</div></div>
        <div class="col-12 col-md-4"><select :id="`${id}-style-${index}`" class="form-select form-select-sm" :aria-label="`${code} 书名号`" :value="modelValue[code] || modelValue[labels?.[code] || code] || defaultStyle" :disabled="locked" @change="choose(code, ($event.target as HTMLSelectElement).value)"><option v-for="choice in choices" :key="choice.value" :value="choice.value">{{ choice.label }}</option></select></div>
      </div>
    </div>
    <p v-if="!visible.length" class="text-muted small mb-0" role="status">{{ codes.length ? '没有匹配的标准，请更换关键词。' : '选择检测依据后，可逐条设置书名号。' }}</p>
    <div v-if="codes.length > pageSize" class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-3">
      <span class="small text-muted" role="status">{{ filtered.length ? `第 ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, filtered.length)} 条 / 共 ${filtered.length} 条` : '0 条匹配' }}</span>
      <nav class="btn-group btn-group-sm" aria-label="标准书名号分页"><button type="button" class="btn btn-light" :disabled="page <= 1" @click="page--">上一页</button><button type="button" class="btn btn-light" :disabled="page >= pages" @click="page++">下一页</button></nav>
    </div>
  </div>
</template>
