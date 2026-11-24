<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import { inject } from 'vue'
const registrationDemo = inject<any>('platform-registration-services')!
if (!registrationDemo) throw Error('缺少平台表单服务')
import { organizationNames } from '../../services/commissions/organizationNames'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { currentActor } from '../../stores/session'
import type { Manufacturer, ManufacturerPage, ManufacturerQuery } from '../../types/commissions/manufacturer'

const props = defineProps<{ open: boolean; value: string }>()
const emit = defineEmits<{ close: []; select: [string] }>()
const filters = reactive({ code: '', name: '', type: '' })
const applied = ref<ManufacturerQuery>({}), pageSize = ref(10), requestedPage = ref(1)
const result = ref<ManufacturerPage>({ items: [], total: 0, page: 1, pageSize: 10, types: [] })
const loading = ref(false), error = ref<ErrorValue>(''), selectedNames = ref<string[]>([])
const combined = computed(() => selectedNames.value.join('；'))
const allChecked = computed(() => result.value.items.length > 0 && result.value.items.every(isSelected))
const someChecked = computed(() => result.value.items.some(isSelected))
let controller: AbortController | undefined, sequence = 0
function isSelected(row: Manufacturer) { return selectedNames.value.includes(row.name) }
async function load(page = 1) {
  requestedPage.value = page
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  loading.value = true; error.value = ''; result.value.items = []
  try {
    const data = await registrationDemo.manufacturers({ ...applied.value, page, pageSize: pageSize.value }, active.signal)
    if (token === sequence) result.value = data
  } catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
function search() { applied.value = { ...filters }; void load() }
function resize(size: number) { pageSize.value = size; void load() }
function choose(row: Manufacturer) {
  selectedNames.value = isSelected(row) ? selectedNames.value.filter(name => name !== row.name) : [...selectedNames.value, row.name]
}
function choosePage() {
  const names = new Set(result.value.items.map((row: any) => row.name))
  selectedNames.value = allChecked.value ? selectedNames.value.filter(name => !names.has(name)) : [...new Set([...selectedNames.value, ...names])]
}
function confirm() { if (!loading.value && !error.value && combined.value.length <= 2000) emit('select', combined.value) }
function cancelRequest() { sequence++; controller?.abort(); loading.value = false }
watch(() => props.open, open => {
  cancelRequest()
  if (open) {
    Object.assign(filters, { code: '', name: '', type: '' }); applied.value = {}; pageSize.value = 10
    selectedNames.value = organizationNames(props.value); void load()
  }
}, { immediate: true })
watch(currentActor, () => { cancelRequest(); emit('close') })
onBeforeUnmount(cancelRequest)
</script>

<template>
  <BootstrapModal :loading="loading" :open="open" title="选择生产厂家" size="xl" scrollable fullscreen-mobile fill-height body-class="p-0 mx-3 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <form class="row g-3 align-items-end mb-3" aria-label="厂家查询" @submit.prevent="search">
        <div class="col-12 col-md-3"><label for="manufacturer-code" class="form-label">厂家代号</label><input id="manufacturer-code" v-model="filters.code" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-md-3"><label for="manufacturer-name" class="form-label">厂家名称</label><input id="manufacturer-name" v-model="filters.name" class="form-control" maxlength="200" /></div>
        <div class="col-12 col-md-3"><label for="manufacturer-type" class="form-label">厂家类型</label><select id="manufacturer-type" v-model="filters.type" class="form-select"><option value="">全部</option><option v-for="type in result.types" :key="type">{{ type }}</option></select></div>
        <div class="col-auto d-flex gap-2"><button class="btn btn-primary" type="submit" :disabled="loading">查询</button></div>
      </form>
      <div class="form-check mb-3"><input id="manufacturer-all" class="form-check-input" type="checkbox" :checked="allChecked" :indeterminate="someChecked && !allChecked" :disabled="loading || !!error || !result.items.length" @change="choosePage" /><label for="manufacturer-all" class="form-check-label">全选本页</label></div>
    </template>
    <ErrorNotice :error="error" retry :busy="loading" @retry="load(requestedPage)" />
    <p v-if="loading" class="text-muted text-center py-4" role="status">正在查询厂家…</p>
    <table v-else-if="!error" class="table table-striped table-hover align-middle mb-0" aria-label="可选生产厂家列表">
      <thead class="table-light"><tr><th scope="col" class="text-center" aria-label="选择"></th><th scope="col" class="text-nowrap">厂家（产地）代号</th><th scope="col" class="text-nowrap">厂家（产地）名称</th><th scope="col" class="text-nowrap">厂家（产地）类型</th></tr></thead>
      <tbody>
        <tr v-for="row in result.items" :key="row.id" :class="{ 'table-active': isSelected(row) }">
          <td class="text-center"><input :id="`manufacturer-choice-${row.id}`" class="form-check-input" type="checkbox" :checked="isSelected(row)" :aria-label="`选择 ${row.name}`" @click.stop @change="choose(row)" /></td>
          <td class="text-nowrap">{{ row.code }}</td><td class="text-nowrap">{{ row.name }}</td><td>{{ row.type }}</td>
        </tr>
        <tr v-if="!result.items.length"><td colspan="4" class="text-center text-muted py-5">没有符合条件的厂家</td></tr>
      </tbody>
    </table>
    <template #pagination><div :inert="loading || !!error" :aria-busy="loading"><TablePagination label="可选厂家" :total="result.total" :page="result.page" :page-size="result.pageSize" :sizes="[5, 10, 20]" extended @page="load" @size="resize" /></div></template>
    <template #footer>
      <span class="me-auto" :class="combined.length > 2000 ? 'text-danger' : 'text-muted'">{{ combined.length > 2000 ? '厂家名称合计不能超过 2000 字' : `已选 ${selectedNames.length} 家` }}</span>
      <button class="btn btn-light" type="button" @click="emit('close')">返回</button><button class="btn btn-primary" type="button" :disabled="loading || !!error || combined.length > 2000" @click="confirm">确定</button>
    </template>
  </BootstrapModal>
</template>
