<template>
  <el-card
    shadow="never"
    
    :data-title-only="Boolean(title && !description && !$slots.title && !$slots.meta)"
  >
    <template v-if="title || $slots.title || $slots.meta" #header>
      <div class="d-flex flex-wrap align-items-center justify-content-between gap-3">
        <div >
          <slot name="title">
            <strong>{{ title }}</strong>
            <p v-if="description">{{ description }}</p>
          </slot>
        </div>
        <div v-if="$slots.meta" class="d-flex align-items-center gap-2">
          <slot name="meta" />
        </div>
      </div>
    </template>
    <slot />
    <div v-if="$slots.footer" class="border-top mt-3">
      <slot name="footer" />
    </div>
  </el-card>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  {
    title: '',
    description: '',
  },
)
</script>
