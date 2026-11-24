<script setup lang="ts">
import ConfirmationModal from '../common/ConfirmationModal.vue'
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import PersonnelAttachments from './PersonnelAttachments.vue'
import AttachmentLeaveConfirmation from '../common/AttachmentLeaveConfirmation.vue'
import { useAttachmentDraft } from '../common/useAttachmentDraft'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import { canApplyDailyRequests } from '../../types/quality/dailyRequests'
import { registrationDepartments } from '../../types/commissions/commissionForm'
import { clientToday } from '../../services/common/date'
import { dailyRequestItems, type DailyRequestDraft, type DailyRequestRow, type DailyRequestMode, type DailyApprovalOperation } from '../../types/quality/dailyRequests'
const props = defineProps<{ mode: DailyRequestMode; record?: DailyRequestRow; approvalPage?: boolean }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const record = ref(props.record), draft = reactive<DailyRequestDraft>({ reason: '', items: [], other: '', copies: 1, files: [] })
const loading = ref(false), loaded = ref(props.mode === 'new'), busy = ref(false), intent = ref(''), withdrawalReason = ref(''), error = ref<ErrorValue>('')
const uploads = useAttachmentDraft('daily-request', () => props.record?.id, () => draft.files, () => busy.value, { value: () => draft, ready: () => ['new', 'edit'].includes(props.mode) && loaded.value && !loading.value })
const working = computed(() => busy.value || uploads.active.value)
const decision = ref(false), result = ref('审批通过'), opinion = ref('')
const approvalAction = computed(() => ['approve', 'revoke', 'void'].includes(props.mode))
const compact = computed(() => ['withdraw', 'delete', 'revoke', 'void'].includes(props.mode))
const approvalAllowed = computed(() => props.mode === 'approve' ? record.value?.canApprove : props.mode === 'revoke' ? record.value?.canRevoke : record.value?.canVoid)
const history = computed(() => record.value?.events.filter(event => ['审批通过', '不通过', '撤回审批', '作废申请'].includes(event.action)) || [])
const canEdit = computed(() => canApplyDailyRequests(currentActor.value) && (props.mode === 'new' || !!record.value?.canEdit))
const readonly = computed(() => props.mode === 'view' || approvalAction.value || !canEdit.value || busy.value)
const blocked = computed(() => working.value || loading.value || !loaded.value || uploads.failed.value)
const title = computed(() => ({ new: '新增申请', edit: '修改申请', view: '查看申请', withdraw: '撤销申请', delete: '删除申请', approve: '审批申请', revoke: '撤回审批', void: '作废申请' })[props.mode])
const department = computed(() => record.value?.department || registrationDepartments.find(item => item.id === currentActor.value.departmentId)?.name || '无')
const applicant = computed(() => record.value?.applicant || currentActor.value.name)
const appliedDate = computed(() => record.value ? new Date(record.value.appliedAt).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }) : clientToday())
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.record || working.value) return
  controller?.abort(); const request = controller = new AbortController()
  loading.value = true; loaded.value = false; error.value = ''; decision.value = false; opinion.value = ''; result.value = '审批通过'
  try {
    const result = await (props.approvalPage ? registrationDemo.dailyApprovalDetail : registrationDemo.dailyRequestDetail)(props.record.id, request.signal)
    if (alive && !request.signal.aborted) { record.value = result; Object.assign(draft, { reason: result.reason, items: [...result.items], other: result.other, copies: result.copies, files: result.files }); loaded.value = true }
  } catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
