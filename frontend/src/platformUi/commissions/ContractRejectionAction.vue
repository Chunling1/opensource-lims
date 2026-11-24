<script setup lang="ts">
import {ref} from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import {platformError} from '../apiErrors'
const props=defineProps<{record:any;submitReason:(reason:string)=>Promise<boolean>}>()
const emit=defineEmits<{close:[];saved:[]}>()
const kind:string='samples',voidRequest=false,workspace:string='review',changesRoot='',reviewRoot='',registrationRoot=''
const selected=ref('reject'),reason=ref(''),busy=ref(false),error=ref<any>('')
const actions=[{id:'reject',label:'退回（不通过）',reason:true,disabled:false,disabledReason:undefined}],action=actions[0]!
async function submit(){if(busy.value||!reason.value.trim())return;busy.value=true;try{if(await props.submitReason(reason.value))emit('close')}catch(e){error.value=platformError(e)}finally{busy.value=false}}
</script>
<template><BootstrapModal :open="!!record" :title="voidRequest ? '作废申请' : action?.label || '更多操作'" :busy="busy" @close="!busy && emit('close')"><template v-if="record"><p class="text-break"><strong>{{ record.code }}</strong> · {{ record.name }}</p><ErrorNotice :error="error" :latest-to="`${workspace === 'changes' ? changesRoot : workspace === 'review' ? reviewRoot : registrationRoot}/${kind}/${record.id}`" @reload="emit('saved'); emit('close')" /><div v-if="!action" class="d-grid gap-2"><button v-for="item in actions" :key="item.id" class="btn" :class="item.id === 'void' ? 'btn-danger-lt' : 'btn-light'" :disabled="item.disabled" :title="item.disabledReason" @click="selected = item.id">{{ item.label }}</button><p v-if="!actions.length" class="text-muted mb-0">当前状态没有可执行的操作。</p></div><form v-else id="registration-action" @submit.prevent="submit"><p v-if="voidRequest">确认对这条样品提交“作废申请”？</p><p v-else>确认对这条{{ kind === 'commissions' ? '委托' : '样品' }}执行“{{ action.id === 'complete-change' ? '完成更改' : action.label }}”？</p><div v-if="action.reason"><label for="registration-action-reason" class="form-label">{{ voidRequest ? '申请作废原因' : '操作原因' }}</label><textarea id="registration-action-reason" v-model="reason" class="form-control" rows="3" required maxlength="500" :disabled="busy"></textarea></div></form></template><template #footer><button class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button v-if="action" class="btn btn-primary" type="submit" form="registration-action" :disabled="busy || action.disabled">{{ busy ? '正在保存…' : '确认' }}</button></template></BootstrapModal></template>


