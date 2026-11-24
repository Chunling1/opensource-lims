<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeading from '../../components/common/PageHeading.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import RegistrationActionModal from '../../components/commissions/RegistrationActionModal.vue'
import RegistrationAttachmentManager from '../../components/commissions/RegistrationAttachmentManager.vue'
import DataQueryReportModal from '../../components/testing/DataQueryReportModal.vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import ReportQueryList from './ReportQueryList.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { RegistrationSample } from '../../types/commissions/registration'
import type { ReportQueryRow, ReportQueryAction } from '../../types/reports/reportQuery'

const route = useRoute(), router = useRouter(), list = ref<InstanceType<typeof ReportQueryList>>()
const busy = ref(false), error = ref<ErrorValue>(''), attachmentId = ref<string>(), voidRecord = ref<RegistrationSample>()
const preview = ref<ReportQueryRow>(), fileError = ref<ErrorValue>(''), fileLoading = ref(false), blob = ref<Blob>(), url = ref('')
let epoch = 0, previewEpoch = 0, controller: AbortController | undefined
function closePreview() { previewEpoch++; controller?.abort(); preview.value = undefined; fileLoading.value = false; fileError.value = ''; if (url.value) URL.revokeObjectURL(url.value); url.value = ''; blob.value = undefined }
function reset() { epoch++; closePreview(); attachmentId.value = undefined; voidRecord.value = undefined; busy.value = false; error.value = '' }
watch(() => [route.fullPath, currentActor.value.id], reset)
onBeforeUnmount(reset)
async function loadFile() {
  const row = preview.value
  if (!row?.releaseId) return
  const token = ++previewEpoch
  controller?.abort(); const abort = controller = new AbortController()
  fileLoading.value = true; fileError.value = ''
  try {
    const file = await registrationDemo.reportQueryFile(row.id, row.releaseId, abort.signal)
    if (token !== previewEpoch) return
    if (url.value) URL.revokeObjectURL(url.value)
    blob.value = file; url.value = URL.createObjectURL(file)
  } catch (issue) { if (token === previewEpoch && !abort.signal.aborted) fileError.value = normalizeError(issue) }
  finally { if (token === previewEpoch) fileLoading.value = false }
}
async function action(row: ReportQueryRow, operation: ReportQueryAction) {
  if (busy.value) return
  error.value = ''
  if (operation === 'data') { await router.push({ path: `/reports/query/${encodeURIComponent(row.id)}`, query: { returnTo: route.fullPath } }); return }
  if (operation === 'attachments') { attachmentId.value = row.id; return }
  if (operation === 'preview') { closePreview(); preview.value = row; await loadFile(); return }
  if (operation === 'void' && row.canVoid) {
    const token = ++epoch
    busy.value = true
    try { const record = await registrationDemo.sample(row.id); if (token === epoch) voidRecord.value = record }
    catch (issue) { if (token === epoch) error.value = normalizeError(issue) }
    finally { if (token === epoch) busy.value = false }
  }
}
</script>
<template>
  <PageHeading title="报告查询" />
  <ErrorNotice v-if="error" :error="error" />
  <ReportQueryList ref="list" :busy="busy" @action="action" @load-start="error = ''" />
  <RegistrationAttachmentManager :id="attachmentId" kind="samples" title="查看附件" readonly @close="attachmentId = undefined" />
  <RegistrationActionModal kind="samples" :record="voidRecord" initial-action="void" report-query @close="voidRecord = undefined" @saved="list?.load()" />
  <DataQueryReportModal v-if="preview && !preview.releaseId" :key="preview.id" :sample="preview" @close="closePreview" />
  <BootstrapModal :loading="fileLoading" :open="!!preview?.releaseId" title="报告预览" size="xl" scrollable compact @close="closePreview">
    <div v-if="fileLoading" class="text-center py-3" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在加载报告…</div>
    <ErrorNotice v-else-if="fileError" :error="fileError" retry @retry="loadFile" />
    <template v-else-if="preview && url">
      <p v-if="preview.form === '电子' && preview.signingStatus !== '签章完成'" class="text-warning">未签章</p>
      <DataEntryPreview :url="url" :blob="blob" type="application/pdf" :title="`${preview.code} · ${preview.name}`" :name="`${preview.reportCode || preview.code}.pdf`" persistent hide-print hide-download />
    </template>
    <template #footer><button class="btn btn-light" @click="closePreview">关闭</button></template>
  </BootstrapModal>
</template>
