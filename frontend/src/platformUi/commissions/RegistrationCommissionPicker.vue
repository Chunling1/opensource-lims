<script setup lang="ts">
import { ref, watch, onBeforeUnmount } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import TablePagination from '../../components/common/table/TablePagination.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import { inject } from 'vue'
const registrationDemo = inject<any>('platform-registration-services')!
if (!registrationDemo) throw Error('缺少平台表单服务')
import { currentActor } from '../../stores/session'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { RegistrationCommissionRow, RegistrationPage } from '../../types/commissions/registration'
const props = defineProps<{ open: boolean; ids?: string[] }>()
const emit = defineEmits<{ close: []; select: [string] }>()
const keyword = ref(''), applied = ref(''), loading = ref(false), error = ref<ErrorValue>('')
const result = ref<RegistrationPage<RegistrationCommissionRow>>({ items: [], total: 0, page: 1, pageSize: 5 })
let controller: AbortController | undefined, sequence = 0
async function load(page = 1) {
  controller?.abort(); const active = controller = new AbortController(), token = ++sequence
  loading.value = true; error.value = ''; result.value.items = []
  try { const data = await registrationDemo.commissions({ keyword: applied.value, eligibleOnly: true, ids: props.ids, page, pageSize: 5, sort: 'createdAt', direction: 'desc' }, active.signal); if (token === sequence) result.value = data }
  catch (e) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(e) }
  finally { if (token === sequence) loading.value = false }
}
function search() { applied.value = keyword.value.trim(); void load() }
watch(() => props.open, open => { if (open) { keyword.value = ''; applied.value = ''; void load() } else { sequence++; controller?.abort(); result.value.items = [] } })
watch(currentActor, () => { sequence++; controller?.abort(); result.value.items = []; emit('close') })
onBeforeUnmount(() => { sequence++; controller?.abort() })
</script>
<template><BootstrapModal :loading="loading" :open="open" title="选择所属委托" @close="emit('close')"><template #toolbar><form class="d-flex gap-2 mb-3" aria-label="搜索所属委托" @submit.prevent="search"><input v-model="keyword" class="form-control" placeholder="委托编号、名称或单位" aria-label="搜索委托" maxlength="200" /><button class="btn btn-primary" type="submit">查询</button></form><p class="text-muted">仅显示可关联的未完成委托。</p></template><ErrorNotice :error="error" retry @retry="load(result.page)" /><template v-if="!error"><div class="list-group"><button v-for="row in result.items" :key="row.id" type="button" class="list-group-item list-group-item-action" :aria-label="`选择 ${row.code}`" @click="emit('select', row.id)"><strong>{{ row.code }}</strong><div class="text-break">{{ row.name }}</div><small class="text-muted">{{ row.customer }} · {{ row.status }}</small></button></div><p v-if="!result.items.length" class="text-muted">没有符合条件的委托。</p><TablePagination label="可选委托" :total="result.total" :page="result.page" :page-size="5" :sizes="[5]" @page="load" @size="load(1)" /></template><template #footer><button class="btn btn-light" @click="emit('close')">关闭</button></template></BootstrapModal></template>
