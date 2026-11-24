<template>
  <el-dialog :model-value="modelValue" title="CNAS / CMA 全量预检" width="min(980px, 94vw)" :close-on-click-modal="false" :before-close="beforeClose" @update:model-value="$emit('update:modelValue', $event)">
    <el-alert type="warning" :closable="false" title="这里仅预检、暂存新授权依据，不替换现行标准，也不直接开放双资质报告。" />
    <div >
      <input aria-label="选择授权对照工作簿" type="file" accept=".xlsx" :disabled="busy" @change="chooseFile" />
      <el-button type="primary" :loading="busy && action === 'preview'" :disabled="busy || !file" @click="preview">整表预检</el-button>
    </div>
    <el-alert v-if="error" type="error" :closable="false" :title="error" />
    <template v-if="result">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="文件">{{ file?.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ result.batchId ? `已暂存批次 #${result.batchId}（未启用）` : '预检通过，未写入数据库' }}</el-descriptions-item>
        <el-descriptions-item label="CNAS 原行">{{ result.cnasItemCount }}</el-descriptions-item>
        <el-descriptions-item label="CMA 未确认对应">{{ result.unconfirmedCmaItemCount }}</el-descriptions-item>
        <el-descriptions-item label="对应但有差异">{{ result.pairedWithDifferences }}</el-descriptions-item>
        <el-descriptions-item label="一致候选，仍须审核">{{ result.consistentCandidateCount }}</el-descriptions-item>
        <el-descriptions-item label="源文件 SHA256" :span="2"><span >{{ result.sourceSha256 }}</span></el-descriptions-item>
      </el-descriptions>
      <el-table :data="countRows" border max-height="280" >
        <el-table-column prop="sheet" label="工作表" />
        <el-table-column prop="count" label="实际数据行数" width="160" />
      </el-table>
      <div >
        <strong>启用前仍须完成</strong>
        <ul><li v-for="reason in result.activationBlockers" :key="reason">{{ reason }}</li></ul>
      </div>
      <el-checkbox v-model="confirmed" :disabled="busy || !!result.batchId">我确认只暂存证据，不替换现行标准和报告权限</el-checkbox>
    </template>
    <template #footer>
      <el-button :disabled="busy" @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :loading="busy && action === 'stage'" :disabled="!canStage" @click="stage">确认暂存（不启用）</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { previewScopeEvidence, stageScopeEvidence, type ScopePreview } from '@/services/scopeEvidence'

defineProps<{ modelValue: boolean }>()
defineEmits<{ (e: 'update:modelValue', value: boolean): void }>()
const file = ref<File>()
const result = ref<ScopePreview>()
const error = ref('')
const busy = ref(false)
const action = ref('')
const confirmed = ref(false)
const countRows = computed(() => Object.entries(result.value?.counts ?? {}).map(([sheet, count]) => ({ sheet, count })))
const canStage = computed(() => !busy.value && !!file.value && !!result.value?.readyForStaging && !result.value?.batchId && confirmed.value)
function beforeClose(done: () => void) { if (!busy.value) done() }
function chooseFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0]
  result.value = undefined
  confirmed.value = false
  error.value = ''
}
async function preview() {
  if (busy.value || !file.value) return
  result.value = undefined
  confirmed.value = false
  error.value = ''
  if (!file.value.name.toLowerCase().endsWith('.xlsx') || file.value.size > 12 * 1024 * 1024) {
    error.value = '请选择不超过 12 MiB 的原格式 XLSX 文件'
    return
  }
  busy.value = true
  action.value = 'preview'
  try { result.value = await previewScopeEvidence(file.value) }
  catch (e) { error.value = e instanceof Error ? e.message : '预检失败' }
  finally { busy.value = false }
}
async function stage() {
  if (!canStage.value || !file.value || !result.value) return
  busy.value = true
  action.value = 'stage'
  error.value = ''
  try { result.value = await stageScopeEvidence(file.value, result.value.manifestSha256) }
  catch (e) { error.value = e instanceof Error ? e.message : '暂存失败' }
  finally { busy.value = false }
}
</script>


