<script setup lang="ts">
import { nextTick, ref, useId, watch } from 'vue'
import { downloadBlob } from '../../services/reports/reportPdf'
const props = defineProps<{ url: string; name: string; type: string; blob?: Blob; title: string; subtitle?: string; persistent?: boolean; embedded?: boolean; collapsible?: boolean; autoPrint?: boolean; compact?: boolean; hideDownload?: boolean; hidePrint?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const frame = ref<HTMLIFrameElement>()
const collapsed = ref(false), contentId = useId()
const printError = ref('')
let printed = false
function expand() { collapsed.value = false }
watch(() => props.url, expand)
async function print() {
  if (!props.url || props.hidePrint) return
  expand(); await nextTick(); printError.value = ''
  try { frame.value?.contentWindow?.print() }
  catch { printError.value = '未能打开打印窗口，请使用“新窗口预览”后打印。' }
}
function loaded() { if (props.autoPrint && !printed && props.url) { printed = true; void print() } }
defineExpose({ expand })
</script>
<template>
  <section id="entry-preview" :class="embedded ? 'mb-0' : 'card mb-0'" :aria-label="title">
    <div class="d-flex flex-wrap align-items-center gap-3" :class="embedded ? compact ? 'mb-2' : 'mb-4' : ['card-header', { 'py-2': compact }]">
      <div v-if="embedded"><h4 class="text-break" :class="subtitle ? 'mb-2' : 'mb-0'">{{ title }}</h4><p v-if="subtitle" class="text-muted mb-0">{{ subtitle }}</p></div>
      <h5 v-else class="card-title mb-0 text-break">{{ title }}</h5>
      <div class="ms-sm-auto d-flex flex-wrap gap-2">
        <a v-if="url" :href="url" target="_blank" rel="noopener" class="btn btn-light">新窗口预览</a><button v-else class="btn btn-light" type="button" disabled>新窗口预览</button>
        <button v-if="!hideDownload" class="btn btn-light" type="button" :disabled="!blob" @click="blob && downloadBlob(blob, name)">下载</button>
        <button v-if="type === 'application/pdf' && !hidePrint" class="btn btn-light" type="button" :disabled="!url" @click="print">打印</button>
        <button v-if="collapsible && url" class="btn btn-light" type="button" :aria-expanded="!collapsed" :aria-controls="contentId" @click="collapsed = !collapsed"><i :class="collapsed ? 'ti ti-chevron-down' : 'ti ti-chevron-up'" class="me-1" aria-hidden="true"></i>{{ collapsed ? '展开预览' : '收起预览' }}</button>
        <button v-if="!persistent" class="btn btn-light" type="button" @click="emit('close')">关闭预览</button>
        <slot name="actions" />
      </div>
    </div>
    <div :class="{ 'card-body': !embedded, 'py-2': compact && !embedded }">
      <slot name="before" />
      <p v-if="printError" class="text-danger" role="alert">{{ printError }}</p>
      <div :id="contentId" v-show="!collapsed">
        <slot v-if="!url" name="empty"><p class="text-muted text-center py-5 mb-0">暂无可预览文件</p></slot>
        <img v-else-if="type.startsWith('image/')" :src="url" :alt="name" class="img-fluid" />
        <iframe v-else ref="frame" :src="url" :title="title" class="w-100 border rounded" height="650" @load="loaded"></iframe>
      </div>
    </div>
  </section>
</template>
