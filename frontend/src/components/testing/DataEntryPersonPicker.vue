<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import PersonPickerFrame from './PersonPickerFrame.vue'
import ErrorNotice from '../common/ErrorNotice.vue'
import SingleChoice from '../common/SingleChoice.vue'
import TablePagination from '../common/table/TablePagination.vue'
import { registrationDemo } from '../../services/commissions/registrationApi'
import { normalizeError, type ErrorValue } from '../../services/common/errors'
import type { ReportStage } from '../../types/reports/reportCheck'
import type { ReportChangeSource } from '../../types/reports/reportChange'
import { currentActor } from '../../stores/session'
import type { EntryPersonRole, EntryPeopleScope, EntryPeoplePage, EntryPerson, EntryPersonCandidate } from '../../types/testing/dataEntryDetail'

const props = defineProps<{ sampleId: string; role: EntryPersonRole; title: string; value?: EntryPerson; initialScope?: EntryPeopleScope; excludeId?: string; purpose?: 'report-check' | 'report-change' | 'personnel' | 'reference-material'; reportStage?: ReportStage; changeSource?: ReportChangeSource; embedded?: boolean }>()
const emit = defineEmits<{ close: []; select: [EntryPersonCandidate]; scope: [EntryPeopleScope] }>()
const userPicker = computed(() => props.purpose === 'personnel' || props.purpose === 'reference-material')
const scopes = computed(() => ([{ key: 'preset', label: '方案预设人员' }, { key: 'department', label: '本部门人员' }, { key: 'all', label: '所有人员' }] as const).filter(item => props.purpose !== 'report-change' || item.key !== 'preset'))
const scope = ref(props.initialScope), keyword = ref(''), applied = ref(''), pageSize = ref(10), requestedPage = ref(1)
const userFilters = reactive({ account: '', name: '', certificateNumber: '' }), appliedUsers = ref({ ...userFilters })
const userFields = [{ key: 'account', label: '用户账号' }, { key: 'name', label: '姓名' }, { key: 'certificateNumber', label: '上岗证号' }] as const
const result = ref<EntryPeoplePage>(), selected = ref<EntryPerson | undefined>(props.value), loading = ref(false), confirming = ref(false), error = ref<ErrorValue>('')
let controller: AbortController | undefined, sequence = 0
function cancel() { sequence++; controller?.abort(); loading.value = false; confirming.value = false }
async function load(page = 1) {
  cancel(); const token = sequence, active = controller = new AbortController()
  requestedPage.value = page; loading.value = true; error.value = ''
  try {
    const query = { role: props.role, scope: scope.value, keyword: applied.value, page, pageSize: pageSize.value, excludeId: props.excludeId }
    const data = await (userPicker.value ? (props.purpose === 'reference-material' ? registrationDemo.materialPeople : registrationDemo.personnelUsers)({ ...appliedUsers.value, page, pageSize: pageSize.value }, active.signal) : props.purpose === 'report-change' ? registrationDemo.reportChangeHandlers(query, active.signal, props.changeSource) : props.purpose === 'report-check' ? registrationDemo.reportCheckRecipients(props.sampleId, query, active.signal, props.reportStage) : registrationDemo.entryPeople(props.sampleId, query, active.signal))
    if (token !== sequence) return
    result.value = data; scope.value = data.scope; emit('scope', data.scope)
  } catch (issue) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(issue) }
  finally { if (token === sequence) loading.value = false }
}
function search() { applied.value = keyword.value.trim(); appliedUsers.value = { ...userFilters }; void load() }
function changeScope(value: EntryPeopleScope) { scope.value = value; void load() }
function choose(person: EntryPersonCandidate) { if (!loading.value && !confirming.value && !person.disabledReason) selected.value = person }
async function confirm() {
  if (!selected.value || loading.value || confirming.value || error.value) return
  cancel(); const token = sequence, active = controller = new AbortController()
  confirming.value = true; error.value = ''
  try {
    const person = await (userPicker.value ? (props.purpose === 'reference-material' ? registrationDemo.materialPerson : registrationDemo.personnelUser)(selected.value.id, active.signal) : props.purpose === 'report-change' ? registrationDemo.reportChangeHandler(selected.value.id, active.signal, props.changeSource) : props.purpose === 'report-check' ? registrationDemo.reportCheckRecipient(props.sampleId, selected.value.id, active.signal, props.reportStage) : registrationDemo.entryPerson(props.sampleId, { role: props.role, id: selected.value.id, excludeId: props.excludeId }, active.signal))
    if (token === sequence) emit('select', person)
  } catch (issue) { if (token === sequence && !active.signal.aborted) error.value = normalizeError(issue) }
  finally { if (token === sequence) confirming.value = false }
}
function close() { cancel(); emit('close') }
watch(currentActor, close)
onBeforeUnmount(cancel)
void load()
</script>
<template>
  <PersonPickerFrame :loading="loading" :title="title" :embedded="embedded" @close="close">
    <template #toolbar>
      <form class="row gx-3 gy-2 align-items-center px-3 mb-3" aria-label="人员查询" @submit.prevent="search">
        <template v-if="userPicker"><div v-for="f in userFields" :key="f.key" class="col-12 col-md d-flex align-items-center gap-2"><label :for="`personnel-user-${f.key}`" class="col-form-label text-nowrap">{{ f.label }}</label><input :id="`personnel-user-${f.key}`" v-model="userFilters[f.key]" class="form-control" size="1" maxlength="200" :disabled="confirming" /></div></template>
        <template v-else><div class="col-12 col-md-auto d-flex align-items-center gap-2">
          <label for="entry-people-scope" class="col-form-label text-nowrap">人员范围</label>
          <select id="entry-people-scope" class="form-select" :value="scope" :disabled="confirming" @change="changeScope(($event.target as HTMLSelectElement).value as EntryPeopleScope)">
            <option v-for="item in scopes" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </div>
        <div class="col-12 col-md d-flex align-items-center gap-2">
          <label for="entry-people-keyword" class="col-form-label text-nowrap">姓名或工号</label>
          <input id="entry-people-keyword" v-model="keyword" class="form-control" placeholder="请输入姓名或工号" maxlength="200" :disabled="confirming" />
        </div>
        </template><div class="col-auto d-flex gap-1"><button type="submit" class="btn btn-primary" :disabled="confirming">查询</button></div>
      </form>
      <div v-if="!userPicker && result && (purpose !== 'report-change' && !result.presetConfigured || scope === 'department')" class="d-flex flex-wrap gap-2 text-muted small px-3 mb-2">
        <span v-if="purpose !== 'report-change' && !result.presetConfigured">当前检测方案未配置此角色的预设人员。</span>
        <span v-if="scope === 'department'">当前部门：{{ result.departmentName }}</span>
      </div>
    </template>
    <ErrorNotice :error="error" retry :busy="loading || confirming" @retry="load(requestedPage)" />
    <p v-if="loading" class="text-muted text-center py-4" role="status">正在查询人员…</p>
    <div v-else-if="!error" class="table-responsive">
      <table class="table table-hover table-nowrap align-middle fs-6 fw-normal mb-0" aria-label="可选人员列表">
        <thead class="table-light"><tr><th class="p-2" scope="col" aria-label="选择"></th><template v-if="userPicker"><th v-for="label in ['用户账号', '姓名', '邮箱', '电话', '岗位', '上岗证号', '职务']" :key="label" class="p-2" scope="col">{{ label }}</th></template><template v-else><th class="p-2" scope="col">工号</th><th class="p-2" scope="col">姓名</th><th class="p-2" scope="col">所属部门</th><th class="p-2" scope="col">上岗证号</th><th class="p-2" scope="col">联系电话</th></template></tr></thead>
        <tbody><tr v-for="person in result?.items || []" :key="person.id" :class="{ 'bg-primary-subtle': selected?.id === person.id, 'text-muted': person.disabledReason }" :title="person.disabledReason">
          <td class="bg-transparent p-2"><SingleChoice name="entry-person-choice" :value="person.id" :checked="selected?.id === person.id" :disabled="confirming || !!person.disabledReason" :label="`选择 ${person.name}（${person.id}）${person.disabledReason ? `，${person.disabledReason}` : ''}`" @change="choose(person)" /></td>
          <td class="bg-transparent p-2">{{ person.id }}</td><td class="bg-transparent p-2">{{ person.name }}</td><template v-if="userPicker"><td class="bg-transparent p-2">{{ person.email || '—' }}</td><td class="bg-transparent p-2">{{ person.phone || '—' }}</td><td class="bg-transparent p-2">{{ person.position || '—' }}</td><td class="bg-transparent p-2">{{ person.certificateNumber || '—' }}</td><td class="bg-transparent p-2">{{ person.jobTitle || '—' }}</td></template><template v-else><td class="bg-transparent p-2">{{ person.departmentName }}</td><td class="bg-transparent p-2">{{ person.certificateNumber }}</td><td class="bg-transparent p-2">{{ person.phone }}</td></template>
        </tr><tr v-if="!result?.items.length"><td :colspan="userPicker ? 8 : 6" class="text-center text-muted py-4">没有符合条件的人员</td></tr></tbody>
      </table>
    </div>
    <template #pagination><div v-if="result" :inert="loading || confirming || !!error"><TablePagination label="人员" :total="result.total" :page="result.page" :page-size="result.pageSize" :sizes="[10, 20, 50]" @page="load" @size="pageSize = $event; load()" /></div></template>
    <template #footer>
      <span v-if="selected" class="me-auto text-muted text-break">{{ selected.name }}（{{ selected.id }}）</span>
      <button class="btn btn-light" type="button" @click="close">取消</button>
      <button class="btn btn-primary" type="button" :disabled="!selected || loading || confirming || !!error" @click="confirm">{{ confirming ? '正在确认…' : '确定' }}</button>
    </template>
  </PersonPickerFrame>
</template>
