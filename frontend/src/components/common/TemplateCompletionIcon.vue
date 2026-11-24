<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { loadCompletionAnimation } from '../../services/common/completionAnimation'

const props = defineProps<{ active: boolean }>()
const animation = shallowRef<Record<string, unknown>>()
const ready = ref(false), visible = ref(false), reducedMotion = ref(true)
let preference: MediaQueryList | undefined
const playing = computed(() => props.active && visible.value && !reducedMotion.value)
function visibility() { visible.value = !document.hidden }
function motion() { reducedMotion.value = preference?.matches ?? true }
watch(playing, async active => {
  ready.value = false
  if (!active || animation.value) return
  try { animation.value = await loadCompletionAnimation() }
  catch { /* Decorative animation falls back to the existing static icon. */ }
})
onMounted(() => {
  preference = matchMedia('(prefers-reduced-motion: reduce)')
  motion(); visibility()
  preference.addEventListener('change', motion)
  document.addEventListener('visibilitychange', visibility)
})
onBeforeUnmount(() => {
  preference?.removeEventListener('change', motion)
  document.removeEventListener('visibilitychange', visibility)
})
</script>
<template>
  <div class="avatar-xl mx-auto position-relative" aria-hidden="true">
    <component :is="'lord-icon'" v-if="playing && animation" :icon.prop="animation" trigger="loop" colors="primary:#0ab39c,secondary:#405189" class="d-block w-100 h-100 position-absolute top-0 start-0" @ready="ready = true" />
    <slot v-if="!playing || !ready" />
  </div>
</template>
