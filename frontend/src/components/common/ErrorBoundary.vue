<script setup lang="ts">
import { onErrorCaptured, ref, shallowRef, watch } from 'vue'
import { normalizeError, type AppError } from '../../services/common/errors'
import ErrorPage from './ErrorPage.vue'
const props = defineProps<{ resetKey?: string; standalone?: boolean }>()
const error = shallowRef<AppError>(), generation = ref(0)
onErrorCaptured(value => { error.value = normalizeError(value); return false })
function reset() { error.value = undefined; generation.value++ }
watch(() => props.resetKey, reset)
</script>
<template><ErrorPage v-if="error" :error="error" :standalone="standalone" retry @retry="reset" /><slot v-else :key="generation" /></template>
