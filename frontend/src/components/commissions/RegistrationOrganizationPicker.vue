<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import SingleChoice from '../common/SingleChoice.vue'
import TablePagination from '../common/table/TablePagination.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { organizationNames } from '../../services/commissions/organizationNames'
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { RegistrationPage } from '../../types/commissions/registration'
import type { RegistrationOrganization } from '../../types/commissions/commissionForm'

const props = defineProps<{ open: boolean; title: string; multiple?: boolean; value?: string }>()
const emit = defineEmits<{ close: []; select: [string] }>()
const keyword = ref(''), applied = ref(''), loading = ref(false), error = ref<ErrorValue>('')
const selected = ref<RegistrationOrganization>(), pageSize = ref(10)
const selectedNames = ref<string[]>([])
const combined = computed(() => selectedNames.value.join('；'))
const allChecked = computed(() => result.value.items.length > 0 && result.value.items.every(row => selectedNames.value.includes(row.name)))
const someChecked = computed(() => result.value.items.some(row => selectedNames.value.includes(row.name)))
const result = ref<RegistrationPage<RegistrationOrganization>>({ items: [], total: 0, page: 1, pageSize: 10 })
let controller: AbortController | undefined, sequence = 0
async function load(page = 1) {
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  loading.value = true; error.value = ''; selected.value = undefined; result.value.items = []
  try {
    const data = await registrationDemo.organizations({ keyword: applied.value, page, pageSize: pageSize.value }, active.signal)
    if (token === sequence) {
      result.value = data
      if (!props.multiple) selected.value = data.items.find(row => row.name === props.value?.trim())
    }
  } catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
function search() { applied.value = keyword.value; void load() }
function resize(size: number) { pageSize.value = size; void load() }
function isSelected(row: RegistrationOrganization) { return props.multiple ? selectedNames.value.includes(row.name) : selected.value?.id === row.id }
function choose(row: RegistrationOrganization) {
  if (!props.multiple) { selected.value = row; return }
  selectedNames.value = isSelected(row) ? selectedNames.value.filter(name => name !== row.name) : [...selectedNames.value, row.name]
}
function choosePage() {
  const names = new Set(result.value.items.map(row => row.name))
  selectedNames.value = allChecked.value ? selectedNames.value.filter(name => !names.has(name)) : [...new Set([...selectedNames.value, ...names])]
}
function confirm() {
  if (loading.value || error.value) return
  if (props.multiple && combined.value.length <= 500) emit('select', combined.value)
  else if (!props.multiple && selected.value) emit('select', selected.value.name)
}
function clear() { sequence++; controller?.abort(); result.value.items = []; selected.value = undefined; selectedNames.value = [] }
watch(() => props.open, open => {
  if (open) { const currentNames = organizationNames(props.value || ''); keyword.value = ''; applied.value = ''; pageSize.value = 10; selectedNames.value = props.multiple ? currentNames : []; void load() }
  else clear()
}, { immediate: true })
watch(currentActor, () => { clear(); emit('close') })
onBeforeUnmount(clear)
</script>

<template>
  <BootstrapModal :loading="loading" :open="open" :title="title" size="lg" scrollable fullscreen-mobile fill-height body-class="p-0 mx-3 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <form class="row g-2 align-items-center mb-3" aria-label="单位查询" @submit.prevent="search">
        <div class="col-12 col-sm-auto"><label for="organization-keyword" class="col-form-label">单位名称</label></div>
        <div class="col-12 col-sm"><input id="organization-keyword" v-model="keyword" class="form-control" maxlength="500" /></div>
        <div class="col-auto d-flex gap-1"><button class="btn btn-primary" type="submit">查询</button></div>
      </form>
    </template>
    <ErrorNotice :error="error" retry @retry="load(result.page)" />
    <p v-if="loading" class="text-muted text-center py-4" role="status">正在查询单位…</p>
    <table v-else-if="!error" class="table table-striped table-hover align-middle mb-0" aria-label="可选单位列表">
      <thead class="table-light"><tr><th scope="col" class="text-center" aria-label="选择"><input v-if="multiple" class="form-check-input" type="checkbox" aria-label="选择本页单位" :checked="allChecked" :indeterminate="someChecked && !allChecked" :disabled="!result.items.length" @change="choosePage" /></th><th scope="col">委托单位</th></tr></thead>
      <tbody>
        <tr v-for="row in result.items" :key="row.id" :class="{ 'table-active': isSelected(row) }">
          <td class="text-center"><input v-if="multiple" :id="`organization-choice-${row.id}`" class="form-check-input" type="checkbox" name="selected-organization" :checked="isSelected(row)" :aria-label="`选择 ${row.name}`" @click.stop @change="choose(row)" /><SingleChoice v-else :id="`organization-choice-${row.id}`" name="selected-organization" :checked="isSelected(row)" :label="`选择 ${row.name}`" @change="choose(row)" /></td>
          <td class="text-break">{{ row.name }}</td>
        </tr>
        <tr v-if="!result.items.length"><td colspan="2" class="text-center text-muted py-5">没有符合条件的单位</td></tr>
      </tbody>
    </table>
    <template #pagination><div :inert="loading || !!error" :aria-busy="loading"><TablePagination label="可选单位" :total="result.total" :page="result.page" :page-size="result.pageSize" :sizes="[5, 10, 20]" extended @page="load" @size="resize" /></div></template>
    <template #footer>
      <span v-if="multiple" class="me-auto" :class="combined.length > 500 ? 'text-danger' : 'text-muted'">{{ combined.length > 500 ? '单位名称合计不能超过 500 字' : `已选 ${selectedNames.length} 家` }}</span>
      <button class="btn btn-light" type="button" @click="emit('close')">返回</button><button class="btn btn-primary" type="button" :disabled="(multiple ? combined.length > 500 : !selected) || loading || !!error" @click="confirm">确定</button>
    </template>
  </BootstrapModal>
</template>
