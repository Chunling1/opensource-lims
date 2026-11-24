<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
const emit = defineEmits<{ close: []; saved: [count: number] }>()
const file = ref<File>(), busy = ref(false), error = ref<ErrorValue>('')
let alive = true
onBeforeUnmount(() => { alive = false })
function choose(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0]; error.value = '' }
async function submit() {
  if (!file.value || busy.value) return
  busy.value = true; error.value = ''
  try {
    if (!/\.csv$/i.test(file.value.name) || file.value.size > 2 * 1024 * 1024) throw new AppError('VALIDATION', '请选择不超过 2 MB 的 CSV 文件。')
    const csv = await file.value.text()
    if (!alive) return
    const result = await registrationDemo.importMaintenanceCosts(csv)
    if (alive) emit('saved', result.count)
  } catch (issue) { if (alive) { const failure = normalizeError(issue); error.value = failure.code === 'VALIDATION' ? new AppError('VALIDATION', failure.message, { fieldErrors: { file: failure.message } }) : failure } }
  finally { if (alive) busy.value = false }
}
</script>
<template>
  <BootstrapModal open title="导入设备维护费用" :busy="busy" @close="emit('close')">
    <form id="maintenance-cost-import" @submit.prevent="submit"><label for="maintenance-cost-file" class="form-label">导入文件</label><input id="maintenance-cost-file" data-validation-key="file" type="file" accept=".csv,text/csv" class="form-control" :disabled="busy" required @change="choose" /><div class="form-text">使用下载的 CSV 模板填写，日期格式为 YYYY-MM-DD，最多 1000 条、2 MB。总金额可留空自动计算；部门填写部门名称。全部记录校验通过后一次导入。</div></form>
    <ErrorNotice :error="error" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button class="btn btn-primary" form="maintenance-cost-import" :disabled="busy || !file">{{ busy ? '正在导入…' : '导入' }}</button></template>
  </BootstrapModal>
</template>
