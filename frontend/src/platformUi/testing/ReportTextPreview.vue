<script setup lang="ts">
import { computed, ref } from 'vue'
const props = defineProps<{ id: string; label: string; text: string; separator: string; readonly?: boolean; hideSeparator?: boolean }>()
const emit = defineEmits<{ 'update:separator': [value: string] }>()
const options = [{ label: '分号', value: '；' }, { label: '顿号', value: '、' }, { label: '逗号', value: '，' }, { label: '空格', value: ' ' }, { label: '换行', value: '\n' }, { label: '不分隔', value: '' }]
const customChosen = ref(false)
const custom = computed(() => customChosen.value || !options.some(option => option.value === props.separator))
const description = computed(() => Array.from(props.separator).map(value => options.find(option => option.value === value)?.label || value).join(' + ') || '不分隔')
function choose(value: string) {
  if (props.readonly) return
  customChosen.value = value === 'custom'
  if (!customChosen.value) emit('update:separator', value)
}
function update(value: string) { if (!props.readonly && value.length <= 16) emit('update:separator', value) }
</script>
<template>
  <div>
    <div v-if="!hideSeparator" class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <label :for="`${id}-separator`" class="form-label mb-0">排列方式</label>
      <select :id="`${id}-separator`" class="form-select form-select-sm w-auto" :value="custom ? 'custom' : separator" :disabled="readonly" @change="choose(($event.target as HTMLSelectElement).value)">
        <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
        <option value="custom">自定义组合</option>
      </select>
      <span class="text-muted small">{{ description }}</span>
    </div>
    <div v-if="custom && !hideSeparator" class="mb-3">
      <div class="d-flex flex-wrap gap-1 mb-1">
        <button v-for="option in options.filter(o => o.value)" :key="option.value" type="button" class="btn btn-sm btn-light" :disabled="readonly || separator.length >= 16" @click="update(separator + option.value)">添加{{ option.label }}</button>
        <button type="button" class="btn btn-sm btn-light" :disabled="readonly || !separator" @click="update(separator.slice(0, -1))">撤销一个</button>
        <button type="button" class="btn btn-sm btn-light" :disabled="readonly || !separator" @click="update('')">清空</button>
      </div>
      <p class="small text-muted mb-0">按点击顺序组合，例如“分号 + 换行”；最多16个字符。</p>
    </div>
    <label :for="id" class="form-label small">{{ label }}</label>
    <textarea :id="id" :value="text" class="form-control" rows="4" readonly placeholder="选择内容后显示排列效果"></textarea>
    <p class="small text-muted mt-1 mb-0">文字排列即时预览；实际页内换行以完整报告 PDF 为准。</p>
  </div>
</template>
