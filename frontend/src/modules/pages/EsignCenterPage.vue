<template>
  <ModuleWorkspace
    title="我的签署"
    area-name="检测管理信息服务"
    module-name="报告管理"
    :path="route.path"
    :pages="pages"
    active-key="signing"
    :show-command="false"
    :show-content="false"
  >
    <div >
      <el-card shadow="never" >
        <template #header><div class="card-title"><strong>电子签署身份</strong><el-tag :type="bindingType">{{ bindingLabel }}</el-tag></div></template>
        <div class="row g-3">
          <span class="col-12 col-md-6">系统账号</span><strong class="col-12 col-md-6">{{ binding?.account || session.account }}</strong>
          <span class="col-12 col-md-6">签署姓名</span><strong class="col-12 col-md-6">{{ binding?.legalName || session.userName }}</strong>
          <span class="col-12 col-md-6">e签宝账号</span><strong class="col-12 col-md-6">{{ binding?.psnAccountMasked || '尚未绑定' }}</strong>
        </div>
        <el-alert type="info" :closable="false" title="名册手机号不等于已实名。可确认名册手机号建立绑定；实名和签署仍由本人在e签宝完成。" />
        <RosterBindingButton v-if="binding?.status === 'unbound'" :disabled="session.businessReadOnly" @bound="reload" />
      </el-card>
      <ModuleCommandBar :count-label="`待签 ${pending.length} 项`" :show-search="false">
        <template #actions>
          <el-button @click="reload">刷新</el-button>
          <el-button v-if="canManageBindings" @click="rosterOpen = true">全员绑定管理</el-button>
          <el-button type="primary" :disabled="!selectedIds.length || session.businessReadOnly" :loading="opening" @click="openBatch">批量签署已选 {{ selectedIds.length }} 份</el-button>
        </template>
      </ModuleCommandBar>
      <ModuleContentCard title="电子签发任务" description="仅显示当前登录人员本人承担的主检、审核或批准签署任务">
        <el-table :data="tasks" border height="100%" row-key="id" v-loading="loading" @selection-change="selectTasks">
          <el-table-column type="selection" width="48" :selectable="canSign" />
          <el-table-column prop="reportNo" label="报告编号" min-width="180" />
          <el-table-column prop="myRole" label="本人角色" width="100" />
          <el-table-column label="签发状态" width="120"><template #default="{ row }"><el-tag>{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
          <el-table-column label="本人状态" width="110"><template #default="{ row }"><el-tag :type="row.myStatus === 'signed' ? 'success' : 'warning'">{{ signerStatus(row.myStatus) }}</el-tag></template></el-table-column>
          <el-table-column prop="createdAt" label="进入签发时间" width="180" />
          <el-table-column label="处理结果 / 失败原因" min-width="250"><template #default="{ row }">{{ row.myStatus === 'signed' ? '本人已完成，不重复发起' : row.errorMessage || outcomes[row.id] || '' }}</template></el-table-column>
          <el-table-column label="操作" width="140"><template #default="{ row }"><el-button v-if="row.status === 'signing' && row.myStatus !== 'signed'" type="primary" link @click="openSingle(row)">去签署</el-button><span v-else>—</span></template></el-table-column>
          <template #empty><el-empty description="当前没有电子签署任务" /></template>
        </el-table>
      </ModuleContentCard>
    </div>
    <EsignBindingRoster v-if="canManageBindings" v-model="rosterOpen" />
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, onBeforeUnmount } from 'vue'
import EsignBindingRoster from '@/components/EsignBindingRoster.vue'
import { selectedSignableIds, canSignTask, groupSignTasks } from '@/composables/esignBatch'
import { selectedBatchSignUrl } from '@/services/reportAssurance'
import RosterBindingButton from '@/components/RosterBindingButton.vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import ModuleCommandBar from '@/components/ModuleCommandBar.vue'
import ModuleContentCard from '@/components/ModuleContentCard.vue'
import { modules } from '@/data/modules'
import { fetchMyEsignBinding, fetchMyEsignTasks, getEsignSignUrl, type EsignBinding, type EsignFlow } from '@/services/esign'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const session = useSessionStore()
const pages = computed(() => modules.find((row) => row.key === 'report')?.pages ?? [])
const binding = ref<EsignBinding | null>(null)
const tasks = ref<EsignFlow[]>([])
const loading = ref(false)
const opening = ref(false)
const rosterOpen = ref(false), selectedIds = ref<number[]>([]), outcomes = ref<Record<number, string>>({})
const canManageBindings = computed(() => session.roleKey === 'admin' || session.canAction('quality.personnel.update'))
const canSign = (row: EsignFlow) => !session.businessReadOnly && canSignTask(row)
function selectTasks(rows: EsignFlow[]) { selectedIds.value = selectedSignableIds(rows) }
const pending = computed(() => tasks.value.filter((row) => row.status === 'signing' && row.myStatus !== 'signed'))
const bindingLabel = computed(() => ({ verified: '已实名', pending: '待认证 / 认证中', disabled: '已停用', invalid: '实名失效 / 待核实', unbound: '未绑定' } as Record<string, string>)[binding.value?.status || 'unbound'])
const bindingType = computed(() => binding.value?.status === 'verified' ? 'success' : binding.value?.status === 'disabled' ? 'danger' : 'warning')
function statusLabel(status: string) { return ({ signing: '签署中', completed: '已完成', verified: '已验签', binding_required: '待绑定', ready: '待发起', failed: '失败', cancelled: '已撤销', expired: '已过期', rejected: '已拒签' } as Record<string, string>)[status] ?? status }
function signerStatus(status?: string) { return ({ signed: '已签', pending: '待签', binding_required: '待绑定', failed: '失败' } as Record<string, string>)[status || ''] ?? status ?? '—' }
function safeOpen(url: string) { if (!/^https:\/\//i.test(url)) throw new Error('签署地址不是受信任的HTTPS链接'); window.open(url, '_blank', 'noopener,noreferrer') }
async function reload() { loading.value = true; try { const [identity, rows] = await Promise.all([fetchMyEsignBinding(), fetchMyEsignTasks()]); binding.value = identity; tasks.value = groupSignTasks(rows); selectedIds.value = selectedIds.value.filter(id => tasks.value.some(row => row.id === id && canSign(row))) } catch (e) { ElMessage.error(e instanceof Error ? e.message : '签署任务加载失败') } finally { loading.value = false } }
async function openSingle(row: EsignFlow) { if (opening.value || !canSign(row)) return; opening.value = true; try { const link = await getEsignSignUrl(row.id); safeOpen(link.url || link.shortUrl); outcomes.value[row.id] = '签署入口已打开；等待本人操作及回调确认' } catch (e) { outcomes.value[row.id] = e instanceof Error ? e.message : '获取签署入口失败'; ElMessage.error(outcomes.value[row.id]) } finally { opening.value = false } }
async function openBatch() {
  if (opening.value || session.businessReadOnly) return
  const ids = selectedSignableIds(tasks.value.filter(row => selectedIds.value.includes(row.id)))
  if (!ids.length) return
  opening.value = true
  try { const link = await selectedBatchSignUrl(ids); safeOpen(link.url || link.shortUrl); ids.forEach(id => { outcomes.value[id] = link.flowIds.includes(id) ? '批量入口已打开；实际进度以刷新后的本人状态为准' : '未加入本批次：状态、权限或签署顺序已变化，请刷新核对' }) }
  catch (e) { const message = e instanceof Error ? e.message : '获取批量入口失败'; ids.forEach(id => { outcomes.value[id] = `入口获取失败：${message}；可重新选择重试` }); ElMessage.error(message) }
  finally { opening.value = false }
}
function refreshAfterSigning() { if (!document.hidden && !loading.value) void reload() }
onMounted(() => { void reload(); window.addEventListener('focus', refreshAfterSigning) })
onBeforeUnmount(() => window.removeEventListener('focus', refreshAfterSigning))
</script>


