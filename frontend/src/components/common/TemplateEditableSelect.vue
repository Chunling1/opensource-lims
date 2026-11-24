<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Dropdown from 'bootstrap/js/dist/dropdown'

const props = defineProps<{ id: string; label: string; modelValue: string; options: string[]; placeholder?: string; readonly?: boolean; loading?: boolean; maxlength?: number; multiple?: boolean; required?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const input = ref<HTMLInputElement>(), button = ref<HTMLButtonElement>()
let dropdown: Dropdown | undefined
const selected = computed(() => [...new Set(props.modelValue.split(/[；;\r\n]+/).map(value => value.trim()).filter(Boolean))])
onMounted(() => { dropdown = new Dropdown(button.value!, { autoClose: props.multiple ? 'outside' : true }) })
onBeforeUnmount(() => dropdown?.dispose())
watch(() => props.readonly || props.loading, value => { if (value) dropdown?.hide() })
async function select(value: string) {
  if (props.readonly || props.loading) return
  if (props.multiple) {
    const values = selected.value.includes(value) ? selected.value.filter(item => item !== value) : [...selected.value, value]
    emit('update:modelValue', values.join('；'))
    await nextTick(); input.value?.dispatchEvent(new Event('change', { bubbles: true }))
    return
  }
  emit('update:modelValue', value)
  await nextTick(); input.value?.dispatchEvent(new Event('change', { bubbles: true }))
  dropdown?.hide()
  input.value?.focus()
}
</script>

<template>
  <div class="input-group">
    <input :id="id" ref="input" class="form-control" :class="{ 'bg-body-tertiary': readonly }" :aria-label="label" :value="modelValue" :placeholder="placeholder" :readonly="readonly" :required="required" :maxlength="maxlength" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
    <button ref="button" class="btn btn-light dropdown-toggle" type="button" data-bs-toggle="dropdown" :aria-label="loading ? `正在加载${label}选项` : `选择${label}`" :aria-busy="loading" :aria-controls="`${id}-options`" aria-expanded="false" :disabled="readonly || loading || !options.length"><span v-if="loading" class="spinner-border spinner-border-sm" aria-hidden="true"></span></button>
    <ul :id="`${id}-options`" class="dropdown-menu dropdown-menu-end w-100" :aria-label="`${label}选项`">
      <li v-for="option in options" :key="option">
        <label v-if="multiple" class="dropdown-item d-flex align-items-center gap-2 text-wrap mb-0"><input class="form-check-input m-0 flex-shrink-0" type="checkbox" :checked="selected.includes(option)" :disabled="readonly" @change="select(option)" /><span>{{ option }}</span></label>
        <button v-else class="dropdown-item text-wrap" :class="{ active: modelValue === option }" type="button" :disabled="readonly" @click="select(option)">{{ option }}</button>
      </li>
    </ul>
  </div>
</template>
