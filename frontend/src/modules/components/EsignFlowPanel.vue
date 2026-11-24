<template>
  <LoadState :loading="loading" has-data />
  <SchemaForm :schema="signingSchema" :model="props">
    <template #flow>
      <SigningFlowSteps v-if="flow" :steps="stepItems" :busy="loading || working" />
      <FeedbackNotice v-if="isCancelledPersonalFlow" message="此签署流程已撤销，以下为历史记录。重新建立签发任务后，所有人员需重新签字；原报告及封面保持不变。" />
      <FeedbackNotice v-else-if="!loading && !loadError && !flow" message="尚未建立电子签发任务。请确认报告已有批准版本，且流程人员已绑定 e签宝身份。" />
      <FeedbackNotice v-if="loadError" :message="loadError" tone="danger" />
      <FeedbackNotice v-if="flow?.status === 'cancelling'" message="正在核实旧流程撤销结果。确认停止后将建立全员待签的新任务；管理员或签发人员可点击“继续核实撤销”。" />
      <FeedbackNotice v-if="canSupplementOrganizationSeal" :message="canConfirm ? '人员签字已完成，请核对当前报告后进行签章确认；确认后系统盖章。' : '人员签字已完成，等待获授权的签章人确认。'" />
      <p v-if="flow?.organizationSeal?.confirmation" class="text-muted small">签章确认人：{{ flow.organizationSeal.confirmation.userName }} · {{ flow.organizationSeal.confirmation.confirmedAt }}</p>
      <FeedbackNotice v-if="flow?.errorMessage" :message="flow.errorMessage" tone="danger" />
      <FeedbackNotice v-if="flow?.status === 'binding_required'" message="签署人员需要先绑定 e签宝身份。请到我的签署或人员登记完成绑定后刷新。" />
    </template>
    <template #actions>      <el-button :loading="loading" @click="refreshStatus">刷新状态</el-button>
      <el-button v-if="!readOnly && !loading && !loadError && !flow" type="primary" :loading="working" @click="prepare">建立签发任务</el-button>
      <el-button v-else-if="!readOnly && isCancelledPersonalFlow" type="primary" :loading="working" @click="prepare">重新建立签发任务</el-button>
      <template v-else-if="flow && ['ready', 'failed'].includes(flow.status) && (isOrganizationSealFlow ? canConfirm : !readOnly)">
        <el-button :loading="working" @click="openPositioning">人工拖章校准</el-button>
        <el-button type="primary" :loading="working" @click="dispatch">
          {{ isOrganizationSealFlow ? '重试已确认盖章' : '发起人员电子签署' }}
        </el-button>
      </template>
      <el-button
        v-if="canConfirm && canSupplementOrganizationSeal"
        type="warning"
        :loading="working"
        @click="supplementOrganizationSeal"
      >签章确认</el-button>
      <el-button v-if="!readOnly && flow?.canCancel" type="danger" :loading="working" :disabled="loading" @click="cancelSigning">
        {{ flow.status === 'cancelling' ? '继续核实撤销' : '撤销签署流程' }}
      </el-button>
    </template>
  </SchemaForm>
</template>

<script setup lang="ts">
// BEGIN TEMPLATE SIGNING IMPORTS
import SigningFlowSteps from "../../platformUi/reports/SigningFlowSteps.vue"
import SchemaForm from '../../components/forms/SchemaForm.vue'
import LoadState from '../../components/common/LoadState.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import type {FormSchema} from '../../types/forms'
// END TEMPLATE SIGNING IMPORTS

import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelEsignFlow,
  dispatchEsignFlow,
  fetchReportEsignFlow,
  refreshEsignFlow,
  getEsignPositioningUrl,
  prepareReportEsignFlow,
  startOrganizationSeal,
  type EsignFlow,
} from '@/services/esign'

const props = defineProps<{ reportNo: string; readOnly?: boolean; allowSealConfirmation?: boolean }>()
const flow = ref<EsignFlow | null>(null)
const loading = ref(false)
const loadError = ref('')
const working = ref(false)

