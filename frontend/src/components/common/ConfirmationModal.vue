<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, provide, ref } from 'vue'
import { feedbackTargetKey } from './feedbackContext'
import { useDialogValidation } from '../forms/useDialogValidation'
const props = defineProps<{ title: string; busy?: boolean; size?: 'lg' | 'xl'; fillHeight?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const element = ref<HTMLDialogElement>(), feedbackTarget = ref<HTMLElement>()
useDialogValidation(element)
provide(feedbackTargetKey, feedbackTarget)
// Keep the confirmation inside the current Bootstrap focus boundary while the
// native top layer makes it modal above that window, without a second Bootstrap trap.
const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
const target = opener?.closest('.modal.show') || [...document.querySelectorAll('.modal.show')].at(-1) || document.body
const alreadyLocked = document.body.classList.contains('modal-open')
const opened = ref(false)
let openingFrame = 0
function close() { if (!props.busy) emit('close') }
onMounted(() => {
  document.body.classList.add('modal-open')
  // Finish the opener's key event first: Escape on the parent must not also
  // cancel the confirmation created by that same event.
  openingFrame = requestAnimationFrame(async () => {
    opened.value = true
    await nextTick()
    if (element.value?.isConnected) { element.value.showModal(); element.value.focus() }
  })
})
onBeforeUnmount(() => {
  cancelAnimationFrame(openingFrame)
  element.value?.close()
  if (!alreadyLocked && !document.querySelector('.modal.show')) document.body.classList.remove('modal-open')
  void nextTick(() => { if (opener?.isConnected) opener.focus() })
})
</script>
<template>
  <Teleport :to="target">
    <dialog ref="element" class="modal border-0 p-0 m-0 mw-100 mh-100 bg-dark bg-opacity-50" :class="{ 'd-block': opened }" :aria-label="title" aria-modal="true" tabindex="-1" @cancel.prevent="close" @keydown.stop>
      <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable" :class="size ? `modal-${size}` : undefined"><div class="modal-content" :class="{ 'h-100': fillHeight }">
        <div class="modal-header"><h5 class="modal-title">{{ title }}</h5><button type="button" class="btn-close" aria-label="关闭弹窗" :disabled="busy" @click="close"></button></div>
        <div class="modal-body" :class="{ 'p-0 overflow-hidden': fillHeight }"><slot /></div>
        <div v-if="$slots.footer" class="modal-footer"><slot name="footer" /></div>
      </div></div>
      <div ref="feedbackTarget" class="toast-container position-fixed top-0 end-0 p-3"></div>
    </dialog>
  </Teleport>
</template>
