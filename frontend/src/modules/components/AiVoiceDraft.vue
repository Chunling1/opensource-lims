<template>
  <el-button type="primary" plain :loading="busy" @click="recording ? stop() : start()">
    <el-icon><Microphone /></el-icon>{{ recording ? `停止录音 ${elapsed}s` : 'AI 语音录入' }}
  </el-button>
  <el-dialog v-model="reviewOpen" title="确认 AI 表单草稿" width="720px" append-to-body>
    <el-alert type="warning" :closable="false" show-icon title="只有勾选并确认的字段会写入当前内存表单；仍需您手工保存。" />
    <p ><strong>识别原话：</strong>{{ transcript }}</p>
    <el-table :data="patches" border>
      <el-table-column width="54"><template #default="{ $index }"><el-checkbox v-model="selected[$index]" /></template></el-table-column>
      <el-table-column prop="path" label="字段" width="150" />
      <el-table-column label="候选值"><template #default="{ row }">{{ Array.isArray(row.value) ? row.value.join('；') : row.value }}</template></el-table-column>
      <el-table-column label="置信度" width="90"><template #default="{ row }">{{ Math.round(row.confidence * 100) }}%</template></el-table-column>
      <el-table-column label="依据/警告" min-width="180"><template #default="{ row }"><span>{{ row.evidence }}</span><small v-if="row.warning" >{{ row.warning }}</small></template></el-table-column>
    </el-table>
    <template #footer><el-button @click="reviewOpen=false">取消</el-button><el-button type="primary" @click="apply">应用所选字段</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone } from '@element-plus/icons-vue'
import { auditAppliedDraft, createFormDraft, transcribeAudio, type AiFormPatch } from '@/services/ai'

const props = defineProps<{ schemaId: 'entrust.v1' | 'sample.v1' | 'report-data.v1'; currentValues: Record<string, unknown> }>()
const emit = defineEmits<{ apply: [AiFormPatch[]] }>()
const recording = ref(false), busy = ref(false), reviewOpen = ref(false), elapsed = ref(0)
const transcript = ref(''), patches = ref<AiFormPatch[]>([]), selected = ref<boolean[]>([])
let recorder: MediaRecorder | null = null, timer = 0, startedAt = 0
let chunks: Blob[] = []

async function start() {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') { ElMessage.error('当前浏览器不支持安全语音录入'); return }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    chunks = []; elapsed.value = 0; startedAt = performance.now()
    recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
    recorder.onstop = () => { stream.getTracks().forEach((track) => track.stop()); void processRecording() }
    recorder.start(500); recording.value = true
    timer = window.setInterval(() => { elapsed.value = Math.ceil((performance.now() - startedAt) / 1000); if (elapsed.value >= 90) stop() }, 500)
  } catch { ElMessage.error('未取得麦克风权限') }
}

function stop() { if (!recording.value) return; recording.value = false; window.clearInterval(timer); recorder?.stop() }

async function processRecording() {
  const duration = Math.max(1, Math.ceil((performance.now() - startedAt) / 1000))
  let blob: Blob | null = new Blob(chunks, { type: recorder?.mimeType || 'audio/webm' })
  chunks = []; recorder = null
  if (blob.size > 8 * 1024 * 1024) { blob = null; ElMessage.error('录音超过 8MB，请缩短后重试'); return }
  busy.value = true
  try {
    transcript.value = await transcribeAudio(blob, duration)
    blob = null
    patches.value = await createFormDraft(props.schemaId, transcript.value, props.currentValues)
    selected.value = patches.value.map((item) => item.confidence >= .65)
    reviewOpen.value = true
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '语音识别失败') }
  finally { blob = null; busy.value = false }
}

async function apply() {
  const accepted = patches.value.filter((_item, index) => selected.value[index])
  emit('apply', accepted)
  reviewOpen.value = false
  try { await auditAppliedDraft(props.schemaId, accepted) } catch { /* 表单应用不因审计提示失败而回滚 */ }
  ElMessage.success(`已应用 ${accepted.length} 个字段，尚未保存`)
  transcript.value = ''; patches.value = []
}

onUnmounted(() => { window.clearInterval(timer); recorder?.stream.getTracks().forEach((track) => track.stop()) })
</script>


