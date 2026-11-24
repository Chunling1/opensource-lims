<script setup lang="ts">
import PersonnelAttachments from './PersonnelAttachments.vue'
import type { DemoAttachment } from '../../types/commissions/registration'
defineProps<{ files: DemoAttachment[] }>()
</script>
<template>
  <PersonnelAttachments :files="files" :readonly="false" label="上岗证附件" />
</template>