async function save(operation: 'save' | 'submit' | 'withdraw' | 'delete') {
  if (blocked.value || props.mode === 'view' || approvalAction.value) return
  if (operation === 'withdraw' ? !record.value?.canWithdraw : operation === 'delete' ? !record.value?.canDelete : !canEdit.value) return
  busy.value = true; intent.value = operation; error.value = ''
  try {
    if (operation === 'withdraw' || operation === 'delete') await registrationDemo.dailyRequestAction({ id: record.value!.id, version: record.value!.version, withdrawalReason: withdrawalReason.value }, operation)
    else await registrationDemo.saveDailyRequest(uploads.payload({ ...draft, copies: String(draft.copies ?? '').trim() === '' ? null : Number(draft.copies), intent: operation, ...(props.mode === 'edit' ? { id: record.value!.id, version: record.value!.version } : {}) }))
    if (alive) { uploads.commit(); emit('saved') }
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) { busy.value = false; intent.value = '' } }
}
async function close() { if (!busy.value && (await uploads.allowLeave())) emit('close') }
async function approve() {
  if (blocked.value || !approvalAction.value || !approvalAllowed.value || !record.value) return
  busy.value = true; error.value = ''
  try {
    await registrationDemo.dailyApprovalAction({ id: record.value.id, version: record.value.version, result: result.value, opinion: opinion.value }, props.mode as DailyApprovalOperation)
    if (alive) emit('saved')
  } catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
if (props.mode !== 'new') void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal open :title="title" :size="compact ? undefined : 'lg'" scrollable fullscreen-mobile :busy="busy" guard-close :loading="loading" @close="close">
    <template v-if="loaded">
      <form v-if="mode === 'revoke' || mode === 'void'" id="daily-approval-form" novalidate @submit.prevent="approve">
        <p class="text-break">申请单号：{{ record?.code }}</p>
        <p v-if="mode === 'revoke'">撤回后恢复为待审批，可重新审批。历史审批记录将保留。</p>
        <p v-else-if="mode === 'void'">作废后不能修改或重新审批，申请及历史记录将保留。</p>
        <label for="daily-approval-opinion" class="form-label">{{ mode === 'revoke' ? '撤回原因' : mode === 'void' ? '作废原因' : '审批意见' }}</label>
        <textarea id="daily-approval-opinion" data-validation-key="opinion" v-model="opinion" class="form-control" rows="4" maxlength="1000" :disabled="blocked" />
      </form>
      <template v-else-if="mode === 'delete'"><p class="text-break">确认删除申请“{{ record?.code }}”？</p><p class="text-muted mb-0">办理事由：{{ record?.reason || '未填写' }}</p></template>
      <template v-else-if="mode === 'withdraw'"><p>撤销申请“{{ record?.code }}”后恢复为申请中，可编辑并重新提交。</p><label for="daily-withdrawal" class="form-label">撤回原因<span class="text-danger ms-1" aria-hidden="true">*</span></label><textarea id="daily-withdrawal" data-validation-key="withdrawalReason" v-model="withdrawalReason" class="form-control" rows="2" maxlength="1000" :disabled="blocked" /></template>
      <form v-else id="daily-request-form" novalidate @submit.prevent="save('save')">
        <div v-if="record" class="d-flex flex-wrap justify-content-between gap-2 mb-3"><span class="text-muted">申请单号：{{ record.code }}</span><span class="badge bg-info-subtle text-info">{{ record.status }}</span></div>
        <div class="mb-3"><label for="daily-reason" class="form-label">办理事由</label><textarea id="daily-reason" data-validation-key="reason" v-model="draft.reason" class="form-control" rows="2" maxlength="2000" :disabled="readonly" /></div>
        <fieldset :disabled="readonly" class="mb-3" data-validation-key="items"><legend class="form-label fs-5">办理事项（可多选）</legend><div class="row g-2" data-field-control>
          <div v-for="(item, index) in dailyRequestItems" :key="item" class="col-12 col-sm-6"><div class="form-check"><input :id="`daily-item-${index}`" v-model="draft.items" type="checkbox" class="form-check-input" :value="item" /><label :for="`daily-item-${index}`" class="form-check-label">{{ item }}</label></div></div>
        </div></fieldset>
        <div class="mb-3"><label for="daily-other" class="form-label">其他办理事项</label><input id="daily-other" data-validation-key="other" v-model="draft.other" class="form-control" maxlength="500" :disabled="readonly || !draft.items.includes('其他')" /></div>
        <div class="row g-3 mb-3"><div class="col-12 col-sm-6"><label for="daily-copies" class="form-label">份数</label><input id="daily-copies" data-validation-key="copies" v-model.number="draft.copies" type="number" min="1" max="99999" step="1" class="form-control" :disabled="readonly" /></div></div>
        <div class="mb-3"><h6>附件</h6><PersonnelAttachments label="申请附件" :files="draft.files" :readonly="readonly" /></div>
        <div class="row g-3">
          <div class="col-12 col-sm-4"><label for="daily-department" class="form-label">申请部门</label><input id="daily-department" :value="department" class="form-control" disabled /></div>
          <div class="col-12 col-sm-4"><label for="daily-applicant" class="form-label">申请人</label><input id="daily-applicant" :value="applicant" class="form-control" disabled /></div>
          <div class="col-12 col-sm-4"><label for="daily-date" class="form-label">申请日期</label><input id="daily-date" :value="appliedDate" class="form-control" disabled /></div>
        </div>
        <div v-if="record?.withdrawalReason" class="mt-3"><label for="daily-previous-withdrawal" class="form-label">撤回原因</label><textarea id="daily-previous-withdrawal" :value="record.withdrawalReason" class="form-control" rows="2" disabled /></div>
        <div v-if="record?.approval" class="mt-3 border-top pt-3"><h6>审批信息</h6><p>审批结果：{{ record.approval.result }} · 审批人：{{ record.approval.actor }} · 审批日期：{{ new Date(record.approval.at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }}</p><label for="daily-current-opinion" class="form-label">审批意见</label><textarea id="daily-current-opinion" class="form-control" :value="record.approval.opinion" rows="2" disabled /></div>
        <div v-if="record?.voidReason" class="mt-3"><label for="daily-void-reason" class="form-label">作废原因</label><textarea id="daily-void-reason" class="form-control" :value="record.voidReason" rows="2" disabled /></div>
        <div v-if="history.length" class="mt-3 border-top pt-3"><h6>审批记录</h6><div class="table-responsive"><table class="table table-bordered align-middle mb-0" aria-label="审批记录"><thead><tr><th scope="col">操作</th><th scope="col">操作人</th><th scope="col">日期</th><th scope="col">意见或原因</th></tr></thead><tbody><tr v-for="(event, index) in history" :key="index"><td class="text-nowrap">{{ event.action }}</td><td class="text-nowrap">{{ event.actor }}</td><td class="text-nowrap">{{ new Date(event.at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) }}</td><td class="text-break">{{ event.reason || '—' }}</td></tr></tbody></table></div></div>
      </form>
    </template>
    <ErrorNotice v-if="!decision" :error="error" :retry="!loaded" :busy="working || loading" :class="{ 'mt-3': loaded && error }" @retry="load" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ mode === 'view' || mode === 'approve' ? '返回' : '取消' }}</button>
      <template v-if="approvalAction">
        <button v-if="mode === 'approve'" type="button" class="btn btn-primary" :disabled="blocked || !approvalAllowed" @click="error = ''; decision = true">审批</button>
        <button v-else type="submit" form="daily-approval-form" :class="mode === 'void' ? 'btn btn-danger' : 'btn btn-primary'" :disabled="blocked || !approvalAllowed">{{ busy ? '正在处理…' : mode === 'revoke' ? '确认撤回' : mode === 'void' ? '确认作废' : '确认审批' }}</button>
      </template>
      <button v-if="mode === 'delete' || mode === 'withdraw'" type="button" :class="mode === 'delete' ? 'btn btn-danger' : 'btn btn-primary'" :disabled="blocked || (mode === 'delete' ? !record?.canDelete : !record?.canWithdraw)" @click="save(mode)">{{ busy ? '正在处理…' : mode === 'delete' ? '确认删除' : '确认撤销' }}</button>
      <template v-else-if="mode !== 'view' && !approvalAction"><button type="submit" form="daily-request-form" class="btn btn-light" :disabled="blocked || !canEdit">{{ intent === 'save' ? '正在保存…' : '保存' }}</button><button type="button" class="btn btn-primary" :disabled="blocked || !canEdit" @click="save('submit')">{{ intent === 'submit' ? '正在提交…' : '提交' }}</button></template>
    </template>
  </BootstrapModal>
  <ConfirmationModal v-if="decision" title="审批意见" :busy="busy" @close="decision = false; error = ''">
    <form id="daily-approval-decision" novalidate @submit.prevent="approve">
      <p class="text-break">申请单号：{{ record?.code }}</p>
        <fieldset :disabled="blocked" class="mb-3"><legend class="form-label fs-5">审批状态</legend><div class="d-flex flex-wrap gap-3">
          <div v-for="option in [{ value: '审批通过', label: '审批通过' }, { value: '不通过', label: '审批不通过' }]" :key="option.value" class="form-check"><input :id="`daily-result-${option.value}`" class="form-check-input" type="radio" name="daily-approval-result" data-validation-key="result" v-model="result" :value="option.value" /><label :for="`daily-result-${option.value}`" class="form-check-label">{{ option.label }}</label></div>
        </div></fieldset>

      <label for="daily-decision-opinion" class="form-label">审批意见</label>
      <textarea id="daily-decision-opinion" data-validation-key="opinion" v-model="opinion" class="form-control" rows="4" maxlength="1000" :disabled="blocked" />
      <div class="form-text">审批通过时可不填写意见；审批不通过时须填写意见。</div>
    </form>
    <ErrorNotice :error="error" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="decision = false; error = ''">取消</button><button type="submit" form="daily-approval-decision" class="btn btn-primary" :disabled="blocked || !approvalAllowed">{{ busy ? '正在处理…' : '确认审批' }}</button></template>
  </ConfirmationModal>
  <AttachmentLeaveConfirmation />
</template>
