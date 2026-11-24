<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { platformRequest } from '../../services/platform/http'
import { profile } from '../../services/platform/auth'
import CustomerPicker from '@/components/CustomerPicker.vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import { copy, changes, type Correction, type Value } from '../../services/platform/correctionFields'
const modules = ref<{ key: string; label: string }[]>([]), kind = ref('contracts')
const keyword = ref(''), page = ref(1), total = ref(0), rows = ref<{ id: string; label: string; status: string }[]>([])
const loading = ref(false), saving = ref(false), error = ref(''), saved = ref(''), editError = ref('')
const selected = ref(''), record = ref<Correction>(), draft = ref<Record<string, Value>>({})
const reason = ref(''), confirmed = ref(false), reviewing = ref(false), fieldSearch = ref('')
let controller: AbortController | undefined, epoch = 0, timer: ReturnType<typeof setTimeout> | undefined
const readOnly = computed(() => !!profile.value?.features?.businessReadOnly)
const changed = computed(() => record.value ? changes(record.value, draft.value) : {})
const count = computed(() => Object.keys(changed.value).length)
const visibleFields = computed(() => record.value?.fields.filter(f => !fieldSearch.value || f.label.includes(fieldSearch.value.trim())) || [])
const formFields = computed(() => visibleFields.value.filter(f => f.type !== 'object'))
async function search(reset = false) {
  clearTimeout(timer)
  if (reset) page.value = 1
  controller?.abort(); controller = new AbortController()
  const current = ++epoch; loading.value = true; error.value = ''; rows.value = []
  try {
    const result = await platformRequest<{ rows: typeof rows.value; total: number }>(`/api/erp-content/${kind.value}?keyword=${encodeURIComponent(keyword.value)}&page=${page.value}`, { signal: controller.signal })
    if (current === epoch) { rows.value = result.rows; total.value = result.total }
  } catch (e) { if (current === epoch && !controller.signal.aborted) error.value = e instanceof Error ? e.message : '加载失败，请重试' }
  finally { if (current === epoch) loading.value = false }
}
watch(keyword, () => { clearTimeout(timer); timer = setTimeout(() => search(true), 300) })
watch(kind, () => { keyword.value = ''; search(true) })
async function open(id: string) {
  if (saving.value) return
  selected.value = id; record.value = undefined; editError.value = ''; saved.value = ''
  reviewing.value = false; reason.value = ''; confirmed.value = false; fieldSearch.value = ''
  try {
    record.value = await platformRequest<Correction>(`/api/erp-content/${kind.value}/${encodeURIComponent(id)}`)
    draft.value = copy(record.value.values)
  } catch (e) { editError.value = e instanceof Error ? e.message : '读取失败，请关闭后重试' }
}
function close() {
  if (!saving.value && (!count.value || window.confirm('修改尚未保存，确定关闭吗？'))) {
    selected.value = ''; record.value = undefined
  }
}
async function save() {
  if (!record.value || saving.value || !confirmed.value || !count.value || readOnly.value) return
  if (reason.value.trim().length < 2) { editError.value = '请填写修改说明（至少2字）'; return }
  saving.value = true; editError.value = ''
  try {
    const result = await platformRequest<{ message: string }>(`/api/erp-content/${kind.value}/${encodeURIComponent(selected.value)}`, {
      method: 'PUT', body: { revision: record.value.revision, changes: changed.value, confirmed: true, reason: reason.value.trim() },
    })
    saved.value = result.message; selected.value = ''; record.value = undefined; await search()
  } catch (e) { editError.value = e instanceof Error ? e.message : '保存失败，当前输入已保留' }
  finally { saving.value = false }
}
onMounted(async () => {
  try { modules.value = (await platformRequest<{ modules: typeof modules.value }>('/api/erp-content/catalog')).modules; await search() }
  catch (e) { error.value = e instanceof Error ? e.message : '无法读取修订权限' }
})
onBeforeUnmount(() => { epoch++; controller?.abort(); clearTimeout(timer) })
</script>
<template>
  <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
    <div><h4 class="mb-1">外部ERP内容管理</h4><p class="text-muted mb-0">维护外部ERP合同和客户；业务表单通过搜索选择使用修订后的资料。</p></div>
    <RouterLink class="btn btn-light" to="/dashboard">返回首页</RouterLink>
  </div>
  <div v-if="saved" class="alert alert-success" role="status">{{ saved }}</div>
  <div v-if="readOnly" class="alert alert-warning">平台正在只读维护，暂不能保存修改。</div>
  <div class="card">
    <div class="card-body">
      <form class="row g-3 align-items-end" @submit.prevent="search(true)">
        <div class="col-md-3"><label class="form-label" for="correction-module">数据类别</label><select id="correction-module" v-model="kind" class="form-select"><option v-for="module in modules" :key="module.key" :value="module.key">{{ module.label }}</option></select></div>
        <div class="col-md"><label class="form-label" for="correction-search">编号或名称</label><input id="correction-search" v-model="keyword" class="form-control" maxlength="200" placeholder="输入后自动筛选，也可点击搜索" /></div>
        <div class="col-md-auto"><button class="btn btn-primary" type="submit" :disabled="loading"><i class="ti ti-search me-1" aria-hidden="true"></i>搜索</button></div>
      </form>
      <div v-if="error" class="alert alert-danger mt-3" role="alert">{{ error }} <button class="btn btn-sm btn-light ms-2" @click="search()">重试</button></div>
    </div>
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0"><thead class="table-light"><tr><th scope="col">外部ERP资料</th><th scope="col">状态／部门</th><th scope="col" class="text-end">操作</th></tr></thead><tbody>
        <tr v-for="row in rows" :key="row.id"><td class="text-break">{{ row.label }}</td><td>{{ row.status || '—' }}</td><td class="text-end"><button class="btn btn-sm btn-outline-primary text-nowrap" :disabled="readOnly" @click="open(row.id)"><i class="ti ti-edit me-1" aria-hidden="true"></i>管理员修订</button></td></tr>
        <tr v-if="!rows.length"><td colspan="3" class="text-center text-muted py-5">{{ loading ? '正在查询…' : error ? '未能加载数据' : '没有匹配的记录' }}</td></tr>
      </tbody></table>
    </div>
    <div class="card-body d-flex flex-wrap justify-content-between align-items-center gap-2"><span class="text-muted">共 {{ total }} 条，每页 20 条</span><div class="d-flex gap-2 align-items-center"><button class="btn btn-light btn-sm" :disabled="loading || page <= 1" @click="page--; search()">上一页</button><span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span><button class="btn btn-light btn-sm" :disabled="loading || page * 20 >= total" @click="page++; search()">下一页</button></div></div>
  </div>
  <BootstrapModal :open="!!selected" :title="reviewing ? '确认管理员修订' : '管理员修订'" size="xl" scrollable fullscreen-mobile :busy="saving" @close="close">
    <p v-if="!record && !editError" class="text-muted">正在读取记录…</p>
    <div v-if="editError" class="alert alert-danger" role="alert">{{ editError }}</div>
    <template v-if="record">
      <h6 class="text-break">{{ record.label }}</h6>
      <div class="alert alert-warning" role="note">{{ record.warning }}</div>
      <template v-if="!reviewing">
        <label for="correction-field-search" class="form-label">查找表单项目</label><input id="correction-field-search" v-model="fieldSearch" class="form-control mb-3" placeholder="输入项目名称，如所属部门" />
        <div class="row g-3"><div v-for="field in formFields" :key="field.key" class="col-md-6"><label :for="kind === 'contracts' && field.key === 'client' ? undefined : `source-${field.key}`" class="form-label">{{ field.label }}</label><CustomerPicker v-if="kind === 'contracts' && field.key === 'client'" :model-value="String(draft[field.key] ?? '')" label="合同客户" :disabled="saving || readOnly" @update:model-value="draft[field.key] = $event" /><select v-else-if="field.key === 'enabled'" :id="`source-${field.key}`" v-model="draft[field.key]" class="form-select" :disabled="saving"><option value="1">启用</option><option value="0">禁用</option></select><input v-else :id="`source-${field.key}`" v-model="draft[field.key]" class="form-control" :maxlength="field.maxLength" :disabled="saving" /></div></div>
      </template>
      <template v-else>
        <p>将保存以下 {{ count }} 个项目的修改：</p>
        <div class="table-responsive mb-3"><table class="table table-bordered"><thead><tr><th>项目</th><th>修改前</th><th>修改后</th></tr></thead><tbody><tr v-for="field in record.fields.filter(f => f.key in changed)" :key="field.key"><th>{{ field.label }}</th><td class="text-break">{{ record.values[field.key] || '（空）' }}</td><td class="text-break">{{ draft[field.key] || '（空）' }}</td></tr></tbody></table></div>
        <label for="correction-reason" class="form-label">修改说明 <span class="text-danger">*</span></label>
        <textarea id="correction-reason" v-model="reason" class="form-control mb-3" rows="3" maxlength="300" :disabled="saving" placeholder="说明修改原因，便于后续核对"></textarea>
        <div class="form-check"><input id="correction-confirm" v-model="confirmed" class="form-check-input" type="checkbox" :disabled="saving" /><label for="correction-confirm" class="form-check-label">已核对修改内容，确认使用管理员权限保存</label></div>
      </template>
    </template>
    <template #footer><button class="btn btn-light" :disabled="saving" @click="reviewing ? reviewing = false : close()">{{ reviewing ? '返回修改' : '关闭' }}</button><button v-if="!reviewing" class="btn btn-primary" :disabled="!record || !count || readOnly" @click="reviewing = true; confirmed = false; editError = ''">核对修改（{{ count }}）</button><button v-else class="btn btn-primary" :disabled="saving || !confirmed || !count || readOnly" @click="save">{{ saving ? '正在保存…' : '确认保存' }}</button></template>
  </BootstrapModal>
</template>
