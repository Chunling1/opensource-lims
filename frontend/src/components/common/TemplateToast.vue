<script setup lang="ts">
import { inject, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import Toast from 'bootstrap/js/dist/toast'
import { feedbackTargetKey, insideToastKey } from './feedbackContext'
const props = withDefaults(defineProps<{ message: string; title?: string; tone?: 'success' | 'warning' | 'danger'; autohide?: boolean; withinModal?: boolean; autoShow?: boolean; trigger?: unknown }>(), { autohide: true, title: '系统提示' })
const target = inject(feedbackTargetKey, undefined)
provide(insideToastKey, true)
const element = ref<HTMLElement>()
let instance: Toast | undefined
function syncMessage() { if (props.autoShow) { if (props.message) instance?.show(); else instance?.hide() } }
onMounted(() => { instance = new Toast(element.value!, { delay: 3500, autohide: props.autohide }); syncMessage() })
watch(() => [props.message, props.trigger], syncMessage, { flush: 'post' })
onBeforeUnmount(() => { element.value?.dispatchEvent(new Event('transitionend')); instance?.dispose() })
defineExpose({ show: () => instance?.show(), hide: () => instance?.hide() })
</script>
<template><Teleport :to="target || 'body'" :disabled="withinModal && !target"><div :class="target ? 'mb-2' : 'toast-container position-fixed top-0 end-0 p-3'"><div ref="element" class="toast" :class="tone ? `toast-border-${tone}` : undefined" :role="tone === 'danger' || tone === 'warning' ? 'alert' : 'status'" :aria-live="tone === 'danger' || tone === 'warning' ? 'assertive' : 'polite'" aria-atomic="true"><div class="toast-header"><i aria-hidden="true" class="me-2" :class="tone === 'warning' ? 'ti ti-alert-circle text-warning' : tone === 'danger' ? 'ti ti-alert-circle text-danger' : 'ti ti-circle-check text-success'"></i><strong class="me-auto">{{ title }}</strong><button type="button" class="btn-close" :aria-label="`关闭${title}`" @click="instance?.hide()"></button></div><div class="toast-body"><slot>{{ message }}</slot></div></div></div></Teleport></template>
