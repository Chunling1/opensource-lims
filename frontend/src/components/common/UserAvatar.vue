<script setup lang="ts">
import { computed, ref, watch } from 'vue'
const props = defineProps<{ src?: string }>()
const failed = ref(false)
watch(() => props.src, () => { failed.value = false })
const hasImage = computed(() => !failed.value && !!props.src && !props.src.includes('user-dummy-img'))
</script>

<template>
  <img v-if="hasImage" :src="props.src" alt="用户头像" class="avatar avatar-sm object-fit-cover" @error="failed = true" />
  <span v-else class="avatar avatar-sm bg-primary-lt text-primary rounded-circle d-inline-flex align-items-center justify-content-center" aria-hidden="true">
    <i class="ti ti-user fs-4"></i>
  </span>
</template>
