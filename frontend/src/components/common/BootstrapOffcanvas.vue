<script setup lang="ts">
import { onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { feedbackTargetKey } from './feedbackContext'
import { useDialogValidation } from '../forms/useDialogValidation'
import { ManagedOffcanvas } from '../../services/common/offcanvas'
import LoadState from './LoadState.vue'
const props = defineProps<{ open: boolean; title: string; loading?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const element = ref<HTMLElement>()
useDialogValidation(element)
const feedbackTarget = ref<HTMLElement>()
provide(feedbackTargetKey, feedbackTarget)
let instance: ManagedOffcanvas | undefined
let media: MediaQueryList | undefined
// Bootstrap owns the show/hide classes; keep Vue from replacing them on render.
const resize = () => { element.value?.classList.toggle('w-100', media?.matches ?? false) }
onMounted(() => {
  media = window.matchMedia('(max-width: 575.98px)'); media.addEventListener('change', resize); resize()
  instance = new ManagedOffcanvas(element.value!, () => emit('close'))
  if (props.open) instance.show()
})
watch(() => props.open, open => open ? instance?.show() : instance?.hide())
onBeforeUnmount(() => { media?.removeEventListener('change', resize); instance?.dispose() })
</script>
<template>
  <Teleport to="body"><div ref="element" class="offcanvas offcanvas-end" tabindex="-1" :aria-label="title">
    <div class="offcanvas-header"><h5 class="offcanvas-title">{{ title }}</h5><button type="button" class="btn-close" aria-label="关闭抽屉" @click="emit('close')"></button></div>
    <div v-if="$slots.toolbar" class="px-3 pb-3 flex-shrink-0"><slot name="toolbar" /></div>
    <div class="offcanvas-body p-3" :aria-busy="loading"><LoadState v-if="loading" loading /><slot v-else /></div>
    <div class="border-top p-3 d-flex flex-wrap align-items-center justify-content-end gap-2 flex-shrink-0"><slot name="footer" /></div>
    <div ref="feedbackTarget" class="toast-container position-fixed top-0 end-0 p-3"></div>
  </div></Teleport>
</template>
