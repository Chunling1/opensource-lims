<template>
  <ol class="list-group list-unstyled mb-0" :aria-label="label">
    <li v-for="(item, index) in items" :key="item.key" class="list-group-item d-flex align-items-start gap-2 px-2 py-3"
      :class="{ 'bg-warning-subtle': item.manual, 'border-primary': dropKey === item.key }"
      @dragover="over($event, item.key)" @dragleave="dropKey = ''" @drop="drop($event, index)">
      <button v-if="!readonly" type="button" class="btn btn-sm btn-light flex-shrink-0 p-1" draggable="true"
        :aria-label="`拖动排序 ${item.label}，也可用右侧上移下移按钮`" title="拖动调整顺序"
        @dragstart="start($event, item.key)" @dragend="dragKey = ''; dropKey = ''"><i class="ti ti-grip-vertical" aria-hidden="true"></i></button>
      <span class="text-body pt-1 flex-shrink-0">{{ index + 1 }}</span>
      <div class="flex-grow-1 text-break overflow-hidden"><div class="d-flex align-items-start gap-2"><span class="flex-grow-1">{{ item.label }}</span>
        <span v-if="showSource" class="badge flex-shrink-0 mt-1" :class="item.manual ? 'bg-warning-subtle text-body' : 'bg-primary-subtle text-primary'">{{ item.manual ? '库外' : '库内' }}</span></div>
        <small v-if="item.detail" class="text-body d-block mt-1">{{ item.detail }}</small><slot name="item-extra" :item="item" /></div>
      <div v-if="!readonly" class="d-flex flex-column flex-sm-row gap-1 flex-shrink-0">
        <button type="button" class="btn btn-sm btn-light" :disabled="index === 0" :aria-label="`上移 ${item.label}`" title="上移" @click="move(index, index - 1)"><i class="ti ti-arrow-up" aria-hidden="true"></i></button>
        <button type="button" class="btn btn-sm btn-light" :disabled="index === items.length - 1" :aria-label="`下移 ${item.label}`" title="下移" @click="move(index, index + 1)"><i class="ti ti-arrow-down" aria-hidden="true"></i></button>
        <button v-if="removable" type="button" class="btn btn-sm btn-ghost-danger" :aria-label="`移除 ${item.label}`" title="移除" @click="$emit('remove', item.key)"><i class="ti ti-x" aria-hidden="true"></i></button>
      </div>
    </li>
  </ol>
  <span class="visually-hidden" role="status" aria-live="polite">{{ announcement }}</span>
</template>
<script setup lang="ts">
import { ref } from 'vue'
const props = withDefaults(defineProps<{ items: { key: string; label: string; detail?: string; manual?: boolean }[]; label: string; readonly?: boolean; removable?: boolean; showSource?: boolean }>(), { readonly: false, removable: true, showSource: false })
const emit = defineEmits<{ reorder: [keys: string[]]; remove: [key: string] }>()
const dragKey = ref(''), dropKey = ref(''), announcement = ref('')
function start(event: DragEvent, key: string) { if (props.readonly) return; dragKey.value = key; if (event.dataTransfer) { event.dataTransfer.effectAllowed = 'move'; event.dataTransfer.setData('text/plain', key) } }
function over(event: DragEvent, key: string) { if (!props.readonly && dragKey.value) { event.preventDefault(); dropKey.value = key } }
function drop(event: DragEvent, index: number) { event.preventDefault(); const from = props.items.findIndex(item => item.key === dragKey.value); move(from, index); dragKey.value = ''; dropKey.value = '' }
function move(from: number, to: number) {
  if (props.readonly || from < 0 || to < 0 || to >= props.items.length || from === to) return
  const keys = props.items.map(item => item.key), [key] = keys.splice(from, 1); keys.splice(to, 0, key!)
  announcement.value = `${props.items[from]!.label}已移至第 ${to + 1} 项`; emit('reorder', keys)
}
</script>
