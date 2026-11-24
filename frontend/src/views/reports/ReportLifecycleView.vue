<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import ReportDistributionForm from '../../components/reports/ReportDistributionForm.vue'
import ReportPricingForm from '../../components/reports/ReportPricingForm.vue'
import type { ReportPricingDetail, ReportPricingTotals } from '../../types/reports/reportPricing'
import type { ReportDistributionDetail } from '../../types/reports/reportDistribution'
import ReportOutputList from './ReportOutputList.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { reportQueueTitles, reportOperationLabels, type ReportLifecycleRow, type ReportQueue, type ReportOperation } from '../../types/reports/reportLifecycle'
import { canRetry, normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { clientToday } from '../../services/common/date'
import { downloadBlob } from '../../services/reports/reportPdf'

const route = useRoute(), router = useRouter(), queue = computed(() => route.path.split('/').at(-1) as ReportQueue), title = computed(() => reportQueueTitles[queue.value])
const busy = ref(false), error = ref<ErrorValue>(''), dialogError = ref<ErrorValue>(''), attachmentId = ref<string>()
const printList = ref<InstanceType<typeof ReportOutputList>>()
const target = ref<{ row: ReportLifecycleRow; operation: ReportOperation }>()
const form = reactive({ recipient: '', method: '', date: clientToday(), notes: '', trackingNumber: '', mailingAddress: '', reason: '', confirmed: false })
const distributionDetail = ref<ReportDistributionDetail>(), detailLoading = ref(false)
const pricingDetail = ref<ReportPricingDetail>()
const prices = reactive<ReportPricingTotals>({ standardPrice: null, discountPrice: null, actualPrice: null })
const detailMissing = computed(() => detailLoading.value || target.value?.operation === 'distribute' && !distributionDetail.value || target.value?.operation === 'reprice' && !pricingDetail.value)
const progress = ref<Awaited<ReturnType<typeof registrationDemo.reportSigningProgress>>>()
const previewBlob = ref<Blob>(), previewUrl = ref('')
let epoch = 0, dialogEpoch = 0, fileController: AbortController | undefined, detailController: AbortController | undefined
function clearPreview() { if (previewUrl.value) URL.revokeObjectURL(previewUrl.value); previewUrl.value = ''; previewBlob.value = undefined }
function close() { dialogEpoch++; detailController?.abort(); detailLoading.value = false; distributionDetail.value = undefined; pricingDetail.value = undefined; fileController?.abort(); busy.value = false; target.value = undefined; progress.value = undefined; dialogError.value = ''; clearPreview() }
async function load() { error.value = ''; await printList.value?.load() }
watch(() => [route.path, currentActor.value.id], () => {
  epoch++; close(); busy.value = false; attachmentId.value = undefined; error.value = ''
}, { immediate: true })
watch(() => route.fullPath, () => { close(); attachmentId.value = undefined })
onBeforeUnmount(() => { epoch++; close() })
async function open(row: ReportLifecycleRow, operation: ReportOperation) {
  if (!row.actions.find(a => a.id === operation)?.enabled || busy.value) return
  if (operation === 'print-task' || operation === 'print-commission') { await router.push({ path: `/reports/archive/${encodeURIComponent(row.id)}/${operation}`, query: { returnTo: route.fullPath } }); return }
  if (operation === 'attachments') { attachmentId.value = row.id; return }
  close(); target.value = { row, operation }
  Object.assign(form, { recipient: '', method: row.form === '纸质' ? '自取' : '其他', date: clientToday(), notes: '', trackingNumber: '', mailingAddress: (row as { mailingAddress?: string }).mailingAddress || '', reason: '', confirmed: false })
  if (operation === 'distribute' || operation === 'reprice') { await loadActionDetail(); return }
  if (operation === 'progress') { await loadProgress(); return }
  if (!['preview', 'print', 'download', 'print-report'].includes(operation)) return
  await loadFile()
}
async function loadFile() {
  const current = target.value
  if (!current || !['preview', 'print', 'download', 'print-report'].includes(current.operation)) return
  const { row, operation } = current, context = epoch, token = ++dialogEpoch
  fileController?.abort(); clearPreview(); dialogError.value = ''
  busy.value = true; const abort = fileController = new AbortController()
  try {
    const blob = await registrationDemo.reportLifecycleFile(row.id, row.releaseId, operation as 'preview' | 'print' | 'download' | 'print-report', abort.signal)
    if (context !== epoch || token !== dialogEpoch) return
    if (operation === 'download') { downloadBlob(blob, `${row.reportCode || row.code}.pdf`); close() }
    else { previewBlob.value = blob; previewUrl.value = URL.createObjectURL(blob) }
  } catch (e) { if (context === epoch && token === dialogEpoch && !abort.signal.aborted) dialogError.value = normalizeError(e) }
  finally { if (context === epoch && token === dialogEpoch) busy.value = false }
}
async function loadActionDetail() {
  const current = target.value, context = epoch, token = ++dialogEpoch
  if (!current || !['distribute', 'reprice'].includes(current.operation)) return
  detailController?.abort(); const abort = detailController = new AbortController()
  detailLoading.value = true; distributionDetail.value = undefined; pricingDetail.value = undefined; dialogError.value = ''
  try {
    if (current.operation === 'reprice') {
      const detail = await registrationDemo.reportPricingDetail(current.row.id, current.row.version, current.row.releaseId, abort.signal)
      if (context !== epoch || token !== dialogEpoch) return
      pricingDetail.value = detail
      Object.assign(prices, { standardPrice: detail.standardPrice, discountPrice: detail.discountPrice, actualPrice: detail.actualPrice })
    } else {
      const detail = await registrationDemo.reportDistributionDetail(current.row.id, current.row.version, current.row.releaseId, abort.signal)
      if (context !== epoch || token !== dialogEpoch) return
      distributionDetail.value = detail; form.mailingAddress = detail.mailingAddress
    }
  } catch (issue) { if (context === epoch && token === dialogEpoch && !abort.signal.aborted) dialogError.value = normalizeError(issue) }
  finally { if (context === epoch && token === dialogEpoch) detailLoading.value = false }
}
async function loadProgress() {
  const current = target.value, context = epoch, token = dialogEpoch
  if (!current) return
  busy.value = true; dialogError.value = ''
  try { const next = await registrationDemo.reportSigningProgress(current.row.id); if (context === epoch && token === dialogEpoch) progress.value = next }
  catch (e) { if (context === epoch && token === dialogEpoch) dialogError.value = normalizeError(e) }
  finally { if (context === epoch && token === dialogEpoch) busy.value = false }
}
async function submit() {
  const current = target.value, context = epoch
  if (!current || busy.value || detailMissing.value) return
  busy.value = true; dialogError.value = ''
  try {
    await registrationDemo.reportLifecycleAction(current.row.id, { action: current.operation, releaseId: current.row.releaseId, version: current.row.version, ...form, ...(current.operation === 'reprice' ? { prices: { ...prices } } : {}) })
    if (context !== epoch) return
    close(); await load()
  } catch (e) {
    if (context === epoch) {
      const issue = normalizeError(e)
      if (['BUSINESS_RULE', 'FORBIDDEN', 'NOT_FOUND', 'NETWORK'].includes(issue.code)) { close(); await load(); error.value = issue }
      else dialogError.value = issue
    }
  } finally { if (context === epoch) busy.value = false }
}
const isFile = computed(() => target.value && ['preview', 'print', 'download', 'print-report'].includes(target.value.operation))
const isPrintConfirmation = computed(() => target.value && ['complete-print', 'undo-print', 'archive', 'undo-archive'].includes(target.value.operation))
</script>
<template>
  <PageHeading :title="title" />
  <ErrorNotice v-if="error" :error="error" />
  <ReportOutputList :key="queue" ref="printList" :mode="queue" :busy="busy" :paused="!!target || !!attachmentId" @action="open" @load-start="error = ''" />
  <RegistrationAttachmentManager :id="attachmentId" kind="samples" title="查看附件" readonly @close="attachmentId = undefined" />
  <BootstrapModal :loading="detailLoading || busy && (isFile || target?.operation === 'progress')" :open="!!target" :title="target?.operation === 'preview' ? '报告预览' : target?.operation === 'print' ? '报告打印' : target?.operation === 'archive' ? '报告归档' : target?.operation === 'distribute' ? '报告发放' : target ? reportOperationLabels[target.operation] : ''" :size="isFile || target?.operation === 'distribute' || target?.operation === 'reprice' ? 'xl' : isPrintConfirmation ? undefined : 'lg'" :busy="busy && !isFile && target?.operation !== 'progress'" scrollable :compact="!isPrintConfirmation" @close="close">
    <template v-if="target">
      <p v-if="!isFile && target.operation !== 'reprice'" class="text-break"><strong>{{ target.row.code }}</strong> · {{ target.row.name }}<span v-if="queue !== 'signing' && !['distribute', 'complete-print', 'undo-print', 'archive', 'undo-archive'].includes(target.operation)" class="badge bg-light text-body ms-2">{{ target.row.form }}</span></p>
      <ErrorNotice v-if="dialogError" :error="dialogError" :retry="(!!isFile || ['distribute', 'reprice'].includes(target.operation)) && canRetry(dialogError)" :busy="busy || detailLoading" @retry="isFile ? loadFile() : loadActionDetail()" />
      <div v-if="detailLoading || busy && !isPrintConfirmation" class="text-center py-3" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>{{ detailLoading ? target.operation === 'reprice' ? '正在加载计价信息…' : '正在加载发放信息…' : isFile ? '正在加载报告…' : target.operation === 'progress' ? '正在刷新签章进度…' : '正在处理…' }}</div>
      <template v-if="isFile">
        <p v-if="target.row.form === '电子' && target.row.signingStatus !== '签章完成'" class="text-warning">未签章</p>
        <DataEntryPreview v-if="previewUrl" :key="previewUrl" :url="previewUrl" :blob="previewBlob" type="application/pdf" :title="`${target.row.code} · ${target.row.name}`" :name="`${target.row.reportCode}.pdf`" persistent :auto-print="target.operation === 'print' || target.operation === 'print-report'" :hide-print="target.operation !== 'print-report' && (target.row.form !== '纸质' || !target.row.actions.some(a => a.id === 'print' && a.enabled))" :hide-download="target.row.form !== '电子' || !target.row.actions.some(a => a.id === 'download' && a.enabled)" />
      </template>
      <template v-else-if="target.operation === 'progress' && progress">
        <dl class="row"><dt class="col-4">签章状态</dt><dd class="col-8">{{ progress.signing?.status }}</dd><dt class="col-4">电子签名</dt><dd class="col-8">{{ progress.signing?.signature }}</dd><dt class="col-4">电子盖章</dt><dd class="col-8">{{ progress.signing?.seal }}</dd><dt class="col-4">任务编号</dt><dd class="col-8 text-break">{{ progress.signing?.externalId || '等待服务商受理' }}</dd></dl>
        <p v-if="progress.signing?.error" class="text-danger">{{ progress.signing.error }}</p>
        <div class="table-responsive"><table class="table"><thead><tr><th>时间</th><th>进度</th><th>说明</th></tr></thead><tbody><tr v-for="(entry, index) in progress.signing?.events" :key="index"><td>{{ entry.at }}</td><td>{{ entry.status }}</td><td>{{ entry.message }}</td></tr></tbody></table></div>
        <details v-if="progress.signing?.attempts?.length"><summary>历史签章任务</summary><ul class="mt-2"><li v-for="attempt in progress.signing.attempts" :key="attempt.key" class="text-break">第 {{ attempt.attempt }} 次 · {{ attempt.status }} · {{ attempt.externalId || attempt.key }}<span v-if="attempt.error"> · {{ attempt.error }}</span></li></ul></details>
      </template>
      <form v-else-if="!isFile && target.operation !== 'progress'" id="release-action" @submit.prevent="submit">
        <template v-if="target.operation === 'distribute'">
          <fieldset v-if="distributionDetail" :disabled="busy" class="border-0 p-0 m-0"><ReportDistributionForm :detail="distributionDetail" :model-value="form" @update:model-value="Object.assign(form, $event)" /></fieldset>
        </template>
        <template v-else-if="target.operation === 'reprice'">
          <fieldset v-if="pricingDetail" :disabled="busy" class="border-0 p-0 m-0"><ReportPricingForm :detail="pricingDetail" :model-value="prices" @update:model-value="Object.assign(prices, $event)" /></fieldset>
        </template>
        <template v-else-if="target.operation === 'archive'">
          <div class="row g-3 align-items-center"><label for="archive-person" class="col-3 col-form-label">归档人</label><div class="col-9"><input id="archive-person" class="form-control" :value="currentActor.name" readonly /></div><label for="archive-date" class="col-3 col-form-label">归档日期</label><div class="col-9"><input id="archive-date" v-model="form.date" class="form-control" type="date" required /></div></div>
        </template>
        <template v-else-if="target.operation === 'undo-archive'"><p class="mb-0">确认撤销归档？</p></template>
        <template v-else-if="target.operation === 'complete-print'"><label class="form-check"><input v-model="form.confirmed" type="checkbox" class="form-check-input" required /><span class="form-check-label">确认打印完成</span></label></template>
        <template v-else-if="target.operation === 'undo-distribute'"><p class="text-muted">此操作仅更正发放登记，不能追回已交付的纸张或电子文件。</p><label class="form-label" for="release-reason">撤销原因</label><textarea id="release-reason" v-model="form.reason" class="form-control" rows="3" maxlength="1000" required></textarea></template>
        <p v-else>{{ target.operation === 'retry' ? '确认重试此失败的签章任务？' : '确认撤销打印完成？' }}</p>
      </form>
    </template>
    <template #footer><button v-if="target?.operation === 'progress'" class="btn btn-light" :disabled="busy" @click="loadProgress">刷新进度</button><button class="btn btn-light" :disabled="busy && !isFile && target?.operation !== 'progress'" @click="close">{{ isFile || target?.operation === 'progress' ? '关闭' : '取消' }}</button><button v-if="target && !isFile && target.operation !== 'progress'" type="submit" form="release-action" class="btn btn-primary" :disabled="busy || detailMissing">{{ busy ? '正在保存…' : '确认' }}</button></template>
  </BootstrapModal>
</template>
