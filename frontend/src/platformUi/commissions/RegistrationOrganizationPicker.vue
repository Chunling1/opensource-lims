<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount, useId } from 'vue'
import { useLiveSearch } from '@/composables/liveSearch'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import SingleChoice from '../../components/common/SingleChoice.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { inject } from 'vue'
const registrationDemo = inject<any>('platform-registration-services')!
if (!registrationDemo) throw Error('缺少平台表单服务')
import { organizationNames } from '../../services/commissions/organizationNames'
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { RegistrationPage } from '../../types/commissions/registration'
import type { RegistrationOrganization } from '../../types/commissions/commissionForm'

const props = defineProps<{ open: boolean; title: string; multiple?: boolean; value?: string }>()
const emit = defineEmits<{ close: []; select: [string] }>()
const instanceId = useId()
const keyword = ref(''), applied = ref(''), loading = ref(false), error = ref<ErrorValue>('')
const selected = ref<RegistrationOrganization>(), pageSize = ref(10)
const selectedNames = ref<string[]>([])
const combined = computed(() => selectedNames.value.join('；'))
const allChecked = computed(() => result.value.items.length > 0 && result.value.items.every((row: any) => selectedNames.value.includes(row.name)))
const someChecked = computed(() => result.value.items.some((row: any) => selectedNames.value.includes(row.name)))
const result = ref<RegistrationPage<RegistrationOrganization>>({ items: [], total: 0, page: 1, pageSize: 10 })
let controller: AbortController | undefined, sequence = 0, resetting = false
async function load(page = 1) {
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  loading.value = true; error.value = ''; result.value.items = []
  const timeout = setTimeout(() => active.abort(), 12000)
  try {
    const data = await registrationDemo.organizations({ keyword: applied.value, page, pageSize: pageSize.value }, active.signal)
    if (token === sequence && props.open) {
      result.value = data
      if (!props.multiple && selected.value) selected.value = data.items.find((row: any) => row.name === selected.value?.name) || selected.value
    }
  } catch (e) { if (token === sequence && props.open) error.value = normalizeError(active.signal.aborted ? Error('客户查询超时，请重试；已选单位已保留。') : e) }
  finally { clearTimeout(timeout); if (token === sequence) loading.value = false }
}
function search() { liveSearch.cancel(); applied.value = keyword.value.trim(); void load() }
function resize(size: number) { pageSize.value = size; void load() }
function isSelected(row: RegistrationOrganization) { return props.multiple ? selectedNames.value.includes(row.name) : selected.value?.id === row.id }
function choose(row: RegistrationOrganization) {
  if (!props.multiple) { selected.value = row; return }
  if (!isSelected(row) && selectedNames.value.length >= 20) return
  selectedNames.value = isSelected(row) ? selectedNames.value.filter(name => name !== row.name) : [...selectedNames.value, row.name]
}
function choosePage() {
  const names = new Set(result.value.items.map((row: any) => row.name))
  selectedNames.value = allChecked.value ? selectedNames.value.filter(name => !names.has(name)) : [...new Set([...selectedNames.value, ...names])].slice(0, 20)
}
function confirm() {
  if (loading.value || error.value) return
  if (props.multiple && combined.value.length <= 500) emit('select', combined.value)
  else if (!props.multiple) emit('select', selected.value?.name || '')
}
function clear() { liveSearch.cancel(); sequence++; controller?.abort(); result.value.items = []; selected.value = undefined; selectedNames.value = [] }
watch(keyword, () => { sequence++; controller?.abort(); loading.value = false }, { flush: 'sync' })
const liveSearch = useLiveSearch(keyword, () => { applied.value = keyword.value.trim(); void load() }, () => props.open && !resetting)
watch(() => props.open, open => {
  if (open) { resetting = true; const currentNames = organizationNames(props.value || ''); keyword.value = ''; applied.value = ''; pageSize.value = 10; selectedNames.value = props.multiple ? currentNames : []; selected.value = !props.multiple && props.value ? { id: '', name: props.value } : undefined; liveSearch.cancel(); resetting = false; void load() }
  else clear()
}, { immediate: true })
watch(currentActor, () => { clear(); emit('close') })
onBeforeUnmount(clear)
</script>

