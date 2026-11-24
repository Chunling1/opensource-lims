<template>
  <div class="mb-3">
    <fieldset :disabled="disabled || loading || downloading" class="mb-2">
      <legend class="fs-5 mb-2">导出页码</legend>
      <div class="d-flex flex-wrap align-items-center gap-3">
        <label v-for="page in pageCount" :key="page" class="form-check mb-0">
          <input v-model="selectedPages" class="form-check-input" type="checkbox" :value="page" />
          <span class="form-check-label">第 {{ page }} 页</span>
        </label>
        <span v-if="loading" class="text-muted" role="status">正在读取页码…</span>
        <span v-else-if="!url" class="text-muted">生成预览后可选择下载页码</span>
      </div>
    </fieldset>
    <div class="d-flex flex-wrap align-items-center gap-2">
      <button type="button" class="btn btn-primary btn-sm" :disabled="disabled || loading || downloading || !document || !selectedPages.length" @click="download">
        {{ downloading ? '正在准备下载…' : '下载委托单 PDF' }}
      </button>
      <span v-if="document && !selectedPages.length" class="text-muted">请至少选择一页</span>
      <button v-if="error && !document" type="button" class="btn btn-light btn-sm" :disabled="disabled || loading" @click="load">重试读取页码</button>
    </div>
    <div v-if="error" class="text-danger mt-2" role="alert">{{ error }}</div>
    <div v-else-if="downloadStatus" class="text-success mt-2" role="status">{{ downloadStatus }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import type { PDFDocument } from 'pdf-lib'

const props = defineProps<{
  url: string
  filename: string
  disabled?: boolean
  beforeDownload?: () => Promise<boolean>
}>()
const document = shallowRef<PDFDocument>()
const selectedPages = ref<number[]>([])
const loading = ref(false), downloading = ref(false), error = ref('')
const downloadStatus = ref('')
const pageCount = computed(() => document.value?.getPageCount() ?? 0)
let revision = 0
let request: AbortController | undefined

// Read the exact PDF displayed in the preview, including overflow pages.
// Changing records/templates invalidates both page choices and in-flight downloads.
async function load() {
  const current = ++revision, url = props.url
  request?.abort()
  request = new AbortController()
  document.value = undefined
  selectedPages.value = []
  error.value = ''
  downloadStatus.value = ''
  loading.value = !!url
  if (!url) return
  try {
    const response = await fetch(url, { signal: request.signal })
    if (!response.ok) throw new Error('PDF 读取失败，请刷新预览后重试')
    const { PDFDocument } = await import('pdf-lib')
    const pdf = await PDFDocument.load(await response.arrayBuffer())
    if (current !== revision) return
    document.value = pdf
    selectedPages.value = pdf.getPageIndices().map(index => index + 1)
  } catch (cause) {
    if (current === revision) error.value = cause instanceof Error ? cause.message : 'PDF 页码读取失败，请刷新预览后重试'
  } finally {
    if (current === revision) loading.value = false
  }
}
async function download() {
  if (props.disabled || loading.value || downloading.value || !document.value || !selectedPages.value.length) return
  const current = revision, source = document.value, url = props.url, filename = props.filename
  const pages = [...selectedPages.value].sort((a, b) => a - b)
  downloading.value = true
  error.value = ''
  downloadStatus.value = ''
  let slicedUrl = ''
  try {
    if (props.beforeDownload && !await props.beforeDownload()) return
    if (current !== revision || props.url !== url || props.disabled) return
    let downloadUrl = url
    if (pages.length !== source.getPageCount()) {
      const { PDFDocument } = await import('pdf-lib')
      const selected = await PDFDocument.create()
      for (const page of await selected.copyPages(source, pages.map(page => page - 1))) selected.addPage(page)
      slicedUrl = URL.createObjectURL(new Blob([new Uint8Array(await selected.save())], { type: 'application/pdf' }))
      downloadUrl = slicedUrl
    }
    if (current !== revision || props.url !== url || props.disabled) return
    const link = window.document.createElement('a')
    link.href = downloadUrl
    link.download = pages.length === source.getPageCount() ? filename : `${filename.replace(/\.pdf$/i, '')}-第${pages.join('-')}页.pdf`
    link.click()
    downloadStatus.value = `已生成下载文件：第 ${pages.join('、')} 页`
  } catch (cause) {
    if (current === revision) error.value = cause instanceof Error ? cause.message : 'PDF 下载失败，请重试'
  } finally {
    if (slicedUrl) setTimeout(() => URL.revokeObjectURL(slicedUrl), 1000)
    downloading.value = false
  }
}
watch(() => props.url, load, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => { ++revision; request?.abort() })
</script>
