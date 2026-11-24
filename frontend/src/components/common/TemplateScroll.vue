<script setup lang="ts">
import { ref } from 'vue'
defineOptions({ inheritAttrs: false })
withDefaults(defineProps<{ enabled?: boolean; label?: string }>(), { enabled: true, label: '滚动区域' })
const root = ref<HTMLElement>()

defineExpose({
  reveal: (element: HTMLElement | null) => {
    const scroller = root.value
    if (!scroller || !element) return
    const item = element.getBoundingClientRect()
    const area = scroller.getBoundingClientRect()
    if (item.top < area.top || item.bottom > area.bottom) {
      scroller.scrollTop += item.top - area.top - 24
    }
  },
})
</script>

<template>
  <div ref="root" v-bind="$attrs" :class="{ 'lims-scroll': enabled }" :tabindex="enabled ? 0 : undefined" :role="enabled ? 'region' : undefined" :aria-label="enabled ? label : undefined">
    <slot />
  </div>
</template>