<template>
  <BootstrapModal :loading="loading" :open="open" :title="title" size="lg" scrollable fullscreen-mobile fill-height body-class="p-0 mx-3 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <form class="row g-2 align-items-center mb-3" aria-label="单位查询" @submit.prevent="search">
        <div class="col-12 col-sm-auto"><label :for="`${instanceId}-keyword`" class="col-form-label">搜索客户</label></div>
        <div class="col-12 col-sm"><input :id="`${instanceId}-keyword`" v-model="keyword" class="form-control" maxlength="200" placeholder="客户名称 / 客户编码，输入后自动筛选" /></div>
        <div class="col-auto d-flex gap-1"><button class="btn btn-primary" type="submit">查询</button></div>
      </form>
    </template>
    <div v-if="selectedNames.length || selected" class="d-flex flex-wrap gap-2 py-2" aria-label="已选单位">
      <span v-for="name in (multiple ? selectedNames : selected ? [selected.name] : [])" :key="name" class="badge bg-primary-subtle text-primary d-inline-flex align-items-center gap-2 text-wrap">{{ name }}<button class="btn btn-sm btn-light" type="button" :aria-label="`移除 ${name}`" @click="multiple ? selectedNames = selectedNames.filter(n => n !== name) : selected = undefined"><i class="ti ti-x" aria-hidden="true"></i></button></span>
      <button class="btn btn-sm btn-light" type="button" @click="selectedNames = []; selected = undefined">清空已选</button>
    </div>
    <p v-if="multiple" class="small text-muted mb-2">可跨页选择，最多20家；移除后点击确定才应用到表单。</p>
    <ErrorNotice :error="error" retry @retry="load(result.page)" />
    <p v-if="loading" class="text-muted text-center py-4" role="status">正在查询单位…</p>
    <table v-else-if="!error" class="table table-striped table-hover align-middle mb-0" aria-label="可选单位列表">
      <thead class="table-light"><tr><th scope="col" class="text-center" aria-label="选择"><input v-if="multiple" class="form-check-input" type="checkbox" aria-label="选择本页单位" :checked="allChecked" :indeterminate="someChecked && !allChecked" :disabled="!result.items.length" @change="choosePage" /></th><th scope="col">委托单位</th></tr></thead>
      <tbody>
        <tr v-for="row in result.items" :key="row.id" :class="{ 'table-active': isSelected(row) }">
          <td class="text-center"><input v-if="multiple" :id="`${instanceId}-choice-${row.id}`" class="form-check-input" type="checkbox" :name="`${instanceId}-selected`" :checked="isSelected(row)" :aria-label="`选择 ${row.name}`" @click.stop @change="choose(row)" /><SingleChoice v-else :id="`${instanceId}-choice-${row.id}`" :name="`${instanceId}-selected`" :checked="isSelected(row)" :label="`选择 ${row.name}`" @change="choose(row)" /></td>
          <td class="text-break">{{ row.name }}</td>
        </tr>
        <tr v-if="!result.items.length"><td colspan="2" class="text-center text-muted py-5">没有符合条件的单位</td></tr>
      </tbody>
    </table>
    <template #pagination><div :inert="loading || !!error" :aria-busy="loading"><TablePagination label="可选单位" :total="result.total" :page="result.page" :page-size="result.pageSize" :sizes="[5, 10, 20]" extended @page="load" @size="resize" /></div></template>
    <template #footer>
      <span v-if="multiple" class="me-auto" :class="combined.length > 500 ? 'text-danger' : 'text-muted'">{{ combined.length > 500 ? '单位名称合计不能超过 500 字' : `已选 ${selectedNames.length} 家` }}</span>
      <button class="btn btn-light" type="button" @click="emit('close')">返回</button><button class="btn btn-primary" type="button" :disabled="(multiple && combined.length > 500) || loading || !!error" @click="confirm">确定</button>
    </template>
  </BootstrapModal>
</template>
