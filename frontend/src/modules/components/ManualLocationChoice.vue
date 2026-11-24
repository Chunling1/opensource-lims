<template>
  <fieldset class="mt-3">
    <legend class="form-label fs-6">库外检测地点</legend>
    <div class="d-flex flex-wrap gap-2" role="group" aria-label="库外地点方式">
      <button type="button" class="btn btn-sm" :class="modelValue.mode === 'library' ? 'btn-primary' : 'btn-outline-primary'"
        :aria-pressed="modelValue.mode === 'library'" @click="setMode('library')">与库内项目一致</button>
      <button type="button" class="btn btn-sm" :class="modelValue.mode === 'selected' ? 'btn-primary' : 'btn-outline-primary'"
        :aria-pressed="modelValue.mode === 'selected'" @click="setMode('selected')">单独选择地点</button>
    </div>
    <p v-if="modelValue.mode === 'library'" class="small mt-2 mb-0" :class="libraryAddresses.length ? 'text-body' : 'text-danger'">
      {{ libraryAddresses.length ? libraryAddresses.join('；') : '尚未选择有地点的库内参数，请先添加库内参数，或单独选择地点。' }}
    </p>
    <div v-else class="mt-2">
      <p v-if="loading" role="status" class="small">正在读取数据库地点…</p>
      <p v-else-if="error" role="alert" class="small text-danger">{{ error }}<button class="btn btn-sm btn-outline-danger ms-2" type="button" @click="$emit('retry')">重试</button></p>
      <div v-else class="d-flex flex-column gap-2">
        <label v-for="address in options" :key="address" class="border rounded p-2 d-flex align-items-start gap-2">
          <input type="checkbox" class="form-check-input flex-shrink-0 mt-1" :checked="modelValue.addresses.includes(address)" @change="toggle(address)" />
          <span class="text-break">{{ address }}</span>
        </label>
        <p v-if="!options.length" class="small mb-0">数据库暂无可选地点，请联系管理员维护。</p>
        <p v-if="invalidAddresses.length" class="small text-danger mb-0">原地点已不在当前库中：{{ invalidAddresses.join('；') }}。请选择现有地点。</p>
      </div>
    </div>
  </fieldset>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { ManualParameterLocation } from '@/data/parameterLocations'
const props = defineProps<{ modelValue: ManualParameterLocation; options: string[]; libraryAddresses: string[]; loading?: boolean; error?: string }>()
const emit = defineEmits<{ 'update:modelValue': [ManualParameterLocation]; retry: [] }>()
const invalidAddresses = computed(() => props.modelValue.addresses.filter(address => !props.options.includes(address)))
function setMode(mode: ManualParameterLocation['mode']) { emit('update:modelValue', { mode, addresses: props.modelValue.addresses }) }
function toggle(address: string) {
  const current = props.modelValue.addresses.filter(value => props.options.includes(value))
  emit('update:modelValue', { mode: 'selected', addresses: current.includes(address) ? current.filter(value => value !== address) : [...current, address] })
}
</script>
