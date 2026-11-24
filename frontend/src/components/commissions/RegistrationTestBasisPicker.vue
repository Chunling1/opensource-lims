<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, useId, watch } from 'vue'
import BootstrapModal from '../common/BootstrapModal.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import TablePagination from '../common/table/TablePagination.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import { retainBasisSeparators } from '../../services/commissions/testBasisText'
import { currentActor } from '../../stores/session'
import { maxTestBasisSelection, testBasisSearchFields, type TestBasisQuery, type TestBasisPage, type TestBasisStandard, type TestBasisSelection } from '../../types/commissions/testBasis'

const props = withDefaults(defineProps<{ open: boolean; planId: string; ids: string[]; separators: string[]; englishBookMarks: boolean; label?: string }>(), { label: '检测依据' })
const prefix = useId()
const emit = defineEmits<{ close: []; select: [TestBasisSelection] }>()
const defaults = () => ({ searchField: 'code' as typeof testBasisSearchFields[number]['key'], contains: '', qualification: '', departmentCategory: '', ownDepartment: true })
function queryFilters(): Omit<TestBasisQuery, 'planId'> {
  const { searchField, contains, ...rest } = filters
  return { ...rest, [searchField]: contains.trim() }
}
const filters = reactive(defaults()), applied = ref(queryFilters()), more = ref(false)
const selectedIds = ref<string[]>([]), english = ref(false), loading = ref(false), confirming = ref(false), error = ref<ErrorValue>(''), confirmError = ref<ErrorValue>(''), pageSize = ref(10)
const empty = (): TestBasisPage => ({ items: [], total: 0, page: 1, pageSize: 10, departmentCategories: [], qualifications: [] })
const result = ref(empty())
const allChecked = computed(() => result.value.items.length > 0 && result.value.items.every(row => selectedIds.value.includes(row.id)))
const someChecked = computed(() => result.value.items.some(row => selectedIds.value.includes(row.id)))
const canSelectPage = computed(() => new Set([...selectedIds.value, ...result.value.items.map(row => row.id)]).size <= maxTestBasisSelection)
const activeFilters = computed(() => Number(!!applied.value.qualification) + Number(!!applied.value.departmentCategory))
let controller: AbortController | undefined, confirmController: AbortController | undefined, sequence = 0
async function load(page = 1) {
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  loading.value = true; error.value = ''; confirmError.value = ''; result.value.items = []
  try {
    const data = await registrationDemo.testBases({ ...applied.value, planId: props.planId, page, pageSize: pageSize.value }, active.signal)
    if (token === sequence) result.value = data
  } catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
function search() { applied.value = queryFilters(); void load() }
function choose(row: TestBasisStandard) {
  const index = selectedIds.value.indexOf(row.id)
  if (index >= 0) selectedIds.value.splice(index, 1)
  else if (selectedIds.value.length < maxTestBasisSelection) selectedIds.value.push(row.id)
}
function choosePage() {
  const pageIds = new Set(result.value.items.map(row => row.id))
  if (allChecked.value) selectedIds.value = selectedIds.value.filter(id => !pageIds.has(id))
  else if (canSelectPage.value) selectedIds.value = [...new Set([...selectedIds.value, ...pageIds])]
}
function resize(size: number) { pageSize.value = size; void load() }
async function confirm() {
  if (loading.value || confirming.value || error.value) return
  const active = confirmController = new AbortController(), token = sequence
  confirming.value = true; confirmError.value = ''
  try {
    const selection = await registrationDemo.resolveTestBases(props.planId, [...selectedIds.value], english.value, active.signal, retainBasisSeparators(props.ids, props.separators, selectedIds.value))
    if (token === sequence && props.open) emit('select', selection)
  } catch (e) { if (token === sequence && !active.signal.aborted) confirmError.value = normalizeError(e) }
  finally { if (token === sequence) confirming.value = false }
}
function clear() { sequence++; controller?.abort(); confirmController?.abort(); result.value = empty(); selectedIds.value = []; confirming.value = false }
watch(() => [props.open, props.planId], () => {
  clear()
  if (props.open && props.planId) {
    Object.assign(filters, defaults()); applied.value = queryFilters(); more.value = false
    selectedIds.value = [...props.ids]; english.value = props.englishBookMarks; pageSize.value = 10; void load()
  }
}, { immediate: true })
watch(currentActor, () => { clear(); emit('close') })
onBeforeUnmount(clear)
</script>

<template>
  <BootstrapModal :loading="loading" :open="open" :title="`选择${label}`" size="xl" scrollable fullscreen-mobile fill-height :busy="confirming" body-class="p-0 mx-3 overflow-auto" @close="emit('close')">
    <template #toolbar>
      <form class="mx-3 mb-3" :aria-label="`${label}查询`" :inert="confirming" @submit.prevent="search">
        <div class="row gx-3 gy-2 align-items-start">
          <div class="col-12 col-xl">
            <div class="row gx-3 gy-2 align-items-center">
              <div class="col-12 col-sm-6 d-flex align-items-center gap-2"><label :for="`${prefix}-search-field`" class="col-form-label text-nowrap w-sm flex-shrink-0">查询内容</label><select :id="`${prefix}-search-field`" v-model="filters.searchField" class="form-select"><option v-for="field in testBasisSearchFields" :key="field.key" :value="field.key">{{ field.label }}</option></select></div>
              <div class="col-12 col-sm-6 d-flex align-items-center gap-2"><label :for="`${prefix}-contains`" class="col-form-label text-nowrap w-sm flex-shrink-0">包含</label><input :id="`${prefix}-contains`" v-model="filters.contains" class="form-control" size="1" maxlength="200" /></div>
            </div>
            <div v-if="more" :id="`${prefix}-more-filters`" class="row gx-3 gy-2 align-items-center mt-1">
              <div class="col-12 col-sm-6 d-flex align-items-center gap-2"><label :for="`${prefix}-qualification`" class="col-form-label text-nowrap w-sm flex-shrink-0">标准资质类别</label><select :id="`${prefix}-qualification`" v-model="filters.qualification" class="form-select"><option value="">全部</option><option v-for="qualification in result.qualifications" :key="qualification">{{ qualification }}</option></select></div>
              <div class="col-12 col-sm-6 d-flex align-items-center gap-2"><label :for="`${prefix}-department`" class="col-form-label text-nowrap w-sm flex-shrink-0">类别</label><select :id="`${prefix}-department`" v-model="filters.departmentCategory" class="form-select"><option value="">全部</option><option v-for="category in result.departmentCategories" :key="category">{{ category }}</option></select></div>
            </div>
          </div>
          <div class="col-12 col-xl-auto d-flex flex-wrap align-items-center gap-1">
            <div class="form-check mb-0 me-2 align-self-center"><input :id="`${prefix}-own`" v-model="filters.ownDepartment" class="form-check-input" type="checkbox" /><label :for="`${prefix}-own`" class="form-check-label">本部门标准</label></div>
            <button class="btn btn-primary" type="submit">查询</button><button class="btn btn-link" type="button" :aria-expanded="more" :aria-controls="`${prefix}-more-filters`" @click="more = !more">更多筛选<span v-if="activeFilters">（{{ activeFilters }}）</span><i :class="more ? 'ti ti-chevron-up' : 'ti ti-chevron-down'" aria-hidden="true"></i></button>
          </div>
        </div>
      </form>
    </template>
    <ErrorNotice :error="error" retry @retry="load(result.page)" />
    <p v-if="loading" class="text-muted text-center py-4" role="status">正在查询{{ label }}…</p>
    <table v-else-if="!error" class="table table-striped table-hover table-nowrap align-middle mb-0" :aria-label="`可选${label}列表`" :inert="confirming">
      <thead class="table-light"><tr><th scope="col"><input class="form-check-input" type="checkbox" :aria-label="`全选本页${label}`" :checked="allChecked" :indeterminate="someChecked && !allChecked" :disabled="!result.items.length || (!allChecked && !canSelectPage)" @change="choosePage" /></th><th scope="col">受控号</th><th scope="col">标准资质类别</th><th scope="col">标准编号</th><th scope="col">标准名称</th><th scope="col">类别</th><th scope="col">存放地点</th><th scope="col">实施日期</th><th scope="col">作废日期</th><th scope="col">延期时间（天）</th><th scope="col">替换标准号</th><th scope="col">备注</th></tr></thead>
      <tbody><tr v-for="row in result.items" :key="row.id" :class="{ 'table-active': selectedIds.includes(row.id) }"><td><input class="form-check-input" type="checkbox" :aria-label="`选择 ${row.code}`" :checked="selectedIds.includes(row.id)" :disabled="!selectedIds.includes(row.id) && selectedIds.length >= maxTestBasisSelection" @click.stop @change="choose(row)" /></td><td>{{ row.controlNumber }}</td><td>{{ row.qualification }}</td><td>{{ row.code }}</td><td>{{ row.name }}</td><td>{{ row.category }}</td><td>{{ row.location }}</td><td>{{ row.implementedDate || '—' }}</td><td>{{ row.revokedDate || '—' }}</td><td>{{ row.extensionDays ?? '—' }}</td><td>{{ row.replacementCode || '—' }}</td><td>{{ row.notes || '—' }}</td></tr><tr v-if="!result.items.length"><td colspan="12" class="text-center text-muted py-5">没有符合条件的{{ label }}</td></tr></tbody>
    </table>
    <template #pagination><div :inert="loading || confirming || !!error"><TablePagination :label="label" :total="result.total" :page="result.page" :page-size="result.pageSize" :sizes="[10, 20, 50]" extended @page="load" @size="resize" /></div></template>
    <template #footer>
      <div v-if="confirmError" class="w-100"><ErrorNotice :error="confirmError" /></div>
      <span class="me-auto text-muted">已选 {{ selectedIds.length }} 项<span v-if="selectedIds.length >= maxTestBasisSelection">（已达上限）</span></span>
      <div class="form-check mb-0 me-2"><input :id="`${prefix}-english`" v-model="english" class="form-check-input" type="checkbox" :disabled="confirming" /><label :for="`${prefix}-english`" class="form-check-label">英文书名号</label></div>
      <button class="btn btn-light" type="button" :disabled="confirming" @click="emit('close')">取消</button><button class="btn btn-primary" type="button" :disabled="loading || confirming || !!error" @click="confirm">{{ confirming ? '正在确认…' : '确定' }}</button>
    </template>
  </BootstrapModal>
</template>
