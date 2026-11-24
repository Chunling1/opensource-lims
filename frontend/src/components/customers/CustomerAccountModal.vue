<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import DataTable from '../common/table/DataTable.vue'
import FormLeaveConfirmation from '../common/FormLeaveConfirmation.vue'
import { useFormLeaveGuard } from '../common/useFormLeaveGuard'
import CustomerContractPicker from './CustomerContractPicker.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { AppError, normalizeError, type ErrorValue } from '../../services/common/errors'
import { customerContractColumns, emptyCustomerAccount, type CustomerAccount } from '../../types/customers/accounts'
import type { RegistrationContract } from '../../types/commissions/commissionForm'
const props = defineProps<{ mode: 'new' | 'edit' | 'view'; row?: CustomerAccount }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const draft = reactive(emptyCustomerAccount()), contracts = ref<RegistrationContract[]>([]), selected = ref<string[]>([]), tab = ref('info'), picker = ref(false), removeConfirm = ref(false)
const loading = ref(false), loaded = ref(props.mode === 'new'), busy = ref(false), error = ref<ErrorValue>('')
const title = computed(() => `${{ new: '新增', edit: '修改', view: '查看' }[props.mode]}账号`)
const readonly = computed(() => props.mode === 'view')
const leave = useFormLeaveGuard(() => draft, () => !readonly.value && loaded.value && !loading.value, () => busy.value)
async function close() { if (picker.value) { picker.value = false; return }; if (await leave.allowLeave()) emit('close') }
let alive = true, controller: AbortController | undefined
async function load() {
  if (!props.row) return
  controller?.abort(); const request = controller = new AbortController(); loading.value = true; loaded.value = false; error.value = ''
  try { const row = await registrationDemo.customerAccount(props.row.id, request.signal); if (alive && !request.signal.aborted) { for (const key of Object.keys(draft) as (keyof typeof draft)[]) Object.assign(draft, { [key]: row[key] }); contracts.value = row.contracts; loaded.value = true } }
  catch (issue) { if (alive && !request.signal.aborted) error.value = normalizeError(issue) }
  finally { if (alive && !request.signal.aborted) loading.value = false }
}
function associate(rows: RegistrationContract[]) { for (const row of rows) if (!draft.contractIds.includes(row.id)) { draft.contractIds.push(row.id); contracts.value.push(row) }; picker.value = false }
function remove() { draft.contractIds = draft.contractIds.filter(id => !selected.value.includes(id)); contracts.value = contracts.value.filter(row => draft.contractIds.includes(row.id)); selected.value = []; removeConfirm.value = false }
async function save() {
  if (busy.value || loading.value || !loaded.value || readonly.value) return
  if (!draft.name.trim()) { tab.value = 'info'; error.value = new AppError('VALIDATION', '请填写客户名称。', { fieldErrors: { name: '请填写客户名称。' } }); return }
  busy.value = true; error.value = ''
  try { await registrationDemo.saveCustomerAccount({ ...draft, ...(props.row ? { id: props.row.id } : {}) }); if (alive) { leave.commit(); emit('saved') } }
  catch (issue) { if (alive) { tab.value = 'info'; error.value = normalizeError(issue) } }
  finally { if (alive) busy.value = false }
}
if (props.row) void load()
onBeforeUnmount(() => { alive = false; controller?.abort() })
</script>
<template>
  <BootstrapModal open guard-close :title="title" size="xl" scrollable fullscreen-mobile :busy="busy" :loading="loading" @close="close">
    <template v-if="loaded">
      <ul class="nav nav-tabs mb-3" role="tablist"><li v-for="item in [{ id: 'info', label: '账号信息' }, { id: 'contracts', label: '关联合同' }]" :key="item.id" class="nav-item" role="presentation"><button :id="`account-tab-${item.id}`" type="button" role="tab" class="nav-link" :class="{ active: tab === item.id }" :aria-selected="tab === item.id" :aria-controls="`account-panel-${item.id}`" @click="tab = item.id">{{ item.label }}</button></li></ul>
      <form id="customer-account-form" novalidate @submit.prevent="save">
        <div v-show="tab === 'info'" id="account-panel-info" role="tabpanel" aria-labelledby="account-tab-info">
          <h6 class="mb-3">基本信息</h6>
          <fieldset class="row g-3" :disabled="readonly || busy">
            <div class="col-12 col-md-4"><label for="account-code" class="form-label">客户账号</label><input id="account-code" class="form-control" :value="row?.code || ''" placeholder="保存后自动生成" disabled /></div>
            <div class="col-12 col-md-8"><label for="account-name" class="form-label">客户名称<span class="text-danger ms-1" aria-hidden="true">*</span></label><input id="account-name" v-model="draft.name" data-validation-key="name" class="form-control" required maxlength="200" /></div>
            <div class="col-12 col-md-4"><label for="account-postcode" class="form-label">邮政编码</label><input id="account-postcode" v-model="draft.postcode" data-validation-key="postcode" class="form-control" maxlength="6" inputmode="numeric" /></div>
            <div class="col-12 col-md-8"><label for="account-address" class="form-label">地址</label><input id="account-address" v-model="draft.address" data-validation-key="address" class="form-control" maxlength="500" /></div>
            <div v-for="field in [{ key: 'contact', label: '联系人' }, { key: 'mobile', label: '手机号码' }, { key: 'phone', label: '单位电话' }, { key: 'fax', label: '传真' }] as const" :key="field.key" class="col-12 col-md-4"><label :for="`account-${field.key}`" class="form-label">{{ field.label }}</label><input :id="`account-${field.key}`" v-model="draft[field.key]" :data-validation-key="field.key" class="form-control" maxlength="200" /></div>
            <div class="col-12 col-md-8"><label for="account-email" class="form-label">电子邮箱</label><input id="account-email" v-model="draft.email" data-validation-key="email" class="form-control" type="email" maxlength="200" /></div>
            <div class="col-12"><label for="account-notes" class="form-label">备注</label><textarea id="account-notes" v-model="draft.notes" data-validation-key="notes" class="form-control" rows="3" maxlength="2000" /></div>
          </fieldset>
        </div>
        <div v-show="tab === 'contracts'" id="account-panel-contracts" role="tabpanel" aria-labelledby="account-tab-contracts">
          <div v-if="!readonly" class="d-flex justify-content-end gap-2 mb-3"><button type="button" class="btn btn-primary" :disabled="busy" @click="picker = true">新增关联合同</button><button type="button" class="btn btn-light" :disabled="busy || !selected.length" @click="removeConfirm = true">删除关联合同</button></div>
          <DataTable label="关联合同" :rows="contracts" :columns="customerContractColumns" :row-key="row => row.id" :row-label="row => row.code" :selectable="() => !readonly && !busy" v-model:selected="selected" />
        </div>
      </form>
    </template>
    <ErrorNotice :error="error" :retry="!loaded" :busy="loading || busy" @retry="load" />
    <template #footer><button type="button" class="btn btn-light" :disabled="busy" @click="close">{{ readonly ? '返回' : '取消' }}</button><button v-if="!readonly" type="submit" form="customer-account-form" class="btn btn-primary" :disabled="busy || loading || !loaded">{{ busy ? '正在保存…' : '保存' }}</button></template>
  </BootstrapModal>
  <CustomerContractPicker v-if="picker" :linked="draft.contractIds" @close="picker = false" @select="associate" />
  <ConfirmationModal v-if="removeConfirm" title="删除关联合同" @close="removeConfirm = false"><p class="mb-0">确定移除所选 {{ selected.length }} 份合同的关联？合同本身不会删除，保存账号后生效。</p><template #footer><button class="btn btn-light" @click="removeConfirm = false">取消</button><button class="btn btn-danger" @click="remove">确认移除</button></template></ConfirmationModal>
  <FormLeaveConfirmation :guard="leave" />
</template>

