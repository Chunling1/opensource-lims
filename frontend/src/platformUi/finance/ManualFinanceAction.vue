<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {profile} from '../../services/platform/auth'
import {canOperateErp} from './erpPermissions'
import {AppError,type ErrorValue} from '../../services/common/errors'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import FinanceOperationSummary from './FinanceOperationSummary.vue'
import FeedbackNotice from '../../components/common/FeedbackNotice.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import LoadState from '../../components/common/LoadState.vue'
import {manualStatus,retryFinanceStep,runManualFinance,type FinanceMode,type FinanceState} from './manualFinance'
const props=defineProps<{reportNo:string;mode:FinanceMode}>()
const authorized=computed(()=>canOperateErp(profile.value?.erpPermissions,props.mode))
const label=computed(()=>props.mode==='send'?'外部ERP回传':'外部ERP签发回传')
const open=ref(false),busy=ref(false),message=ref(''),error=ref<ErrorValue>(''),state=ref<FinanceState>(),target=ref('')
const receiptTime=(time:string)=>new Date(time).toLocaleString('zh-CN',{hour12:false})
let epoch=0
watch(()=>[props.reportNo,props.mode],()=>{epoch++;open.value=false;state.value=undefined;busy.value=false})
async function show(){
  if(!authorized.value||!props.reportNo||busy.value)return
  target.value=props.reportNo;open.value=true;state.value=undefined;message.value='';error.value='';busy.value=true
  const current=++epoch
  try{const result=await manualStatus(target.value);if(current===epoch)state.value=result[props.mode]}
  catch(e){if(current===epoch)error.value=new AppError('BUSINESS_RULE',e instanceof Error?e.message:'状态读取失败，请重新打开')}
  finally{if(current===epoch)busy.value=false}
}
async function submit(){
  if(!authorized.value||busy.value||!state.value?.allowed||state.value.done)return
  busy.value=true;error.value='';message.value='正在核对合同及客户资料，请稍候…';const current=epoch
  try{
    const result=state.value.retry ? await retryFinanceStep(state.value.retry) : await runManualFinance(target.value,props.mode,result=>{if(current===epoch)message.value=result.message})
    if(current!==epoch)return
    message.value=result.message

    state.value={done:result.done,allowed:!result.done&&(!result.blocked||result.retryable),message:'',retry:result.retry,receipts:result.receipts,
      refreshOnly:result.blocked&&!result.retryable&&!result.done}
  }catch(e){if(current===epoch){state.value={allowed:false,done:false,message:'请刷新查看最新发送结果。',refreshOnly:true};error.value=new AppError('BUSINESS_RULE',e instanceof Error?e.message:'请求未完成')}}
  finally{if(current===epoch)busy.value=false}
}
</script>
<template>
  <button v-if="authorized" type="button" class="btn btn-light text-nowrap" :disabled="!reportNo || busy" :title="!reportNo ? '请勾选一份报告' : undefined" @click="show">{{ label }}</button>
  <BootstrapModal :open="open" :title="label" :busy="busy" @close="!busy && (open=false)">
    <FinanceOperationSummary :text="target + ' · ' + (mode==='send' ? '合同批准后可首次回传；已签发、已发放或已归档但尚未回传成功的仍可回传。收到外部ERP明确成功回执后禁止重复回传，后续请在签发完成后使用“外部ERP签发回传”执行反审核流程。' : '签发完成后，虚拟框架合同依次反审核、更新订单、登记合同并回传报告；收到反审核接口确认后继续，外部ERP实际审核状态以单据为准。标准／框架合同按原流程仅回传报告。') + '每步收到明确成功回执后继续，已成功步骤不重复发送；外部ERP审核、执行和浪潮下发状态需另行核对。'" />
    <LoadState :loading="busy" has-data />
    <FeedbackNotice v-if="state?.message || message" role="status" aria-live="polite" :message="state?.message || message" />
    <FinanceOperationSummary v-for="receipt in state?.receipts" :key="receipt.operation"
      :text="receipt.operation + '成功 · ' + receiptTime(receipt.receivedAt)" />
    <ErrorNotice :error="error" />
    <template #footer>
      <button type="button" class="btn btn-light" :disabled="busy" @click="open=false">关闭</button>
      <button v-if="state?.refreshOnly" type="button" class="btn btn-primary" :disabled="busy" @click="show">刷新状态</button>
      <button v-else type="button" class="btn btn-primary" :disabled="busy || !state?.allowed || state.done" @click="submit">{{ busy ? '处理中…' : state?.done ? '接口处理完成' : state?.retry?.label ?? (message ? '继续核对并处理' : '确认' + label) }}</button>
    </template>
  </BootstrapModal>
</template>