const canConfirm = computed(() => props.allowSealConfirmation !== false && flow.value?.canConfirmSeal === true)
const isUnified = computed(() => flow.value?.signingMode === 'single_flow_confirmation_v1')
const confirmationHash = computed(() => isUnified.value ? flow.value?.sourceSha256 : flow.value?.signedSha256)
const isOrganizationSealFlow = computed(() => flow.value?.flowKind === 'organization_seal')
const isCancelledPersonalFlow = computed(() => flow.value?.status === 'cancelled' && !isOrganizationSealFlow.value)
const organizationSealIncluded = computed(() => Boolean(flow.value?.organizationSeal?.included))
const organizationSealCompleted = computed(() => ['completed', 'verified'].includes(flow.value?.organizationSeal?.status || ''))
const canSupplementOrganizationSeal = computed(() => Boolean(
  flow.value && (isUnified.value
    ? flow.value.status === 'signing' && flow.value.organizationSeal?.status === 'awaiting_confirmation'
    : ['completed', 'verified'].includes(flow.value.status) && !organizationSealIncluded.value),
))
const stepItems = computed(() => {
  const signers = (flow.value?.signers || []).map((signer) => ({
    key: `person-${signer.id}`,
    title: signer.roleName,
    description: `${signer.userName || signer.legalName} · ${isCancelledPersonalFlow.value ? (signer.status === 'signed' ? '已签（历史记录）' : '未签（流程已撤销）') : signerStatus(signer.status)}`,
    complete: !isCancelledPersonalFlow.value && signer.status === 'signed',
  }))
  signers.push({key: 'seal-confirmation', title: '签章确认',
    description: isCancelledPersonalFlow.value ? '流程已撤销' : flow.value?.organizationSeal?.confirmation?.userName || (organizationSealIncluded.value ? '历史盖章流程' : canSupplementOrganizationSeal.value ? '待确认' : '等待人员签字'),
    complete: !!flow.value?.organizationSeal?.confirmation || organizationSealIncluded.value})
  if (flow.value) {
    signers.push({
      key: 'organization-seal',
      title: '组织盖章',
      description: isCancelledPersonalFlow.value ? '流程已撤销' : `${flow.value?.organizationSeal?.sealMode === 'assigned' ? '指定专用章' : '默认组织章'} · ${sealStatus(flow.value?.organizationSeal?.status || '')}`,
      complete: organizationSealCompleted.value,
    })
  }
  return signers
})
const signedCount = computed(() => stepItems.value.filter((row) => row.complete).length)
const flowTag = computed(() => {
  const status = flow.value?.status ?? 'unprepared'
  const map: Record<string, { label: string; type: 'success' | 'warning' | 'danger' | 'info' }> = {
    unprepared: { label: '待建立', type: 'info' }, binding_required: { label: '待绑定人员', type: 'warning' },
    ready: { label: '待发起', type: 'warning' }, dispatching: { label: '发起中', type: 'warning' },
    signing: { label: canSupplementOrganizationSeal.value ? '待签章确认' : isOrganizationSealFlow.value || flow.value?.organizationSeal?.confirmation ? '盖章处理中' : '签署中', type: 'warning' }, completed: { label: organizationSealIncluded.value ? '已签章' : '待签章确认', type: 'success' },
    verified: { label: '已验签', type: 'success' }, failed: { label: '发起失败', type: 'danger' },
    cancelled: { label: '已撤销', type: 'danger' }, cancelling: { label: '撤销待核实', type: 'warning' }, expired: { label: '已过期', type: 'danger' },
    rejected: { label: '已拒签', type: 'danger' },
  }
  return map[status] ?? { label: status, type: 'info' as const }
})
const organizationSealTag = computed(() => {
  const seal = flow.value?.organizationSeal
  const mode = seal?.sealMode === 'assigned' ? '专用章' : '默认组织章'
  const label = organizationSealCompleted.value
    ? `${mode}及骑缝章已完成`
    : `${mode}及骑缝章${sealStatus(seal?.status || '')}`
  return { label, type: organizationSealCompleted.value ? 'success' as const : 'warning' as const }
})
const positioningTag = computed(() => {
  const positioning = flow.value?.positioning
  if (positioning?.status === 'resolved') {
    return {
      label: positioning.mode === 'manual' ? '人工拖章坐标已确认' : 'e签宝关键字定位完成',
      type: 'success' as const,
    }
  }
  if (positioning?.status === 'awaiting_callback') {
    return { label: '等待拖章坐标回传', type: 'warning' as const }
  }
  return { label: '签字位置待确认', type: 'danger' as const }
})

