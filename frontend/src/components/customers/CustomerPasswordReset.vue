<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { CustomerAccount } from '../../types/customers/accounts'
const props = defineProps<{ row: CustomerAccount }>()
const emit = defineEmits<{ close: [] }>()
const busy = ref(false), error = ref<ErrorValue>(''), password = ref('')
let alive = true
async function reset() {
  if (busy.value || password.value) return
  busy.value = true; error.value = ''
  try { const result = await registrationDemo.resetCustomerPassword(props.row.id); if (alive) password.value = result.password }
  catch (issue) { if (alive) error.value = normalizeError(issue) }
  finally { if (alive) busy.value = false }
}
onBeforeUnmount(() => { alive = false; password.value = '' })
</script>
<template>
  <ConfirmationModal :title="password ? '密码重置成功' : '密码重置'" :busy="busy" @close="emit('close')">
    <template v-if="password"><p>客户账号：{{ row.code }}</p><label for="customer-temporary-password" class="form-label">临时密码</label><input id="customer-temporary-password" class="form-control font-monospace" :value="password" readonly autocomplete="off" /><p class="text-muted mt-3 mb-0">临时密码仅本次显示，请妥善保存并告知客户首次登录时修改。</p></template>
    <p v-else class="mb-0">确认重置“{{ row.name }}”（{{ row.code }}）的密码？原密码将失效，系统将生成新的临时密码。</p>
    <ErrorNotice :error="error" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="emit('close')">{{ password ? '关闭' : '取消' }}</button><button v-if="!password" type="button" class="btn btn-primary" :disabled="busy" @click="reset">{{ busy ? '正在重置…' : '确认重置' }}</button></template>
  </ConfirmationModal>
</template>
