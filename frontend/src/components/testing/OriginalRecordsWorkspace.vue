<script setup lang="ts">
import FeedbackNotice from '../common/FeedbackNotice.vue'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import FilePondUpload from '../common/FilePondUpload.vue'
import AttachmentFileList from '../common/AttachmentFileList.vue'
import type { UploadProgress } from '../common/fileUploadProgress'
import type { TransferProgress } from '../../services/common/uploadRequest'
import { useFileUpload } from '../common/useFileUpload'
import ErrorNotice from '../common/ErrorNotice.vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import TablePagination from '../common/table/TablePagination.vue'
import TemplateToast from '../common/TemplateToast.vue'
import DataEntryPreview from './DataEntryPreview.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { downloadBlob } from '../../services/reports/reportPdf'
import type { OriginalContext, OriginalRecordView, ElnPage } from '../../types/testing/originalRecords'

const props = defineProps<{ sampleId: string; active: boolean; readonly: boolean; previewOnly?: boolean; autoPrint?: boolean; compact?: boolean; previewTitle?: string }>()
const emit = defineEmits<{ busy: [boolean] }>()
const data = ref<OriginalContext>(), loading = ref(false), busy = ref(false), stale = ref(false), error = ref<ErrorValue>('')
const uploadStatus = useFileUpload()
const elnLoading = ref(false)
const writing = computed(() => busy.value || uploadStatus.active.value)
const working = computed(() => writing.value || loading.value || elnLoading.value)
const toast = ref<InstanceType<typeof TemplateToast>>(), success = ref('')
const managerOpen = ref(false), managerView = ref<'list' | 'eln' | 'preview'>('list')
const checked = ref<string[]>([]), renaming = ref(false), renameRecordId = ref(''), newName = ref('')
const elnRows = ref<ElnPage>(), elnChecked = ref<string[]>([]), elnQuery = ref({ sampleCode: '', name: '', page: 1, pageSize: 10 })
const selected = ref(''), selectedFile = ref(''), previewUrl = ref(''), previewBlob = ref<Blob>(), previewBusy = ref(false), previewError = ref<ErrorValue>('')
const filePreviewUrl = ref(''), filePreviewBlob = ref<Blob>(), filePreviewBusy = ref(false), filePreviewError = ref<ErrorValue>('')
const previewKey = ref(''), mutationLabel = ref(''), pendingUpdate = ref<OriginalRecordView>()
const pending = ref<OriginalRecordView[]>([])
const record = computed(() => data.value?.records.find(row => row.id === selected.value))
const file = computed(() => record.value?.files.find(file => file.id === selectedFile.value))
const rows = computed(() => data.value?.records || [])
const listFiles = computed(() => rows.value.map(row => ({ ...row, type: 'application/pdf', size: row.files.reduce((total, file) => total + file.size, 0) })))
const canWrite = computed(() => !props.readonly && !props.previewOnly && !working.value && !stale.value)
let epoch = 0, previewSequence = 0, elnSequence = 0, filePreviewSequence = 0
watch(working, value => emit('busy', value))
function notify(message: string) { success.value = message; void nextTick(() => toast.value?.show()) }
function clearPreview() { previewSequence++; if (previewUrl.value) URL.revokeObjectURL(previewUrl.value); previewUrl.value = ''; previewBlob.value = undefined; previewError.value = ''; previewBusy.value = false }
function closePreview() { clearPreview(); previewKey.value = '' }
function clearFilePreview() { filePreviewSequence++; if (filePreviewUrl.value) URL.revokeObjectURL(filePreviewUrl.value); filePreviewUrl.value = ''; filePreviewBlob.value = undefined; filePreviewError.value = ''; filePreviewBusy.value = false }
function backToList() { elnSequence++; elnLoading.value = false; clearFilePreview(); selected.value = ''; selectedFile.value = ''; managerView.value = 'list' }
function syncPreview() {
  checked.value = checked.value.filter(id => rows.value.some(row => row.id === id))
  if (uploadStatus.active.value || stale.value) return
  if (!rows.value.length) { closePreview(); return }
  const key = `all:${data.value?.version}`
  if (key !== previewKey.value) void preview()
}
function openManager() { if (props.previewOnly) return; managerView.value = 'list'; pending.value = []; pendingUpdate.value = undefined; renaming.value = false; managerOpen.value = true }
function closeManager() { if (writing.value) return; elnSequence++; elnLoading.value = false; managerOpen.value = false; clearFilePreview(); pending.value = []; pendingUpdate.value = undefined; renaming.value = false }
function viewRecord(row: OriginalRecordView) { if (!working.value) { managerView.value = 'preview'; void previewFile(row) } }
async function load() {
  const token = epoch; loading.value = true
  try { const result = await registrationDemo.originals(props.sampleId); if (token !== epoch) return; data.value = result; stale.value = false; error.value = ''; syncPreview() }
  catch (issue) { if (token === epoch) { error.value = normalizeError(issue); stale.value = true } }
  finally { if (token === epoch) loading.value = false }
}
async function mutate(action: string, payload: Record<string, unknown>, progress?: TransferProgress) {
  if (!data.value || busy.value || stale.value || props.readonly) return false
  const token = epoch; busy.value = true; error.value = ''; mutationLabel.value = ['link', 'update-eln'].includes(action) ? '正在导入 ELN PDF，请稍候…' : ''
  try {
    const result = await registrationDemo.originalAction(props.sampleId, action, { ...payload, version: data.value.version, sampleVersion: data.value.sampleVersion, requestId: crypto.randomUUID() }, progress)
    if (token !== epoch) return false
    data.value = result; selected.value = ''; selectedFile.value = ''; syncPreview(); return true
  } catch (issue) {
    if (token !== epoch) return false
    error.value = normalizeError(issue)
    if (['NETWORK', 'UNAVAILABLE', 'FORBIDDEN', 'NOT_FOUND'].includes(error.value.code)) { stale.value = true; clearPreview(); previewKey.value = '' }
    return false
  } finally { if (token === epoch) { busy.value = false; mutationLabel.value = '' } }
}
async function upload(file: File, progress: UploadProgress) {
  if (!data.value || !canWrite.value || !data.value.capabilities.canUpload) throw new Error('当前不可上传，请刷新核对后重试。')
  if (!file.name.toLowerCase().endsWith('.pdf') || !file.size || file.size > data.value.maxFileSize) throw new Error(`仅支持不超过 ${data.value.maxFileSize / 1024 / 1024} MB 的非空 PDF 文件。`)
  const token = epoch
  uploadStatus.start(file.name); error.value = ''; pending.value = []; pendingUpdate.value = undefined; renaming.value = false
  try {
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error('无法读取文件。'))
      reader.onabort = () => reject(new Error('文件读取已取消。'))
      reader.onprogress = event => progress('reading', event.loaded, event.lengthComputable ? event.total : undefined)
      reader.readAsDataURL(file)
    })
    if (token !== epoch) throw new Error('页面已切换，请重新上传。')
    uploadStatus.processing(); progress('uploading')
    const ok = await mutate('upload', { file: { name: file.name, size: file.size, dataUrl } },
      (loaded, total) => progress(loaded === total ? 'saving' : 'uploading', loaded === total ? undefined : loaded, loaded === total ? undefined : total))
    if (!ok) {
      const failure = error.value as ErrorValue
      // Ordinary upload failures are shown in the upload row; uncertain writes need an explicit refresh.
      if (!stale.value) error.value = ''
      throw new Error(failure ? failure.message : '上传失败，请重试。')
    }
  } finally { if (token === epoch) { uploadStatus.finish(); syncPreview() } }
}
async function preview() {
  clearPreview()
  previewKey.value = `all:${data.value?.version}`
  const token = previewSequence; previewBusy.value = true
  try {
    const result = await registrationDemo.entryDownload(props.sampleId, `original-records/preview?version=${data.value?.version}`)
    if (token === previewSequence) { previewBlob.value = result; previewUrl.value = URL.createObjectURL(result) }
  } catch (issue) { if (token === previewSequence) previewError.value = normalizeError(issue) }
  finally { if (token === previewSequence) previewBusy.value = false }
}
async function previewFile(row: OriginalRecordView, fileId = row.files[0]?.id || '') {
  clearFilePreview(); selected.value = row.id; selectedFile.value = fileId
  const token = filePreviewSequence; filePreviewBusy.value = true
  try {
    if (!fileId) throw new AppError('BUSINESS_RULE', '此 ELN 记录尚未导入 PDF，请在文件列表中点击“更新”。')
    const result = await registrationDemo.entryDownload(props.sampleId, `original-records/${encodeURIComponent(row.id)}/files/${encodeURIComponent(fileId)}`)
    if (token === filePreviewSequence) { filePreviewBlob.value = result; filePreviewUrl.value = URL.createObjectURL(result) }
  } catch (issue) { if (token === filePreviewSequence) filePreviewError.value = normalizeError(issue) }
  finally { if (token === filePreviewSequence) filePreviewBusy.value = false }
}
async function download(row: OriginalRecordView, fileId: string, name: string) { try { downloadBlob(await registrationDemo.entryDownload(props.sampleId, `original-records/${encodeURIComponent(row.id)}/files/${encodeURIComponent(fileId)}`), name) } catch (issue) { error.value = normalizeError(issue) } }
function remove(records: OriginalRecordView[]) { pending.value = [...records]; pendingUpdate.value = undefined; renaming.value = false; error.value = '' }
const deletingBusy = ref(false)
async function confirmRemove() {
  if (!canWrite.value || deletingBusy.value) return
  const ids = pending.value.map(row => row.id); deletingBusy.value = true
  try { if (ids.length && await mutate('remove', { ids })) { pending.value = []; notify('所选记录已移除。') } }
  finally { deletingBusy.value = false }
}
function rename(row: OriginalRecordView) { if (!canWrite.value || !data.value?.capabilities.canUpload || row.source === 'eln') return; renameRecordId.value = row.id; newName.value = row.name; renaming.value = true; pending.value = []; pendingUpdate.value = undefined; void nextTick(() => document.getElementById('original-record-name')?.focus()) }
async function saveName() {
  const row = rows.value.find(item => item.id === renameRecordId.value)
  if (!canWrite.value || !data.value?.capabilities.canUpload || !row || row.source === 'eln' || !newName.value.trim()) return
  if (await mutate('rename', { recordId: row.id, name: newName.value })) { renaming.value = false; notify('记录名称已修改。') }
}
async function move(row: OriginalRecordView, direction: number) {
  const index = rows.value.findIndex(item => item.id === row.id), target = index + direction
  if (!canWrite.value || !data.value?.capabilities.canUpload || index < 0 || target < 0 || target >= rows.value.length) return
  const ids = rows.value.map(row => row.id); [ids[index], ids[target]] = [ids[target]!, ids[index]!]
  if (await mutate('reorder', { ids })) notify('记录顺序已更新。')
}
async function queryEln(page = 1, pageSize = elnQuery.value.pageSize) {
  if (elnLoading.value) return
  elnQuery.value.page = page; elnQuery.value.pageSize = pageSize
  const token = ++elnSequence; elnLoading.value = true; error.value = ''
  try { const result = await registrationDemo.originalElnQuery(props.sampleId, { ...elnQuery.value }); if (token === elnSequence) { elnRows.value = result; elnChecked.value = [] } }
  catch (issue) { if (token === elnSequence) { error.value = normalizeError(issue); elnRows.value = undefined } }
  finally { if (token === elnSequence) elnLoading.value = false }
}
function openEln() { managerView.value = 'eln'; elnRows.value = undefined; elnQuery.value = { sampleCode: data.value?.sampleCode || '', name: '', page: 1, pageSize: 10 }; void queryEln() }
async function refreshManager() { await load(); if (!stale.value && managerView.value === 'eln') await queryEln() }
async function linkEln() { if (await mutate('link', { ids: elnChecked.value })) { managerView.value = 'list'; elnChecked.value = []; notify('外部原始记录已关联。') } }
async function updateEln() { if (pendingUpdate.value && await mutate('update-eln', { recordId: pendingUpdate.value.id })) { pendingUpdate.value = undefined; notify('ELN PDF 已更新。') } }
async function retryPreview() { previewKey.value = ''; await load() }
watch(() => props.active, value => { if (value) void load() }, { immediate: true })
watch(() => props.sampleId, () => { epoch++; elnSequence++; elnLoading.value = false; managerOpen.value = false; closePreview(); backToList(); data.value = undefined; busy.value = false; uploadStatus.finish(); stale.value = false; if (props.active) void load() })
onBeforeUnmount(() => { epoch++; elnSequence++; clearPreview(); clearFilePreview(); emit('busy', false) })
</script>
<template>
  <section :class="compact ? 'mb-0' : 'mb-4'" aria-label="原始记录工作区" :aria-busy="working">
    <template v-if="!managerOpen"><ErrorNotice :error="error" /><button v-if="error" type="button" class="btn btn-light mb-3" :disabled="working" @click="load">刷新原始记录</button></template>
    <DataEntryPreview persistent :auto-print="autoPrint" :url="previewUrl" :blob="previewBlob" :name="data?.sampleCode + '-原始记录.pdf'" type="application/pdf" :title="previewTitle || '原始记录预览'">
      <template v-if="!previewOnly" #actions><button type="button" class="btn btn-primary" :disabled="working" @click="openManager">上传记录</button></template>
      <template #before>
        <p v-if="previewBusy" class="text-muted" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>正在更新预览…</p>
        <ErrorNotice :error="previewError" />
        <button v-if="previewError" type="button" class="btn btn-light mb-3" :disabled="working || previewBusy" @click="retryPreview">重试预览</button>
      </template>
      <template #empty><div class="text-center text-muted py-5"><i class="ti ti-file-type-pdf display-4 d-block mb-3" aria-hidden="true"></i>{{ loading || previewBusy ? '请稍候' : previewError ? '原始记录预览尚不可用' : previewOnly ? '暂无可预览原始记录' : '暂无原始记录，请上传记录' }}</div></template>
    </DataEntryPreview>
    <BootstrapModal :loading="loading || elnLoading || managerView === 'preview' && filePreviewBusy" v-if="!previewOnly" :open="managerOpen" :title="managerView === 'eln' ? '关联 ELN' : managerView === 'preview' ? '查看原始记录' : '上传原始记录'" size="xl" scrollable fullscreen-mobile :compact-height="managerView === 'list' ? 'large' : false" :fill-height="managerView !== 'list'" :busy="writing" @close="closeManager">
      <template v-if="managerView === 'eln' || managerView === 'preview'" #toolbar>
        <form v-if="managerView === 'eln'" class="row g-2 align-items-end pb-3" @submit.prevent="queryEln()">
          <div class="col-12 col-md-5"><label for="original-eln-sample" class="form-label">样品编号</label><input id="original-eln-sample" v-model="elnQuery.sampleCode" class="form-control" :disabled="working" /></div>
          <div class="col-12 col-md-5"><label for="original-eln-name" class="form-label">记录名称</label><input id="original-eln-name" v-model="elnQuery.name" class="form-control" :disabled="working" /></div>
          <div class="col-auto"><button class="btn btn-primary" :disabled="working">查询</button></div>
        </form>
        <select v-if="managerView === 'preview' && record && record.files.length > 1" class="form-select mb-3" :value="selectedFile" aria-label="原始记录文件" @change="previewFile(record, ($event.target as HTMLSelectElement).value)"><option v-for="item in record.files" :key="item.id" :value="item.id">{{ item.name }}</option></select>
      </template>
      <ErrorNotice :error="error" /><button v-if="error" type="button" class="btn btn-light mb-3" :disabled="working" @click="refreshManager">刷新原始记录</button>
      <p v-if="busy && mutationLabel" class="text-muted" role="status"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>{{ mutationLabel }}</p><FeedbackNotice v-if="uploadStatus.leaveAttempted.value" message="文件正在上传，请等待完成后再离开。" />
      <template v-if="managerView === 'list'">
        <FilePondUpload v-if="managerOpen && !readonly && data?.capabilities.canUpload" :key="sampleId" :upload="upload" :disabled="!canWrite" label="上传 PDF 原始记录" accept=".pdf" :max-size="data.maxFileSize" multiple :hint="`PDF · 可多选 · 单个文件最大 ${data.maxFileSize / 1024 / 1024} MB`" />
        <form v-if="renaming" class="row g-2 align-items-end mb-3" @submit.prevent="saveName">
          <div class="col-12 col-sm-8"><label for="original-record-name" class="form-label">记录名称</label><input id="original-record-name" v-model="newName" class="form-control" maxlength="255" required :disabled="working" /></div>
          <div class="col-auto d-flex gap-2"><button class="btn btn-primary" :disabled="!canWrite || !newName.trim()">保存名称</button><button type="button" class="btn btn-light" :disabled="working" @click="renaming = false">取消重命名</button></div>
        </form>
        <AttachmentFileList :files="listFiles" :can-attach="!readonly && !stale" :can-remove="row => row.capabilities.canDelete" :busy="working" :selected-ids="checked" fill-empty title="原始记录列表" empty-label="暂无原始记录" @remove="remove([$event])">
          <template #header-leading><input id="original-select-all" type="checkbox" class="form-check-input m-0 flex-shrink-0" aria-label="全选原始记录" :checked="!!rows.length && checked.length === rows.length" :indeterminate="checked.length > 0 && checked.length < rows.length" :disabled="working || !rows.length" @change="checked = ($event.target as HTMLInputElement).checked ? rows.map(row => row.id) : []" /></template>
          <template #title><label for="original-select-all" class="mb-0">原始记录列表</label></template>
          <template v-if="!readonly" #toolbar><button type="button" class="btn btn-sm btn-primary-lt text-nowrap" :disabled="!canWrite || !data?.capabilities.canLink" @click="openEln"><i class="ti ti-link me-1" aria-hidden="true"></i>关联 ELN</button></template>
          <template #leading="{ file: row }"><input v-model="checked" type="checkbox" class="form-check-input flex-shrink-0" :value="row.id" :aria-label="'选择 ' + row.name" :disabled="working" /></template>
          <template #name="{ file: row }"><div class="d-flex align-items-center gap-2"><button type="button" class="btn btn-link text-body fw-medium p-0 text-start text-truncate" :title="row.name" :disabled="working" @click="viewRecord(row)">{{ row.name }}</button><span class="badge bg-light text-body flex-shrink-0">{{ rows.findIndex(item => item.id === row.id) + 1 }} · {{ row.source === 'eln' ? '外部 ELN' : '上传文件' }}</span></div></template>
          <template #details="{ file: row }"><span v-if="row.source === 'eln'"><span class="mx-2" aria-hidden="true">·</span>{{ row.status }} · 版本 {{ row.eln?.version || '—' }}</span></template>
          <template #download="{ file: row }"><button v-for="item in row.files" :key="item.id" type="button" class="btn btn-sm btn-primary-lt text-break" :disabled="working" :aria-label="`下载原始记录 ${item.name}`" @click="download(row, item.id, item.name)"><i class="ti ti-download me-1" aria-hidden="true"></i>{{ row.files.length > 1 ? `下载 ${item.name}` : '下载' }}</button></template>
          <template #actions="{ file: row }">
            <button v-if="row.source !== 'eln' && !readonly" type="button" class="btn btn-light btn-sm" :aria-label="`重命名 ${row.name}`" :disabled="!canWrite || !data?.capabilities.canUpload" @click="rename(row)"><i class="ti ti-edit me-1" aria-hidden="true"></i>重命名</button>
            <button v-if="row.source === 'eln' && !readonly" type="button" class="btn btn-light btn-sm" :disabled="!canWrite || !row.capabilities.canLink" @click="pendingUpdate = row; pending = []; renaming = false"><i class="ti ti-refresh me-1" aria-hidden="true"></i>更新</button>
            <template v-if="!readonly">
              <button type="button" class="btn btn-light btn-sm" :aria-label="`上移 ${row.name}`" :title="`上移 ${row.name}`" :disabled="!canWrite || !data?.capabilities.canUpload || rows[0]?.id === row.id" @click="move(row, -1)"><i class="ti ti-arrow-up" aria-hidden="true"></i><span class="visually-hidden">上移</span></button>
              <button type="button" class="btn btn-light btn-sm" :aria-label="`下移 ${row.name}`" :title="`下移 ${row.name}`" :disabled="!canWrite || !data?.capabilities.canUpload || rows.at(-1)?.id === row.id" @click="move(row, 1)"><i class="ti ti-arrow-down" aria-hidden="true"></i><span class="visually-hidden">下移</span></button>
            </template>
          </template>
        </AttachmentFileList>
      </template>
      <template v-else-if="managerView === 'eln'">
        <p class="small text-muted">当前为模拟 ELN 数据，真实外部系统尚未接入。</p>
        <div class="table-responsive"><table class="table table-hover align-middle mb-0" aria-label="ELN 记录列表"><thead class="table-light text-nowrap"><tr><th>选择</th><th>记录名称</th><th>样品编号</th><th>状态</th><th>版本</th><th>更新时间</th></tr></thead><tbody><tr v-for="item in elnRows?.items" :key="item.systemId + ':' + item.id"><td><input v-model="elnChecked" type="checkbox" class="form-check-input" :value="item.systemId + ':' + item.id" :aria-label="'关联 ' + item.name" :disabled="working || item.linked || readonly" /><span v-if="item.linked" class="badge bg-light text-body ms-2">已关联</span></td><td class="text-break">{{ item.name }}</td><td class="text-nowrap">{{ item.sampleCode }}</td><td>{{ item.status }}</td><td>{{ item.version }}</td><td class="text-nowrap">{{ item.updatedAt }}</td></tr><tr v-if="!elnRows?.items.length"><td colspan="6" class="text-center text-muted py-4">{{ elnLoading ? '正在查询…' : error ? '查询失败，请重试' : '暂无可关联记录' }}</td></tr></tbody></table></div>
      </template>
      <template v-else-if="managerView === 'preview'">

        <DataEntryPreview id="original-file-preview" persistent :url="filePreviewUrl" :blob="filePreviewBlob" :name="file?.name || record?.name || ''" :type="file?.type || 'application/pdf'" title="单份原始记录预览">
          <template #before>
            <p class="text-break">{{ record?.name }}</p>
            <p v-if="record?.eln" class="small text-muted">ELN 导入版本：{{ record.eln.version || '未导入' }}<template v-if="record.eln.importedAt"> · 导入时间：{{ new Date(record.eln.importedAt).toLocaleString() }}</template></p>
            <ErrorNotice :error="filePreviewError" />
            <button v-if="filePreviewError && record" class="btn btn-light mb-3" type="button" @click="previewFile(record, selectedFile)">重试预览</button>
          </template>
          <template #empty><p class="text-center text-muted py-5" role="status">{{ filePreviewBusy ? '正在加载预览…' : '暂无可预览文件' }}</p></template>
        </DataEntryPreview>
      </template>
      <template #pagination><TablePagination v-if="managerView === 'eln' && elnRows" label="ELN 记录" :total="elnRows.total" :page="elnRows.page" :page-size="elnRows.pageSize" :sizes="[10, 20, 50]" @page="queryEln($event)" @size="queryEln(1, $event)" /></template>
      <template #footer><template v-if="managerView === 'eln'"><button type="button" class="btn btn-light" :disabled="writing" @click="backToList(); error = ''">返回文件列表</button><button type="button" class="btn btn-primary" :disabled="!canWrite || !elnChecked.length" @click="linkEln">确认关联</button></template><button v-else-if="managerView === 'preview'" type="button" class="btn btn-light" @click="backToList">返回文件列表</button><button v-else type="button" class="btn btn-light" :disabled="writing" @click="closeManager">返回</button></template>
    </BootstrapModal>
    <ConfirmationModal v-if="managerOpen && pendingUpdate" title="更新外部原始记录" :busy="working" @close="pendingUpdate = undefined">
      <p class="text-break">重新导入“{{ pendingUpdate.name }}”的最新 PDF，并更新合并预览？更新失败会保留已有文件。</p>
      <ErrorNotice :error="error" /><button v-if="stale" type="button" class="btn btn-light" :disabled="working" @click="refreshManager">刷新原始记录</button>
      <template #footer><button type="button" class="btn btn-light" :disabled="working" @click="pendingUpdate = undefined">取消</button><button type="button" class="btn btn-primary" :disabled="!canWrite" @click="updateEln">{{ busy ? '正在更新…' : '确认更新' }}</button></template>
    </ConfirmationModal>
    <ConfirmationModal v-if="managerOpen && pending.length" title="删除原始记录" :busy="working || deletingBusy" @close="pending = []">
      <p class="text-break">确认删除所选 {{ pending.length }} 条记录？<template v-if="pending.some(row => row.source === 'eln')">外部记录仅解除关联，不会删除 ELN 中的内容。</template></p>
      <ErrorNotice :error="error" /><button v-if="stale" type="button" class="btn btn-light" :disabled="working" @click="refreshManager">刷新原始记录</button>
      <template #footer><button type="button" class="btn btn-light" :disabled="working || deletingBusy" @click="pending = []">取消</button><button type="button" class="btn btn-danger" :disabled="!canWrite || deletingBusy" @click="confirmRemove">{{ deletingBusy ? '正在删除…' : '确认删除' }}</button></template>
    </ConfirmationModal>
    <TemplateToast ref="toast" :message="success" tone="success" />
  </section>
</template>



