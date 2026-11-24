<script setup lang="ts">
import { computed, ref, reactive, watch, onBeforeUnmount } from 'vue'
import ConfirmationModal from '../common/ConfirmationModal.vue'
import TemplateDateRange from '../common/TemplateDateRange.vue'
import SingleChoice from '../common/SingleChoice.vue'
import TablePagination from '../common/table/TablePagination.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { RegistrationPage } from '../../types/commissions/registration'
import { contractSearchFields, type RegistrationContract, type RegistrationContractQuery } from '../../types/commissions/commissionForm'
const props = withDefaults(defineProps<{ open: boolean; multiple?: boolean; linked?: string[]; initialDates?: { from: string; to: string } }>(), { multiple: false, linked: () => [] })
const emit = defineEmits<{ close: []; select: [RegistrationContract]; 'select-many': [RegistrationContract[]] }>()
const defaults = (): RegistrationContractQuery => ({ keyword: '', from: props.initialDates?.from || '', to: props.initialDates?.to || '', searchField: 'all', ownDepartment: true })
const filters = reactive(defaults()), applied = ref(defaults()), loading = ref(false), error = ref<ErrorValue>('')
const selected = ref<RegistrationContract>(), pageSize = ref(10), checked = ref<RegistrationContract[]>([]), dateInput = ref<InstanceType<typeof TemplateDateRange>>()
const result = ref<RegistrationPage<RegistrationContract>>({ items: [], total: 0, page: 1, pageSize: 10 })
const eligible = computed(() => result.value.items.filter(row => !props.linked.includes(row.id)))
const selectedIds = computed(() => new Set(checked.value.map(row => row.id)))
const selectedCount = computed(() => eligible.value.filter(row => selectedIds.value.has(row.id)).length)
const canConfirm = computed(() => props.multiple ? checked.value.length > 0 : !!selected.value)
function toggle(row: RegistrationContract, active: boolean) { if (loading.value || props.linked.includes(row.id)) return; checked.value = checked.value.filter(item => item.id !== row.id); if (active) checked.value.push(row) }
function togglePage() { if (loading.value) return; const all = eligible.value.length > 0 && selectedCount.value === eligible.value.length; for (const row of eligible.value) toggle(row, !all) }
let controller: AbortController | undefined, sequence = 0
async function load(page = 1) {
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  loading.value = true; error.value = ''; selected.value = undefined; result.value.items = []
  try { const data = await registrationDemo.contracts({ ...applied.value, page, pageSize: pageSize.value }, active.signal); if (token === sequence) result.value = data }
  catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
function search() { if (loading.value || !dateInput.value?.validate()) return; applied.value = { ...filters }; void load() }
function resize(size: number) { pageSize.value = size; void load() }
function confirm() {
  if (!canConfirm.value || loading.value || error.value) return
  if (props.multiple) emit('select-many', checked.value.filter(row => !props.linked.includes(row.id)))
  else if (selected.value) emit('select', selected.value)
}
function clear() { sequence++; controller?.abort(); result.value.items = []; selected.value = undefined; checked.value = [] }
watch(() => props.open, open => {
  if (open) { Object.assign(filters, defaults()); applied.value = defaults(); pageSize.value = 10; checked.value = []; void load() }
  else clear()
}, { immediate: true })
watch(currentActor, () => { clear(); emit('close') })
onBeforeUnmount(clear)
</script>
<template>
  <ConfirmationModal v-if="open" title="选择合同号" size="xl" fill-height @close="emit('close')">
    <div class="d-flex flex-column h-100 overflow-hidden">
      <form class="d-flex flex-wrap align-items-center gap-2 px-3 pb-3 flex-shrink-0" aria-label="合同查询" @submit.prevent="search">
        <div class="d-flex align-items-center gap-1 flex-grow-1"><label for="contract-field" class="col-form-label text-nowrap">查询内容</label><select id="contract-field" v-model="filters.searchField" class="form-select w-auto flex-grow-1"><option v-for="field in contractSearchFields" :key="field.value" :value="field.value">{{ field.label }}</option></select></div>
        <div class="d-flex align-items-center gap-1 flex-grow-1"><label for="contract-keyword" class="col-form-label text-nowrap">包含</label><input id="contract-keyword" v-model="filters.keyword" class="form-control w-auto flex-grow-1" size="18" maxlength="200" /></div>
        <div class="d-flex align-items-center gap-1 mw-100 flex-grow-1"><label for="contract-dates" class="col-form-label text-nowrap">签订日期</label><div class="overflow-hidden flex-grow-1"><TemplateDateRange id="contract-dates" ref="dateInput" within-modal :from="filters.from || ''" :to="filters.to || ''" @change="Object.assign(filters, $event)" /></div></div>
        <div class="form-check mb-0"><input id="contract-own" v-model="filters.ownDepartment" class="form-check-input" type="checkbox" /><label for="contract-own" class="form-check-label text-nowrap">本部门合同</label></div>
        <button class="btn btn-primary" type="submit" :disabled="loading">查询</button>
      </form>
      <div data-contract-results class="modal-body pt-0 px-3 overflow-auto" :aria-busy="loading">
        <ErrorNotice :error="error" retry @retry="load(result.page)" />
        <p v-if="loading" class="text-muted text-center py-4" role="status">正在查询合同…</p>
        <table v-else-if="!error" class="table table-hover table-nowrap align-middle mb-0" aria-label="可选合同列表">
          <thead class="table-light"><tr><th scope="col"><input v-if="multiple" class="form-check-input" type="checkbox" aria-label="全选当前页可选合同" :disabled="!eligible.length" :checked="eligible.length > 0 && selectedCount === eligible.length" :indeterminate="selectedCount > 0 && selectedCount < eligible.length" @change="togglePage" /><span v-else class="visually-hidden">选择</span></th><th scope="col">合同号</th><th scope="col">合同名称</th><th scope="col">委托方</th><th scope="col">工程名称</th><th scope="col">工程地址</th><th scope="col">施工单位</th><th scope="col">登记状态</th></tr></thead>
          <tbody><tr v-for="row in result.items" :key="row.id" :class="{ 'table-active': multiple ? selectedIds.has(row.id) : selected?.id === row.id }"><td><input v-if="multiple" class="form-check-input" type="checkbox" :aria-label="`选择可选合同 ${row.code}`" :checked="selectedIds.has(row.id)" :disabled="linked.includes(row.id)" :title="linked.includes(row.id) ? '已关联合同' : undefined" @change="toggle(row, ($event.target as HTMLInputElement).checked)" /><SingleChoice v-else :id="`contract-choice-${row.id}`" name="selected-contract" :checked="selected?.id === row.id" :label="`选择 ${row.code}`" @change="selected = row" /></td><td>{{ row.code }}</td><td>{{ row.name }}</td><td>{{ row.customer }}</td><td>{{ row.projectName }}</td><td>{{ row.projectAddress }}</td><td>{{ row.constructionCompany }}</td><td>{{ row.registrationStatus }}</td></tr><tr v-if="!result.items.length"><td colspan="8" class="text-center text-muted py-5">没有符合条件的合同</td></tr></tbody>
        </table>
      </div>
      <div class="flex-shrink-0" :inert="loading || !!error" :aria-busy="loading"><TablePagination label="可选合同" :total="result.total" :page="result.page" :page-size="result.pageSize" :sizes="[5, 10, 20]" extended @page="load" @size="resize" /></div>
    </div>
    <template #footer><span v-if="multiple" class="me-auto text-muted">已选择 {{ checked.length }} 份合同</span><button class="btn btn-light" type="button" @click="emit('close')">{{ multiple ? '取消' : '返回' }}</button><button class="btn btn-primary" type="button" :disabled="!canConfirm || loading || !!error" @click="confirm">确定</button></template>
  </ConfirmationModal>
</template>
