<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import type { ErrorValue } from '../../services/common/errors'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import FilePondUpload from '../common/FilePondUpload.vue'
import AttachmentFileList from '../common/AttachmentFileList.vue'
import type { UploadProgress } from '../common/fileUploadProgress'
import type { EntryDetail, EntryFileSummary, EntryFileKind } from '../../types/testing/dataEntryDetail'
const props = defineProps<{ detail: EntryDetail; layoutId?: string; busy: boolean; readonly: boolean; dirty: boolean; removalError?: ErrorValue; upload: (kind: EntryFileKind, file: File, progress: UploadProgress) => Promise<void> }>()
const emit = defineEmits<{ remove: [EntryFileSummary]; download: [EntryFileSummary]; sort: [string[]] }>()
const files = computed(() => [...props.detail.files.filter(file => file.kind === 'report'), ...props.detail.files.filter(file => file.kind === 'appendix')])
const report = computed(() => files.value.find(file => file.kind === 'report'))
const deleting = ref<EntryFileSummary>(), pendingReport = ref<File>()
const deletingBusy = ref(false)
function remove() {
  if (!deleting.value || props.busy || props.readonly) return
  deletingBusy.value = true
  emit('remove', deleting.value)
  void nextTick(() => { if (!props.busy) deletingBusy.value = false })
}
watch(() => props.busy, busy => { if (!busy) deletingBusy.value = false })
const currentLayoutId = computed(() => props.layoutId ?? props.detail.layoutId)
const currentLayoutLabel = computed(() => props.detail.layouts.find(layout => layout.id === currentLayoutId.value)?.label || '')
const confirmUploadLabel = computed(() => props.dirty ? (report.value ? '保存并替换' : '保存并上传') : (report.value ? '确认替换' : '确认上传'))
let resolveConfirmation: ((confirmed: boolean) => void) | undefined
function confirmUpload(confirmed: boolean) {
  resolveConfirmation?.(confirmed); resolveConfirmation = undefined; pendingReport.value = undefined
}
watch([currentLayoutId, () => props.detail.template.version, () => report.value?.id, () => props.readonly], () => { deleting.value = undefined; confirmUpload(false) })
watch(files, rows => { if (deleting.value && !rows.some(row => row.id === deleting.value!.id)) deleting.value = undefined })
onBeforeUnmount(() => confirmUpload(false))
function beforeReport(file: File) {
  if (props.busy || props.readonly) return Promise.resolve(false)
  confirmUpload(false); deleting.value = undefined; pendingReport.value = file

  return new Promise<boolean>(resolve => { resolveConfirmation = resolve })
}
function move(file: EntryFileSummary, direction: number) {
  const ids = files.value.filter(row => row.kind === 'appendix').map(row => row.id), index = ids.indexOf(file.id), next = index + direction
  if (props.busy || props.readonly || next < 0 || next >= ids.length) return
  ;[ids[index], ids[next]] = [ids[next]!, ids[index]!]; emit('sort', ids)
}
</script>
<template>
  <section class="mb-4" aria-label="报告文件管理" :aria-busy="busy">
    <div v-if="!readonly" class="row g-3 mb-3">
      <div class="col-12 col-xl-6">
        <h5 class="mb-3">完整报告<span class="badge bg-primary-subtle text-primary fw-normal ms-2">DOCX</span></h5>
        <FilePondUpload :key="`${currentLayoutId}-${detail.template.version}`" :upload="(file, progress) => upload('report', file, progress)" :before-upload="beforeReport" :disabled="busy" :label="report ? '替换完整报告' : '上传完整报告'" accept=".docx" :max-size="detail.options.maxFileSize" :hint="`DOCX · 最大 ${detail.options.maxFileSize / 1024 / 1024} MB`" describedby="entry-report-upload-hint" />
        <p id="entry-report-upload-hint" class="form-text mb-0">请使用当前模板填写完整报告，上传前核对首页版式及报告内容。</p>
      </div>
      <div class="col-12 col-xl-6">
        <h5 class="mb-3">附加文件<span class="badge bg-primary-subtle text-primary fw-normal ms-2">DOCX / PDF</span></h5>
        <FilePondUpload :upload="(file, progress) => upload('appendix', file, progress)" :disabled="busy || !!pendingReport" label="添加附加文件" accept=".docx,.pdf" :max-size="detail.options.maxFileSize" multiple :hint="`可多选 · 单个文件最大 ${detail.options.maxFileSize / 1024 / 1024} MB`" />
        <p class="form-text mb-0">支持多次添加，文件将按列表顺序编排。</p>
      </div>
    </div>
    <slot name="upload-status" />
    <AttachmentFileList :files="files" :can-attach="!readonly" :busy="busy" title="已上传文件" empty-label="尚未上传报告文件" @download="emit('download', $event)" @remove="deleting = $event; confirmUpload(false)">
      <template #metadata="{ file }">
        <div class="d-flex flex-wrap align-items-center gap-2 mt-1 small">
          <span class="badge bg-light text-body">{{ file.kind === 'report' ? '完整报告' : `附加文件 ${files.filter(row => row.kind === 'appendix').findIndex(row => row.id === file.id) + 1}` }}</span>
          <span v-if="file.name.toLowerCase() === 'conclusion.docx'" class="badge bg-info-subtle text-info">结论内容文件</span>
          <span :class="detail.reportStatus === 'failed' && detail.job?.fileErrors?.[file.id] ? 'text-danger' : 'text-muted'">{{ detail.reportStatus === 'failed' && detail.job?.fileErrors?.[file.id] || (detail.reportStatus === 'running' ? '处理中' : detail.reportStatus === 'ready' ? '已处理（模拟）' : '已上传，待处理') }}</span>
        </div>
      </template>
      <template #actions="{ file }">
        <template v-if="!readonly && file.kind === 'appendix'">
          <button type="button" class="btn btn-light btn-sm" :aria-label="`上移 ${file.name}`" :disabled="busy || files.filter(row => row.kind === 'appendix')[0]?.id === file.id" @click="move(file, -1)"><i class="ti ti-arrow-up" aria-hidden="true"></i><span class="visually-hidden">上移</span></button>
          <button type="button" class="btn btn-light btn-sm" :aria-label="`下移 ${file.name}`" :disabled="busy || files.filter(row => row.kind === 'appendix').at(-1)?.id === file.id" @click="move(file, 1)"><i class="ti ti-arrow-down" aria-hidden="true"></i><span class="visually-hidden">下移</span></button>
        </template>
      </template>
    </AttachmentFileList>
    <ConfirmationModal v-if="pendingReport && !readonly" title="完整报告上传确认" :busy="busy" @close="confirmUpload(false)">
      <p class="text-break mb-0">请确认“{{ pendingReport.name }}”与当前模板（{{ currentLayoutLabel }}）首页版式一致，否则无法生成正确的报告。<template v-if="report">上传成功后替换原完整报告。</template></p>
      <template #footer><button class="btn btn-light" type="button" :disabled="busy" @click="confirmUpload(false)">取消</button><button class="btn btn-primary" type="button" :disabled="busy" @click="confirmUpload(true)">{{ confirmUploadLabel }}</button></template>
    </ConfirmationModal>
    <ConfirmationModal v-if="deleting" title="删除报告文件" :busy="busy || deletingBusy" @close="deleting = undefined">
      <p class="text-break">确认删除“{{ deleting.name }}”？</p><ErrorNotice :error="removalError" />
      <template #footer><button class="btn btn-light" type="button" :disabled="busy || deletingBusy" @click="deleting = undefined">取消</button><button class="btn btn-danger" type="button" :disabled="busy || deletingBusy || readonly" @click="remove">{{ deletingBusy ? '正在删除…' : '确认删除' }}</button></template>
    </ConfirmationModal>
  </section>
</template>
