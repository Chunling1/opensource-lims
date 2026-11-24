<template>
  <div>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
      <label :for="`${id}-separator`" class="mb-0 small">分隔符</label>
      <select :id="`${id}-separator`" class="form-select form-select-sm w-auto" :value="mode" :disabled="readonly" @change="choose(($event.target as HTMLSelectElement).value)">
        <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
        <option value="custom">自定义组合</option>
      </select>
      <span class="text-muted small">{{ description }}</span>
    </div>
    <div v-if="custom" class="mb-2">
      <div class="d-flex flex-wrap align-items-center gap-1 mb-1">
        <button v-for="option in options" :key="option.value" type="button" class="btn btn-sm btn-light" :disabled="readonly" @click="$emit('update:separator', separator + option.value)">添加{{ option.label }}</button>
        <button type="button" class="btn btn-sm btn-light" :disabled="readonly || !separator" @click="$emit('update:separator', separator.slice(0, -1))">撤销一个</button>
        <button type="button" class="btn btn-sm btn-light" :disabled="readonly || !separator" @click="$emit('update:separator', '')">清空</button>
      </div>
      <p class="text-muted small mb-0">按点击顺序组合，例如先选分号，再添加空格或换行。</p>
    </div>
    <textarea :id="id" class="form-control" :aria-label="label" :value="text" rows="4" readonly :placeholder="placeholder"></textarea>
    <p class="text-muted small mt-1 mb-0">此处文字用于委托单；选择和排序请打开上方弹窗。</p>
  </div>
</template>

<script setup lang="ts">
import {computed, ref} from 'vue'
const props = defineProps<{id:string; label:string; text:string; separator:string; readonly?:boolean; placeholder:string}>()
const emit = defineEmits<{'update:separator':[value:string]}>()
const options = [{label:'分号',value:'；'},{label:'顿号',value:'、'},{label:'逗号',value:'，'},{label:'空格',value:' '},{label:'换行',value:'\n'}]
const customChosen = ref(false)
const custom = computed(() => customChosen.value || !options.some(option => option.value === props.separator))
const mode = computed(() => custom.value ? 'custom' : props.separator)
const description = computed(() => Array.from(props.separator).map(value => options.find(option => option.value === value)?.label || value).join(' + ') || '不分隔')
function choose(value:string) {
  customChosen.value = value === 'custom'
  if (value !== 'custom') emit('update:separator', value)
}
</script>
