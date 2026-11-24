<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import DataTable from '../TemplateDataTable'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import type { TableColumn } from '../../types/common/table'
import type { ReportRow } from '@/services/auth'
import { platformError } from '../apiErrors'
import type { ErrorValue } from '../../services/common/errors'
import { attachmentObjectUrl } from '@/services/attachments'
import { useLiveSearch } from '@/composables/liveSearch'
import { correctionStatus, correctionReturnModes, fetchCorrections, submitCorrection, decideCorrection, type CorrectionType, type CorrectionRequest, type CorrectionAttachment, fetchCorrectionHistory, downloadCorrectionHistory, type CorrectionHistory } from '@/services/reportCorrections'

type Row = ReportRow & { reportKind?: string; mainReportNo?: string }
const props = defineProps<{ rows: Row[]; total?: number; loading: boolean; error: ErrorValue; canRequest: boolean }>()
const emit = defineEmits<{ view: [row: Row]; refresh: []; query: [query: { keyword: string; correctionStatus: string; page: number; pageSize: number }] }>()
const query = ref(''), status = ref(''), page = ref(1), pageSize = ref(12)
const revisions = ref<Record<number, CorrectionHistory>>({})
const history = ref<CorrectionRequest[]>([]), historyLoading = ref(false), historyError = ref<ErrorValue>('')
const selected = ref<Row>(), mode = ref<'view' | CorrectionType>('view')
const reason = ref(''), returnMode = ref('data_only'), internalFile = ref<File>(), receiptFile = ref<File>()
const busy = ref(false), error = ref(''), success = ref(''), notes = ref<Record<number, string>>({})
let alive = true, sequence = 0
onBeforeUnmount(() => { alive = false; sequence++ })
const records = computed(() => history.value.filter(row => row.mainReportNo === selected.value?.reportNo))
const latest = (no: string) => history.value.find(row => row.mainReportNo === no)
const eligible = (row: Row) => (!row.mainReportNo || row.mainReportNo === row.reportNo) && (!row.reportKind || row.reportKind === 'main') && !history.value.some(item => item.mainReportNo === row.reportNo && (item.blocksNewRequest ?? item.status !== 'rejected'))
const filtered = computed(() => props.rows.filter(row => [row.reportNo, row.client, row.project].some(text => text?.toLowerCase().includes(query.value.trim().toLowerCase())) && (!status.value || (latest(row.reportNo)?.status || 'none') === status.value)))
const total = computed(() => props.total ?? filtered.value.length)
const paged = computed(() => props.total === undefined ? filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value) : props.rows)
const keyword = ref('')
const search = useLiveSearch(query, () => { page.value = 1; keyword.value = query.value.trim() })
watch([status, pageSize], () => { page.value = 1 })
watch(total, count => { page.value = Math.max(1, Math.min(page.value, Math.ceil(count / pageSize.value))) })
watch([keyword, status, page, pageSize], () => {
  if (props.total !== undefined) emit('query', { keyword: keyword.value, correctionStatus: status.value, page: page.value, pageSize: pageSize.value })
}, { immediate: true })
const columns: TableColumn<keyof Row>[] = [{ key: 'reportNo', label: '报告编号' }, { key: 'client', label: '委托单位' }, { key: 'project', label: '检测项目' }, { key: 'status', label: '更正申请' }]
async function load() {
  const id = ++sequence; historyLoading.value = true; historyError.value = ''
  try { const result = await fetchCorrections(); if (alive && sequence === id) history.value = result.rows }
  catch (e) { if (alive && sequence === id) historyError.value = platformError(e) }
  finally { if (alive && sequence === id) historyLoading.value = false }
}
onMounted(load)
function open(row: Row, next: 'view' | CorrectionType) {
  if (busy.value) return
  selected.value = row; mode.value = next; reason.value = ''; returnMode.value = 'data_only'
  internalFile.value = undefined; receiptFile.value = undefined; error.value = ''; notes.value = {}
}
function fileChanged(event: Event, kind: 'internal' | 'receipt') {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (kind === 'internal') internalFile.value = file; else receiptFile.value = file
}
const ready = computed(() => reason.value.trim() && internalFile.value && (mode.value !== 'external' || receiptFile.value))
async function submit() {
  const row = selected.value
  if (!row || mode.value === 'view' || busy.value || !ready.value || !internalFile.value) return
  busy.value = true; error.value = ''
  try {
    await submitCorrection(row.reportNo, mode.value, reason.value, returnMode.value, internalFile.value, receiptFile.value)
    if (!alive) return
    mode.value = 'view'; success.value = `${row.reportNo} 更正申请已提交，等待审批。`
    await load(); emit('refresh')
  } catch (e) { if (alive) error.value = e instanceof Error ? e.message : '提交失败' }
  finally { if (alive) busy.value = false }
}
const pendingDecision = ref<{ row: CorrectionRequest; decision: 'approve' | 'reject' }>()
function close() { if (!busy.value) { selected.value = undefined; pendingDecision.value = undefined } }
async function decide() {
  const pending = pendingDecision.value
  if (!pending || busy.value) return
  const note = notes.value[pending.row.id] || ''
  if (pending.decision === 'reject' && !note.trim()) { error.value = '请填写驳回原因'; return }
  busy.value = true; error.value = ''
  try {
    const result = await decideCorrection(pending.row.id, pending.decision, note)
    if (!alive) return
    success.value = result.status === 'approved' ? (result.correctionType === 'internal' ? `审批通过，${result.correctionReportNo} 沿用原编号进入更改，旧版已留存历史。` : `审批通过，已创建 ${result.correctionReportNo}。`) : result.status === 'rejected' ? '申请已驳回。' : '审批已提交。'
    pendingDecision.value = undefined; await load(); emit('refresh')
  } catch (e) { if (alive) { error.value = e instanceof Error ? e.message : '审批失败'; pendingDecision.value = undefined; await load() } }
  finally { if (alive) busy.value = false }
}
async function showHistory(id: number) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { const data = await fetchCorrectionHistory(id); if (alive) revisions.value[id] = data }
  catch (e) { if (alive) error.value = e instanceof Error ? e.message : '历史记录读取失败' }
  finally { if (alive) busy.value = false }
}
async function historyFile(id: number, kind: 'version' | 'signed', fileId: number) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await downloadCorrectionHistory(id, kind, fileId) }
  catch (e) { if (alive) error.value = e instanceof Error ? e.message : '历史文件读取失败' }
  finally { if (alive) busy.value = false }
}
async function download(att: CorrectionAttachment) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const { url } = await attachmentObjectUrl(att, 'change_request', true)
    if (!alive) { URL.revokeObjectURL(url); return }
    const link = document.createElement('a'); link.href = url; link.download = att.name; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { if (alive) error.value = e instanceof Error ? e.message : '附件读取失败' }
  finally { if (alive) busy.value = false }
}
function preview() { const row = selected.value; if (row && !busy.value) { close(); emit('view', row) } }
const formatTime = (time: string) => time ? new Date(`${time}Z`).toLocaleString('zh-CN', { hour12: false }) : ''
</script>

