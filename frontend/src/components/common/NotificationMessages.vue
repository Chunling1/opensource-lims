<script setup lang="ts">
import { demoNotifications } from '../../services/business/demoNotifications'
</script>

<template>
  <ul class="list-unstyled mb-0" aria-label="通知消息">
    <li v-for="message in demoNotifications" :key="message.id" class="notification-item d-flex p-3 border-bottom">
      <div class="avatar-xs me-3 flex-shrink-0"><span class="avatar rounded-circle fs-4" :class="`bg-${message.tone}-subtle text-${message.tone}`"><i aria-hidden="true" :class="message.icon"></i></span></div>
      <div class="flex-grow-1 overflow-hidden">
        <h6 class="mb-1 small fw-semibold">{{ message.title }}</h6>
        <p class="small text-body text-wrap text-break mb-2">{{ message.content }}</p>
        <time class="small text-muted" :datetime="message.at">{{ new Date(message.at).toLocaleString('zh-CN') }}</time>
      </div>
    </li>
  </ul>
</template>
