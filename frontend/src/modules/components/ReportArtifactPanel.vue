<template>
  <el-card shadow="never" class="mb-3">
    <template #header><strong>报告文件</strong></template>
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <el-button :loading="loading" @click="load">刷新</el-button>
      <el-button :loading="previewing" :disabled="loading || previewing || !original?.canPreview" @click="preview">预览当前报告</el-button>
      <el-button :disabled="loading || !original?.canDownload" @click="download(false)">下载原件</el-button>
      <el-button v-if="signedEntry" :disabled="loading || !signed?.canDownload || downloading" @click="download(true)">下载签字盖章版</el-button>
    </div>
    <p class="text-muted small">预览当前报告和下载原件均为未签字、未盖章版本。</p>
    <div v-for="notice in original?.preview?.notices || []" :key="notice" class="alert alert-warning" role="status">{{ notice }}</div>
    <p v-if="previewing || downloading" role="status" class="text-muted small">正在核对报告版本，内容有更新时自动生成最新文件，请稍候。</p>
    <p v-if="originalError" class="text-danger">{{ originalError }}</p>
    <p v-if="signedEntry && signedError" class="text-muted small">{{ signedError }}</p>
    <el-dialog v-model="previewOpen" title="当前报告（未签字、未盖章）" append-to-body width="1200px" @closed="clearPreview"><div v-for="notice in original?.preview?.notices || []" :key="notice" class="alert alert-warning" role="status">{{ notice }}</div><DataEntryPreview v-if="url" :url="url" title="当前报告（未签章）" name="" type="application/pdf" embedded compact persistent hide-download /></el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { artifactObjectUrl, fetchReportArtifact, fetchSignedReportArtifact, signedReportObjectUrl, type ReportArtifact } from '@/services/reportAssurance'
const props = defineProps<{ reportNo: string; view: string }>()
const signedEntry = computed(() => ['query', 'release', 'print'].includes(props.view))
const original = ref<ReportArtifact | null>(null), signed = ref<ReportArtifact | null>(null)
const loading = ref(false), downloading = ref(false), previewing = ref(false), originalError = ref(''), signedError = ref(''), url = ref(''), previewOpen = ref(false)
let generation = 0
const message = (e: unknown) => e instanceof Error ? e.message : '报告文件暂不可用，请刷新重试'
function clearPreview() { if (url.value) URL.revokeObjectURL(url.value); url.value = '' }
async function load() {
  const id = ++generation
  previewing.value = downloading.value = false
  original.value = signed.value = null; originalError.value = signedError.value = ''; loading.value = true
  clearPreview(); previewOpen.value = false
  const results = await Promise.allSettled([fetchReportArtifact(props.reportNo, props.view, true), ...(signedEntry.value ? [fetchSignedReportArtifact(props.reportNo, props.view)] : [])])
  if (id !== generation) return
  if (results[0].status === 'fulfilled') original.value = results[0].value
  else originalError.value = message(results[0].reason)
  if (results[1]?.status === 'fulfilled') signed.value = results[1].value
  else if (results[1]?.status === 'rejected') signedError.value = message(results[1].reason)
  loading.value = false
}
async function preview() {
  if (previewing.value) return
  const id = generation
  previewing.value = true
  try { const value = await artifactObjectUrl(props.reportNo, props.view, false, true); if (id !== generation) { URL.revokeObjectURL(value); return } clearPreview(); url.value = value; previewOpen.value = true; const latest = await fetchReportArtifact(props.reportNo, props.view, true); if (id === generation) original.value = latest }
  catch (e) { if (id === generation) ElMessage.error(message(e)) }
  finally { if (id === generation) previewing.value = false }
}
async function download(withSignature: boolean) {
  if (downloading.value) return
  const id = generation, no = props.reportNo, view = props.view; downloading.value = true
  try {
    const value = withSignature ? await signedReportObjectUrl(no, view) : await artifactObjectUrl(no, view, true, true)
    if (id === generation) { const a = document.createElement('a'); a.href = value; a.download = `${no}-${withSignature ? 'signed-sealed' : 'unsigned-original'}.pdf`; a.click() }
    setTimeout(() => URL.revokeObjectURL(value), 1000)
    if (!withSignature) { const latest = await fetchReportArtifact(no, view, true); if (id === generation) original.value = latest }
  } catch (e) { if (id === generation) ElMessage.error(message(e)) }
  finally { if (id === generation) downloading.value = false }
}
watch(() => [props.reportNo, props.view], load, { immediate: true })
onBeforeUnmount(() => { ++generation; clearPreview() })
</script>
