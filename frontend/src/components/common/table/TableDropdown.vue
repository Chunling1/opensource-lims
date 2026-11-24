<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import Dropdown from 'bootstrap/js/dist/dropdown'
const props = defineProps<{ label: string; disabled?: boolean; keepOpen?: boolean; iconOnly?: boolean }>()
const button = ref<HTMLElement>()
let dropdown: Dropdown | undefined
onMounted(() => { dropdown = new Dropdown(button.value!, { autoClose: props.keepOpen ? 'outside' : true }) })
// Bootstrap skips disabled toggles when closing menus. Close before Vue disables it.
watch(() => props.disabled, disabled => { if (disabled) dropdown?.hide() }, { flush: 'sync' })
onBeforeUnmount(() => dropdown?.dispose())
</script>
<template><div class="dropdown"><button ref="button" type="button" class="btn btn-light text-nowrap" :class="iconOnly ? 'btn-icon' : 'dropdown-toggle'" data-bs-toggle="dropdown" :aria-label="label" :disabled="disabled" aria-expanded="false"><i v-if="iconOnly" class="ti ti-dots" aria-hidden="true"></i><template v-else>{{ label }}</template></button><div class="dropdown-menu dropdown-menu-end"><slot /></div></div></template>
