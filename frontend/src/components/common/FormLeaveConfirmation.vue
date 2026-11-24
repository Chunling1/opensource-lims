<script setup lang="ts">
import ConfirmationModal from './ConfirmationModal.vue'
import type { useFormLeaveGuard } from './useFormLeaveGuard'
defineProps<{ guard: ReturnType<typeof useFormLeaveGuard> }>()
</script>
<template>
  <ConfirmationModal v-if="guard.requested.value" title="放弃未保存内容" @close="guard.finish(false)">
    <p class="mb-0">内容尚未保存，离开将放弃未保存内容。确定离开？</p>
    <template #footer>
      <button type="button" class="btn btn-light" @click="guard.finish(false)">继续编辑</button>
      <button type="button" class="btn btn-danger" @click="guard.finish(true)">放弃更改</button>
    </template>
  </ConfirmationModal>
</template>
