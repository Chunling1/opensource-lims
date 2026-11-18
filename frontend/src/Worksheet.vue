<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { IconArrowLeft } from '@tabler/icons-vue'
import { api, ApiError, reportStates, type Fields, type Sample } from './api'
import ReasonModal from './ReasonModal.vue'
import ReportEditor from './ReportEditor.vue'

const emit = defineEmits<{ expired: []; saved: []; 'dismiss-toast': [] }>()
const route = useRoute(),
  router = useRouter()
const sid = Number(route.params.sid),
  rid = Number(route.params.rid)
const sample = ref<Sample>(),
  report = computed(() => sample.value?.reports.find((r) => r.id === rid))
const pending = ref(false),
  error = ref(''),
  rule = ref(0)
const modalOpen = ref(false),
  operation = ref<'return' | 'transfer'>('return')
const listName =
  route.query.from === 'tasks'
    ? 'tasks'
    : route.query.from === 'samples' || !rid
      ? 'samples'
      : 'reports'
const listQuery = { ...route.query }
delete listQuery.from
let replay: { signature: string; file?: File; key: string } | undefined
function showError(e: unknown) {
  error.value = e instanceof Error ? e.message : String(e)
  if (e instanceof ApiError && e.status === 401) emit('expired')
}
async function load() {
  sample.value = await api<Sample>('samples/' + sid)
  if (!rule.value) rule.value = sample.value.rules[0]?.id ?? 0
  if (rid && !report.value) error.value = '此样品下没有这份报告。'
}
onMounted(async () => {
  try {
    await load()
  } catch (e) {
    showError(e)
  }
})
function clearFeedback() {
  error.value = ''
  emit('dismiss-toast')
}
function openOwner(op: 'return' | 'transfer') {
  operation.value = op
  error.value = ''
  emit('dismiss-toast')
  modalOpen.value = true
}
async function act(action: string, values: Fields = {}) {
  if (!sample.value || pending.value) return false
  pending.value = true
  error.value = ''
  emit('dismiss-toast')
  const version = report.value?.version ?? sample.value.version
  const signature = JSON.stringify([sid, action, version, values])
  const file = values.file instanceof File ? values.file : undefined
  if (replay?.signature !== signature || file !== replay.file)
    replay = { signature, file, key: crypto.randomUUID() }
  const fields: Fields = { ...values, version, requestId: replay.key }
  const body = action === 'upload' ? new FormData() : fields
  if (body instanceof FormData)
    for (const [k, v] of Object.entries(fields)) body.append(k, v instanceof File ? v : String(v))
  try {
    const result = await api<{ reportId: number | null }>('samples/' + sid + '/' + action, body)
    replay = undefined
    modalOpen.value = false
    emit('saved')
    if (action === 'create') {
      await router.push({
        name: 'report',
        params: { sid, rid: result.reportId! },
        query: { ...listQuery, from: listName },
      })
      return true
    }
    if (action === 'transfer' || action === 'return') {
      await router.push({
        name: 'samples',
        query: { ...listQuery, view: action === 'return' ? 'pool' : 'mine' },
      })
      return true
    }
    await load()

    return true
  } catch (e) {
    if (e instanceof ApiError) {
      replay = undefined
      if (e.status === 409) await load()
    }
    showError(e)
    return false
  } finally {
    pending.value = false
  }
}
</script>
<template>
  <div class="page-header mt-0 mb-3">
    <div class="page-pretitle">检测工作</div>
    <div class="d-flex align-items-center flex-wrap gap-3">
      <h1 class="page-title">{{ rid ? '检测报告工作表' : '样品工作表' }}</h1>
      <RouterLink class="btn btn-sm ms-auto" :to="{ name: listName, query: listQuery }"
        ><IconArrowLeft class="icon" />返回{{
          listName === 'tasks' ? '待办' : listName === 'samples' ? '样品' : '报告'
        }}列表</RouterLink
      >
    </div>
  </div>
  <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
  <div v-if="sample?.frozen" class="alert alert-warning" role="alert">
    <div>
      <strong>样品已冻结</strong>
      <div>领取、退回、转交、创建报告、上传文件、送审和取消草稿已暂停。</div>
    </div>
  </div>
  <template v-if="sample">
    <section v-if="rid && report" class="card">
      <div class="card-header">
        <span class="card-title">{{ sample.name }}</span
        ><span class="ms-2 text-secondary">{{ sample.number }} · {{ sample.commission }}</span>
      </div>
      <ReportEditor
        :key="report.id"
        :sample="sample"
        :report="report"
        :act="act"
        :error="error"
        @open-modal="clearFeedback"
        :pending="pending"
      />
    </section>
    <div v-if="!rid" class="row row-cards"
      ><div class="col-lg-7"><section class="card h-100">
        <div class="card-header">
          <h2 class="card-title">{{ sample.name }} · {{ sample.number }}</h2>
        </div>
        <div class="card-body">
          <div class="datagrid">
            <div
              v-for="pair in [
                ['委托编号', sample.commission],
                ['负责人', sample.owner ?? '待领取'],
                ['模板版本', sample.template],
                ['委托日期', sample.commissionDate],
              ]"
              :key="pair[0]"
              class="datagrid-item"
            >
              <div class="datagrid-title">{{ pair[0] }}</div>
              <div class="datagrid-content">{{ pair[1] }}</div>
            </div>
          </div>
        </div>
        <div class="card-body border-top">
          <div class="datagrid-title mb-2">检测项目</div>
          <div class="d-flex flex-wrap gap-2">
            <span v-for="project in sample.projects" :key="project" class="badge bg-blue-lt">{{ project }}</span>
          </div>
        </div>
        <div class="card-footer d-flex gap-2 flex-wrap">
          <template v-for="op in ['claim', 'return', 'transfer'] as const" :key="op"
            ><div v-if="op in sample.actions" :title="sample.actions[op]">
              <button
                class="btn"
                :class="op === 'claim' ? 'btn-primary' : 'btn-outline-secondary'"
                :disabled="pending || !!sample.actions[op]"
                @click="op === 'claim' ? act('claim') : openOwner(op)"
              >
                <span v-if="pending" class="spinner-border spinner-border-sm me-1"></span
                >{{
                  pending
                    ? '处理中…'
                    : op === 'claim'
                      ? '领取样品'
                      : op === 'return'
                        ? '退回待领取池'
                        : '转交'
                }}</button
              ><small class="d-block text-secondary">{{ sample.actions[op] }}</small>
            </div></template
          >
        </div>
      </section></div>
      <div v-if="sample.reports.length || 'create' in sample.actions" class="col-lg-5"><section class="card h-100">
        <div class="card-header"><h2 class="card-title">关联报告</h2></div>
        <table v-if="sample.reports.length" class="table table-vcenter card-table">
          <thead>
            <tr>
              <th>报告编号</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in sample.reports" :key="r.id">
              <td>
                <RouterLink
                  :to="{
                    name: 'report',
                    params: { sid, rid: r.id },
                    query: { ...listQuery, from: listName },
                  }"
                  >{{ r.number }}</RouterLink
                >
              </td>
              <td>
                <span class="badge" :class="r.state === 'review' ? 'bg-teal-lt' : r.state === 'draft' ? 'bg-blue-lt' : 'bg-secondary-lt'">{{
                  reportStates[r.state]
                }}</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="card-body mb-0 text-secondary">此样品还没有报告。</p>
        <form
          v-if="'create' in sample.actions"
          :title="sample.actions.create"
          class="card-footer d-flex gap-2 align-items-center flex-wrap"
          @submit.prevent="act('create', { ruleId: rule })"
        >
          <label for="rule">编号规则</label
          ><select id="rule" v-model="rule" class="form-select w-auto">
            <option v-for="r in sample.rules" :value="r.id" :key="r.id">
              {{ r.prefix }}
            </option></select
          ><button class="btn btn-primary" :disabled="pending || !!sample.actions.create">
            <span v-if="pending" class="spinner-border spinner-border-sm me-1"></span
            >{{ pending ? '处理中…' : '创建报告' }}</button
          ><small>{{ sample.actions.create }}</small>
        </form>
      </section></div>
      <ReasonModal
        v-if="modalOpen"
        :title="operation === 'return' ? '退回待领取池' : '转交负责人'"
        reason-label="办理原因"
        :targets="operation === 'transfer' ? sample.targets : undefined"
        :pending="pending"
        :error="error"
        @close="modalOpen = false"
        @confirm="
          (reason, target) =>
            act(operation, { reason, ...(operation === 'transfer' ? { targetId: target } : {}) })
        "
      /> </div
  ></template>
</template>
