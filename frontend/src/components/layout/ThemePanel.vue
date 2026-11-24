<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ManagedOffcanvas } from '../../services/common/offcanvas'
import { useThemeStore } from '../../stores/theme/index'
import { choices, type ThemeKey } from '../../stores/theme/settings'

const theme = useThemeStore()
const element = ref<HTMLElement>()
let panel: ManagedOffcanvas | undefined

onMounted(() => { panel = new ManagedOffcanvas(element.value!) })
onBeforeUnmount(() => panel?.dispose())
defineExpose({ show: () => panel?.show() })

function select(key: ThemeKey, value: string) {
  theme.set(key, value)
  if (key === 'preloader') panel?.hide()
}
</script>

<template>
  <div id="theme-settings-offcanvas" ref="element" class="offcanvas offcanvas-end" tabindex="-1" aria-labelledby="theme-title">
    <div class="offcanvas-header">
      <h2 id="theme-title" class="offcanvas-title">主题与布局设置</h2>
      <button id="customizerclose-btn" type="button" class="btn-close" aria-label="关闭主题设置" @click="panel?.hide()"></button>
    </div>
    <div class="offcanvas-body">
      <div v-if="theme.error" class="alert alert-warning" role="alert">{{ theme.error }}</div>

      <div v-for="(group, key) in choices" :key="key" class="mb-4">
        <label class="form-label fw-semibold">{{ group.label }}</label>
        <div class="btn-group w-100 flex-wrap" role="group" :aria-label="group.label">
          <button
            v-for="(label, val) in group.values"
            :key="val"
            type="button"
            class="btn"
            :class="theme.settings[key] === val ? 'btn-primary' : 'btn-outline-secondary'"
            :data-testid="`theme-${key}-${val}`"
            @click="select(key, String(val))"
          >
            {{ label }}
          </button>
        </div>
      </div>

      <div class="mt-4 pt-3 border-top d-flex gap-2">
        <button id="reset-layout" type="button" class="btn btn-outline-secondary w-100" @click="theme.reset()">
          <i class="ti ti-refresh me-1" aria-hidden="true"></i>恢复默认
        </button>
      </div>
    </div>
  </div>
</template>
