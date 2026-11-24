<template>
  <div >
    <div v-if="modelValue.length" class="d-flex flex-wrap gap-2">
      <el-tag v-for="(item, index) in modelValue" :key="`${index}:${item}`" :closable="!disabled"
        @close="remove(index)">{{ item }}</el-tag>
    </div>
    <div class="input-group">
      <el-input v-model="draft" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }" :disabled="disabled"
        aria-label="库外项目输入" placeholder="输入项目后回车或点添加；多项用分号或换行分隔"
        @keydown="onKeydown" @blur="commit" @compositionstart="composing = true" @compositionend="composing = false" />
      <el-button :disabled="disabled || !draft.trim()" @click="commit">添加</el-button>
    </div>
    <div class="text-muted small">仅填写库内没有的项目，不会写入能力库；添加后仍须填写原因并进行合规核查。</div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{ modelValue: string[]; disabled?: boolean }>(), { disabled: false })
const emit = defineEmits<{ 'update:modelValue': [value: string[]]; change: [value: string[]] }>()
const draft = ref('')
const composing = ref(false)
watch(() => props.modelValue, () => { draft.value = ''; composing.value = false })

function update(value: string[]) {
  emit('update:modelValue', value)
  emit('change', value)
}
function commit() {
  if (props.disabled || composing.value) return
  // Commas may belong to a parameter name; do not split or rewrite saved items.
  const additions = draft.value.split(/[;；\r\n]+/).map(item => item.trim()).filter(Boolean)
  draft.value = ''
  const result = [...props.modelValue]
  for (const item of additions) if (!result.includes(item)) result.push(item)
  if (result.length !== props.modelValue.length) update(result)
}
function remove(index: number) {
  if (!props.disabled) update(props.modelValue.filter((_, current) => current !== index))
}
function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229 || composing.value) return
  event.preventDefault()
  commit()
}
defineExpose({ commit })
</script>