<template>
  <section class="card" aria-label="报告更改申请">
    <div class="card-header d-flex justify-content-between align-items-center"><h5 class="card-title mb-0">报告更改申请</h5><span class="badge bg-primary-subtle text-body">{{ total }}</span></div>
    <form class="card-body border-bottom" @submit.prevent="search.run()">
      <div class="row g-3 align-items-end">
        <div class="col-12 col-md-6"><label for="correction-search" class="form-label">查询内容</label><input id="correction-search" v-model="query" class="form-control" placeholder="报告编号 / 委托单位 / 检测项目" /></div>
        <div class="col-12 col-md-4"><label for="correction-status" class="form-label">申请状态</label><select id="correction-status" v-model="status" class="form-select"><option value="">全部</option><option value="none">未申请</option><option v-for="(label, value) in correctionStatus" :key="value" :value="value">{{ label }}</option></select></div>
        <div class="col-12 col-md-2"><button type="button" class="btn btn-light" :disabled="historyLoading || loading" @click="load(); emit('refresh')">刷新</button></div>
      </div>
      <p class="text-muted small mt-3 mb-0">内部更正需内部签字文件，审批后沿用原报告号，旧版保存在历史记录中；外部更正还需甲方回执，审批后创建 GZ 更正报告。</p>
    </form>
    <div v-if="success" class="alert alert-success m-3" role="status">{{ success }}</div>
    <DataTable label="报告更改申请" :rows="paged" :columns="columns" :row-key="row => row.reportNo" :row-label="row => row.reportNo" :loading="loading || historyLoading" :error="props.error || historyError" :pagination="{ total, page, pageSize, sizes: [12, 20, 50] }" :actions-disabled="busy" @page="page = $event" @size="pageSize = $event" @retry="load(); emit('refresh')">
      <template #cell-reportNo="{ row }"><button type="button" class="btn btn-link p-0" @click="open(row, 'view')">{{ row.reportNo }}</button></template>
      <template #cell-status="{ row }"><span :class="latest(row.reportNo)?.status === 'pending_approval' ? 'badge bg-warning-subtle text-warning' : ''">{{ correctionStatus[latest(row.reportNo)?.status || ''] || '未申请' }}</span></template>
      <template #actions="{ row }">
        <button type="button" role="menuitem" class="dropdown-item" @click="open(row, 'view')"><i class="ti ti-eye me-2" aria-hidden="true"></i>查看</button>
        <button type="button" role="menuitem" class="dropdown-item" :disabled="!canRequest || !eligible(row)" @click="open(row, 'external')"><i class="ti ti-file-export me-2" aria-hidden="true"></i>外部更正</button>
        <button type="button" role="menuitem" class="dropdown-item" :disabled="!canRequest || !eligible(row)" @click="open(row, 'internal')"><i class="ti ti-file-pencil me-2" aria-hidden="true"></i>内部更正</button>
      </template>
    </DataTable>
  </section>
  <BootstrapModal v-if="selected" open :title="`${mode === 'view' ? '查看更正申请' : mode === 'internal' ? '内部更正' : '外部更正'} · ${selected.reportNo}`" size="lg" scrollable :busy="busy" @close="close">
    <FeedbackNotice v-if="error" :message="error" />
    <template v-if="mode !== 'view'">
      <form id="correction-form" @submit.prevent="submit">
        <div class="mb-3"><label for="correction-reason" class="form-label">更正原因 <span class="text-danger">*</span></label><textarea id="correction-reason" v-model="reason" class="form-control" rows="3" required :disabled="busy" /></div>
        <div class="mb-3"><label for="correction-return" class="form-label">审批后的更改环节</label><select id="correction-return" v-model="returnMode" class="form-select" :disabled="busy"><option v-for="(label, value) in correctionReturnModes" :key="value" :value="value">{{ label }}</option></select></div>
        <div class="mb-3"><label for="correction-internal" class="form-label">内部签字文件（偏离许可） <span class="text-danger">*</span></label><input id="correction-internal" type="file" class="form-control" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" required :disabled="busy" @change="fileChanged($event, 'internal')" /></div>
        <div v-if="mode === 'external'" class="mb-3"><label for="correction-receipt" class="form-label">甲方回执／确认文件 <span class="text-danger">*</span></label><input id="correction-receipt" type="file" class="form-control" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" required :disabled="busy" @change="fileChanged($event, 'receipt')" /></div>
        <p class="text-muted small">支持 PDF、PNG、JPG、Word，每份不超过 30 MB。提交后由管理员或获“报告更改审批”权限的人员审批。</p>
      </form>
    </template>
    <template v-else>
      <button type="button" class="btn btn-light mb-3" :disabled="busy" @click="preview">查看报告详情与预览</button>
      <p v-if="historyError" class="text-danger" role="alert">{{ historyError.message }} <button class="btn btn-link" @click="load">重试</button></p>
      <p v-else-if="!records.length" class="text-muted">尚未提交更正申请。</p>
      <article v-for="item in records" :key="item.id" class="border rounded p-3 mb-3">
        <div class="d-flex justify-content-between gap-2"><strong>{{ item.correctionType === 'external' ? '外部更正' : item.correctionType === 'internal' ? '内部更正' : '历史更正申请' }}</strong><span>{{ correctionStatus[item.status] || item.status }}</span></div>
        <p class="text-muted small mt-2">{{ item.applicantName }} · {{ formatTime(item.createdAt) }}</p>
        <p class="text-break">{{ item.reason }}</p><p>更改环节：{{ correctionReturnModes[item.returnMode] }}</p>
        <p v-if="item.applicationAttachment" class="mb-2">{{ item.correctionType === 'legacy' ? '申请扫描件' : '内部签字文件' }}：<button type="button" class="btn btn-link p-0 text-break" :disabled="busy" @click="download(item.applicationAttachment)">{{ item.applicationAttachment.name }}</button></p>
        <p v-if="item.receiptAttachment">甲方回执：<button type="button" class="btn btn-link p-0 text-break" :disabled="busy" @click="download(item.receiptAttachment)">{{ item.receiptAttachment.name }}</button></p>
        <p v-if="item.approverAt">审批人：{{ item.approverName }} · {{ formatTime(item.approverAt) }}<br />{{ item.approverNote || '无补充意见' }}</p>
        <p v-if="item.directorAt">部门主任：{{ item.directorName }} · {{ formatTime(item.directorAt) }} {{ item.directorNote }}</p>
        <p v-if="item.leaderAt">院领导：{{ item.leaderName }} · {{ formatTime(item.leaderAt) }} {{ item.leaderNote }}</p>
        <p v-if="item.correctionReportNo">更正报告：<strong>{{ item.correctionReportNo }}</strong></p>
        <button v-if="item.hasHistory" type="button" class="btn btn-light mb-3" :disabled="busy" @click="showHistory(item.id)">查看更正前历史</button>
        <section v-if="revisions[item.id]" class="border rounded p-3 mb-3" aria-label="更正前历史">
          <p>原报告：{{ revisions[item.id].report.reportNo }} · {{ revisions[item.id].report.status }}<br />委托单位：{{ revisions[item.id].report.client }}</p>
          <p class="text-muted small">以下为本次更正前留存的文件。</p>
          <p v-for="version in revisions[item.id].versions" :key="version.id"><button v-if="version.hasPdf" type="button" class="btn btn-link p-0" :disabled="busy" @click="historyFile(item.id, 'version', version.id)">下载历史 {{ version.versionLabel }} PDF</button></p>
          <p v-if="!revisions[item.id].versions.length && !revisions[item.id].flows.length" class="text-muted">本次更正前尚无正式或签章文件，业务快照已保留。</p>
        </section>
        <div v-if="item.canApprove || item.canApproveDirector || item.canApproveLeader" class="border-top pt-3">
          <label :for="`correction-note-${item.id}`" class="form-label">审批意见（驳回时必填）</label><textarea :id="`correction-note-${item.id}`" v-model="notes[item.id]" class="form-control mb-3" rows="2" :disabled="busy" />
          <div v-if="pendingDecision?.row.id === item.id" class="alert alert-warning">
            <p>{{ pendingDecision.decision === 'approve' ? '确认附件齐全并同意本次更正？' : '确认驳回本次申请？' }}</p>
            <button type="button" class="btn btn-primary me-2" :disabled="busy" @click="decide">{{ busy ? '正在保存…' : '确认' }}</button><button type="button" class="btn btn-light" :disabled="busy" @click="pendingDecision = undefined">取消</button>
          </div>
          <div v-else><button type="button" class="btn btn-primary me-2" :disabled="busy" @click="pendingDecision = { row: item, decision: 'approve' }">审批通过</button><button type="button" class="btn btn-outline-danger" :disabled="busy" @click="pendingDecision = { row: item, decision: 'reject' }">驳回</button></div>
        </div>
      </article>
    </template>
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="close">关闭</button><button v-if="mode !== 'view'" type="submit" form="correction-form" class="btn btn-primary" :disabled="busy || !ready">{{ busy ? '正在提交…' : '提交审批' }}</button></template>
  </BootstrapModal>
</template>