function signerStatus(status: string) {
  return ({ pending: '待签', signed: '已签', binding_required: '待绑定', failed: '失败' } as Record<string, string>)[status] ?? status
}
function sealStatus(status: string) {
  return ({ awaiting_personal_signatures: '等待人员签字', awaiting_confirmation: '待确认', appending: '盖章请求待核实，请刷新状态', finishing: '签章完成，正在完结', ready: '待盖', signing: '盖章中', completed: '已盖', verified: '已验签', failed: '失败' } as Record<string, string>)[status] ?? status
}
let loadSequence = 0
async function reload() {
  const sequence = ++loadSequence
  if (!props.reportNo) return
  loading.value = true
  loadError.value = ''
  try { const result = await fetchReportEsignFlow(props.reportNo); if (sequence === loadSequence) flow.value = result }
  catch (error) { if (sequence === loadSequence) { loadError.value = error instanceof Error ? error.message : '电子签发状态加载失败，请刷新重试'; ElMessage.error(loadError.value) } }
  finally { if (sequence === loadSequence) loading.value = false }
}
async function refreshStatus() {
  const target = flow.value
  const reportNo = props.reportNo
  if (loading.value || working.value) return
  loading.value = true
  try {
    if (target?.signingMode === 'single_flow_confirmation_v1' && target.status === 'signing') await refreshEsignFlow(target.id)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上游状态核实失败，请稍后重试')
  } finally {
    loading.value = false
    if (props.reportNo === reportNo) await reload()
  }
}
async function cancelSigning() {
  if (props.readOnly || !flow.value?.canCancel || working.value || loading.value) return
  const target = { reportNo: props.reportNo, id: flow.value.id, sequence: loadSequence }
  working.value = true
  try {
    const { value } = await ElMessageBox.prompt(
      `撤销报告 ${target.reportNo} 的当前签署轮次，保留历史签字及文件，并在本页建立全员待签的新任务。原审核批准保持不变。请填写撤销原因（1至50字）。`,
      '撤销未盖章签署流程',
      { confirmButtonText: '撤销并重置待签', cancelButtonText: '取消', inputPattern: /\S/, inputValidator: (v: string) => Boolean(v?.trim() && v.trim().length <= 50), inputErrorMessage: '请填写1至50字的撤销原因', type: 'warning' },
    )
    if (props.reportNo !== target.reportNo || flow.value?.id !== target.id || loadSequence !== target.sequence) return
    const result = await cancelEsignFlow(target.id, value.trim())
    if (props.reportNo !== target.reportNo || loadSequence !== target.sequence) return
    flow.value = result
    ElMessage.success('旧流程已撤销，所有人员需重新签字；请核对后发起人员电子签署')
    await reload()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close' && props.reportNo === target.reportNo && loadSequence === target.sequence) {
      ElMessage.error(error instanceof Error ? error.message : '撤销未完成，请刷新核实')
      await reload()
    }
  } finally { working.value = false }
}
async function prepare() {
  if (props.readOnly || working.value || loading.value || loadError.value || (flow.value && !isCancelledPersonalFlow.value)) return
  const reportNo = props.reportNo
  const sequence = loadSequence
  working.value = true
  try {
    const result = await prepareReportEsignFlow(reportNo)
    if (props.reportNo !== reportNo || loadSequence !== sequence) return
    flow.value = result
    ElMessage.success('电子签发任务已建立，请核对后发起人员电子签署')
  }
  catch (error) { if (props.reportNo === reportNo && loadSequence === sequence) ElMessage.error(error instanceof Error ? error.message : '建立任务失败') }
  finally { working.value = false }
}
async function dispatch() {
  if (working.value || (isOrganizationSealFlow.value ? !canConfirm.value : props.readOnly)) return
  if (!flow.value) return
  working.value = true
  try {
    flow.value = await dispatchEsignFlow(flow.value.id)
    await reload()
    ElMessage.success(isOrganizationSealFlow.value ? '已发起组织自动盖章' : '已发起电子签署，未发送逐份短信')
  }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : '发起签署失败') }
  finally { working.value = false }
}
async function supplementOrganizationSeal() {
  if (!canConfirm.value || !canSupplementOrganizationSeal.value || working.value || !flow.value) return
  const target = {reportNo: props.reportNo, id: flow.value.id, sha256: confirmationHash.value || ''}
  working.value = true
  try {
    await ElMessageBox.confirm(
      `确认报告 ${target.reportNo} 的人员签字已完成、文件内容无误，并同意盖章。确认后系统将在已签文件上加盖组织章和骑缝章，人员无需重签。`,
      '签章确认',
      { confirmButtonText: '确认并盖章', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    working.value = false
    return
  }
  try {
    if (props.reportNo !== target.reportNo || flow.value?.id !== target.id || confirmationHash.value !== target.sha256) return
    flow.value = await startOrganizationSeal(target.reportNo, target.id, target.sha256)
    await reload()
    ElMessage.success('签章确认已记录，盖章流程已发起')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '发起组织补章失败')
  } finally {
    working.value = false
  }
}
async function openPositioning() {
  if (props.readOnly) return
  if (!flow.value) return
  const positioningWindow = window.open('about:blank', '_blank')
  if (positioningWindow) positioningWindow.opener = null
  working.value = true
  try {
    const result = await getEsignPositioningUrl(flow.value.id)
    if (positioningWindow) positioningWindow.location.href = result.url
    else window.open(result.url, '_blank', 'noopener,noreferrer')
    ElMessage.success('已打开e签宝人工拖章页面，提交后请刷新状态')
    await reload()
  } catch (error) {
    positioningWindow?.close()
    ElMessage.error(error instanceof Error ? error.message : '获取拖章页面失败')
  } finally { working.value = false }
}
watch(() => props.reportNo, () => { flow.value = null; void reload() }, { immediate: true })

// BEGIN TEMPLATE SIGNING ADAPTER
const signingSchema=computed<FormSchema<typeof props>>(()=>({sections:[
{id:'signing-flow',title:'电子签发 · '+flowTag.value.label,slot:'flow',fields:[]},
{id:'signing-actions',title:'签发操作',slot:'actions',fields:[]}
]}))
// END TEMPLATE SIGNING ADAPTER
</script>
