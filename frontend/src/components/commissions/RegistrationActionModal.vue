<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { currentActor } from '../../stores/session'
import { workspaceActions, registrationRoot, reviewRoot, changesRoot } from '../../services/commissions/registrationService'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { RegistrationWorkspace, RegistrationKind, RegistrationCommission, RegistrationSample } from '../../types/commissions/registration'
import type { ReportStage } from '../../types/reports/reportCheck'
const props = defineProps<{ kind: RegistrationKind; record?: RegistrationCommission | RegistrationSample; initialAction?: string; workspace?: RegistrationWorkspace; reportStage?: ReportStage; reportQuery?: boolean }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const selected = ref(''), reason = ref(''), busy = ref(false), error = ref<ErrorValue>('')
const actions = computed(() => props.record ? props.reportStage || props.reportQuery ? [{ id: 'void', label: '作废', reason: true, disabled: false, disabledReason: undefined }] : workspaceActions(currentActor.value, props.kind, props.record, props.workspace) : [])
const voidRequest = computed(() => props.kind === 'samples' && selected.value === 'void')
const action = computed(() => actions.value.find(a => a.id === selected.value))
watch(() => props.record, () => { selected.value = props.initialAction || ''; reason.value = ''; error.value = '' })
async function submit() {
  if (!props.record || !action.value || action.value.disabled || busy.value) return
  busy.value = true; error.value = ''
  try {
    if (props.reportQuery) await registrationDemo.reportQueryVoid(props.record.id, props.record.version, reason.value)
    else if (props.reportStage) await registrationDemo.reportVoidAction(props.record.id, props.record.version, reason.value, props.reportStage)
    else await registrationDemo.act(props.kind, props.record.id, action.value.id, props.record.version, reason.value)
    emit('saved'); emit('close')
  }
  catch (e) { error.value = normalizeError(e) } finally { busy.value = false }
}
</script>
<template><BootstrapModal :open="!!record" :title="voidRequest ? '作废申请' : action?.label || '更多操作'" :busy="busy" @close="!busy && emit('close')"><template v-if="record"><p class="text-break"><strong>{{ record.code }}</strong> · {{ record.name }}</p><ErrorNotice :error="error" :latest-to="`${workspace === 'changes' ? changesRoot : workspace === 'review' ? reviewRoot : registrationRoot}/${kind}/${record.id}`" @reload="emit('saved'); emit('close')" /><div v-if="!action" class="d-grid gap-2"><button v-for="item in actions" :key="item.id" class="btn" :class="item.id === 'void' ? 'btn-danger-lt' : 'btn-light'" :disabled="item.disabled" :title="item.disabledReason" @click="selected = item.id">{{ item.label }}</button><p v-if="!actions.length" class="text-muted mb-0">当前状态没有可执行的操作。</p></div><form v-else id="registration-action" @submit.prevent="submit"><p v-if="voidRequest">确认对这条样品提交“作废申请”？</p><p v-else>确认对这条{{ kind === 'commissions' ? '委托' : '样品' }}执行“{{ action.id === 'complete-change' ? '完成更改' : action.label }}”？</p><div v-if="action.reason"><label for="registration-action-reason" class="form-label">{{ voidRequest ? '申请作废原因' : '操作原因' }}</label><textarea id="registration-action-reason" v-model="reason" class="form-control" rows="3" required maxlength="500" :disabled="busy"></textarea></div></form></template><template #footer><button class="btn btn-light" :disabled="busy" @click="emit('close')">取消</button><button v-if="action" class="btn btn-primary" type="submit" form="registration-action" :disabled="busy || action.disabled">{{ busy ? '正在保存…' : '确认' }}</button></template></BootstrapModal></template>


