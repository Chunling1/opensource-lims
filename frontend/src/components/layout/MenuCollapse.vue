<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Collapse from 'bootstrap/js/dist/collapse'
const props = defineProps<{ open: boolean }>()
const element = ref<HTMLElement>(), initiallyOpen = props.open
let instance: Collapse | undefined
function sync() { props.open ? instance?.show() : instance?.hide() }
onMounted(() => {
  instance = new Collapse(element.value!, { toggle: false })
  element.value!.addEventListener('shown.bs.collapse', sync)
  element.value!.addEventListener('hidden.bs.collapse', sync)
  sync()
})
watch(() => props.open, sync)
onBeforeUnmount(() => {
  element.value?.removeEventListener('shown.bs.collapse', sync)
  element.value?.removeEventListener('hidden.bs.collapse', sync)
  // Complete Bootstrap's pending transition before releasing its instance.
  element.value?.dispatchEvent(new Event('transitionend'))
  instance?.dispose()
})
</script>
<template><div ref="element" class="menu-dropdown collapse" :class="{ show: initiallyOpen }"><slot /></div></template>
