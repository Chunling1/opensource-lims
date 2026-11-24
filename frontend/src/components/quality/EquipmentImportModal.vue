<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import SaveProgress from '../common/SaveProgress.vue'
import { useSaveProgress } from '../common/useSaveProgress'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
const emit = defineEmits<{ close: []; saved: [count: number] }>()
const file = ref<File>(), busy = ref(false), error = ref<ErrorValue>('')
const progress = useSaveProgress()
let alive = true
onBeforeUnmount(() => { alive = false; progress.finish() })
function choose(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0]; error.value = '' }
async function submit() {
  if (!file.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    if (!/\.csv$/i.test(file.value.name) || file.value.size > 2 * 1024 * 1024) throw new AppError('VALIDATION', '请选择不超过 2 MB 的 CSV 文件。')
    const csv = await file.value.text()
    if (!alive) return
    const result = await registrationDemo.importEquipment(csv, progress.start())
    if (alive) emit('saved', result.count)
  } catch (issue) { if (alive) { const failure = normalizeError(issue); error.value = failure.code === 'VALIDATION' ? new AppError('VALIDATION', failure.message, { fieldErrors: { file: failure.message } }) : failure } }
  finally { if (alive) { busy.value = false; progress.finish() } }
}
</script>
<template>
  <BootstrapModal open title="导入设备" :busy="busy" @close="!busy && emit('close')">
    <form id="equipment-import" @submit.prevent="submit">
      <label for="equipment-import-file" class="form-label">导入文件</label><input id="equipment-import-file" data-validation-key="file" type="file" accept=".csv,text/csv" class="form-control" :disabled="busy" required @change="choose" />
      <div class="form-text">请使用 CSV 模板，最多 1000 条，不超过 2 MB。</div>
    </form>
    <ErrorNotice :error="error" />
    <template #footer><SaveProgress :active="progress.active.value" :percent="progress.percent.value" /><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button class="btn btn-primary" form="equipment-import" :disabled="busy || !file">{{ busy ? '正在导入…' : '导入' }}</button></template>
  </BootstrapModal>
</template>
