<script setup lang="ts">
import { inject } from 'vue'
import TemplateToast from './TemplateToast.vue'
import { feedbackTargetKey, insideToastKey } from './feedbackContext'
defineOptions({ inheritAttrs: false })
withDefaults(defineProps<{ message: string; title?: string; tone?: 'warning' | 'danger'; compact?: boolean; trigger?: unknown }>(), { title: '操作提示', tone: 'warning' })
const target = inject(feedbackTargetKey, undefined), insideToast = inject(insideToastKey, false)
</script>
<template>
  <TemplateToast v-if="target && !insideToast" :message="message" :title="title" :tone="tone" :trigger="trigger" auto-show :autohide="false"><slot>{{ message }}</slot></TemplateToast>
  <div v-else v-bind="$attrs" :class="compact || insideToast ? undefined : ['alert', `alert-${tone}`]" role="alert" :aria-label="title"><slot>{{ message }}</slot></div>
</template>
