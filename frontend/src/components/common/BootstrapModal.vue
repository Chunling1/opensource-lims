<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, provide, ref, watch } from 'vue'
import { feedbackTargetKey } from './feedbackContext'
import { useDialogValidation } from '../forms/useDialogValidation'
import Modal from 'bootstrap/js/dist/modal'
import LoadState from './LoadState.vue'
const props = defineProps<{ open: boolean; title: string; busy?: boolean; loading?: boolean; guardClose?: boolean; size?: 'lg' | 'xl'; scrollable?: boolean; fullscreenMobile?: boolean; fillHeight?: boolean; compactHeight?: boolean | 'large'; bodyClass?: string; compact?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const element = ref<HTMLElement>()
useDialogValidation(element)
const feedbackTarget = ref<HTMLElement>()
provide(feedbackTargetKey, feedbackTarget)
const viewportHeight = ref(900)
const updateViewport = () => { viewportHeight.value = window.innerHeight }
// Reserve a modest, stable area for attachments; short windows need more of the available height.
const heightClass = computed(() => props.compactHeight
  ? viewportHeight.value < 560 ? 'h-100' : viewportHeight.value < 800 || props.compactHeight === 'large' ? 'h-75' : 'h-50'
  : props.fillHeight ? 'h-100' : undefined)
let instance: Modal | undefined
let opener: HTMLElement | null = null
let modalElement: HTMLElement | undefined
let active = false, unmounting = false
const dispose = () => {
  modalElement?.removeEventListener('show.bs.modal', opening)
  modalElement?.removeEventListener('shown.bs.modal', shown)
  modalElement?.removeEventListener('hidden.bs.modal', hidden)
  modalElement?.removeEventListener('hide.bs.modal', preventBusyClose)
  instance?.dispose(); instance = undefined
  // Bootstrap may reattach a modal if its opening transition finishes after unmount.
  if (unmounting) modalElement?.remove()
}
const opening = () => { active = true }
const shown = () => { if (unmounting || !props.open) instance?.hide() }
const hidden = () => {
  active = false
  if (unmounting) { dispose(); return }
  if (opener?.isConnected) opener.focus()
  emit('close')
}
const show = () => { opener = document.activeElement instanceof HTMLElement ? document.activeElement : null; instance?.show() }
const preventBusyClose = (e: Event) => { if (props.busy || props.guardClose) { e.preventDefault(); if (!props.busy && props.guardClose) emit('close') } }
onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  modalElement = element.value!
  instance = new Modal(modalElement, { backdrop: 'static' })
  modalElement.addEventListener('show.bs.modal', opening)
  modalElement.addEventListener('shown.bs.modal', shown)
  modalElement.addEventListener('hidden.bs.modal', hidden)
  modalElement.addEventListener('hide.bs.modal', preventBusyClose)
  if (props.open) show()
})
watch(() => props.open, open => open ? show() : instance?.hide())
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewport)
  unmounting = true
  modalElement?.removeEventListener('hide.bs.modal', preventBusyClose)
  // The show class disappears before the backdrop finishes closing. Wait for
  // hidden.bs.modal so Bootstrap restores body overflow and scrollbar padding.
  if (active) instance?.hide()
  else dispose()
})
</script>
<template>
  <Teleport to="body"><div ref="element" class="modal fade" tabindex="-1" :aria-label="title || '确认操作'" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered" :class="[size ? `modal-${size}` : '', { 'modal-dialog-scrollable': scrollable || compactHeight, 'modal-fullscreen-sm-down': fullscreenMobile && !compactHeight }]"><div class="modal-content" :class="heightClass">
      <div class="modal-header" :class="{ 'py-2': compact }"><h5 class="modal-title">{{ title }}<slot name="title-suffix" /></h5><button type="button" class="btn-close" aria-label="关闭弹窗" :disabled="busy" @click="$emit('close')"></button></div>
      <div v-if="$slots.toolbar" class="px-3 flex-shrink-0"><slot name="toolbar" /></div>
      <div class="modal-body" :aria-busy="loading" :class="[bodyClass, { 'py-2': compact }]"><LoadState v-if="loading" loading /><slot v-else /></div>
      <div v-if="$slots.pagination && !loading" class="flex-shrink-0"><slot name="pagination" /></div>
      <div v-if="$slots.footer" class="modal-footer" :class="{ 'py-2': compact }"><slot name="footer" /></div>
    </div></div>
    <div ref="feedbackTarget" class="toast-container position-fixed top-0 end-0 p-3"></div>
  </div></Teleport>
</template>
