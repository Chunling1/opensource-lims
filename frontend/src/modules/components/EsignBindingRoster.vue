<template>
  <el-dialog v-model="open" title="全员电子签署绑定管理" width="1100px" append-to-body>
    <el-alert :closable="false" type="info" title="手机号、实名绑定和签署权限是三件事。此处只管理身份；审核、批准和用章权限仍在账号权限及项目流程中单独配置。同步不会发短信或发起签署。" />
    <div class="toolbar d-flex flex-wrap gap-2 mb-3"><el-input v-model="keyword" clearable placeholder="姓名 / 账号" @keyup.enter="search" /><el-select v-model="status" clearable placeholder="全部绑定状态"><el-option v-for="(label, key) in labels" :key="key" :value="key" :label="label" /></el-select><el-button :loading="loading" @click="search">查询 / 刷新</el-button></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-table :data="rows" v-loading="loading" border row-key="rowKey" max-height="480">
      <el-table-column prop="userName" label="姓名" width="110" /><el-table-column prop="account" label="账号" width="130" />
      <el-table-column prop="psnAccountMasked" label="绑定手机号" width="130" /><el-table-column label="绑定状态" width="130"><template #default="{ row }">{{ labels[row.status] || row.status }}{{ row.enabled || row.status === 'no_account' ? '' : '（账号停用）' }}</template></el-table-column>
      <el-table-column prop="lastCheckedAt" label="最后同步" min-width="160" />
      <el-table-column label="操作" min-width="210"><template #default="{ row }"><el-button link :disabled="!!working || !row.enabled || row.status === 'unbound' || row.status === 'disabled'" @click="act(row, 'sync')">同步实名状态</el-button><el-button link :disabled="!!working || !row.enabled" @click="act(row, 'rebind')">{{ row.status === 'unbound' ? '绑定名册手机号' : '重新绑定' }}</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="50" layout="total, prev, pager, next" @current-change="load" />
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchBindingRoster, maintainBinding } from '@/services/reportAssurance'
import type { EsignBinding } from '@/services/esign'
const open = defineModel<boolean>({ default: false })
const labels: Record<string, string> = { unbound: '未绑定', pending: '待认证 / 认证中', verified: '已绑定并实名', invalid: '实名已失效 / 待核实', disabled: '已停用', no_account: '尚未关联登录账号' }
const keyword = ref(''), status = ref(''), error = ref(''), page = ref(1), total = ref(0), loading = ref(false), working = ref('')
const rows = ref<(EsignBinding & { enabled: boolean })[]>([])
let generation = 0
async function load() { const id = ++generation; loading.value = true; error.value = ''; try { const data = await fetchBindingRoster(keyword.value, status.value, page.value); if (id === generation) { rows.value = data.rows; total.value = data.total } } catch (e) { if (id === generation) error.value = e instanceof Error ? e.message : '读取失败' } finally { if (id === generation) loading.value = false } }
function search() { page.value = 1; void load() }
async function act(row: EsignBinding, action: 'sync' | 'rebind') {
  if (working.value) return
  if (action === 'rebind') { try { await ElMessageBox.confirm(`确认重新使用${row.userName}的名册手机号？将重置本地实名状态，不授予签署权限；有在途签署时会拒绝操作。`, '确认身份绑定', { type: 'warning' }) } catch { return } }
  working.value = `${row.userId}:${action}`
  try { await maintainBinding(row.userId, action); ElMessage.success(action === 'sync' ? '实名状态已同步' : '已保存待认证绑定'); await load() } catch (e) { ElMessage.error(e instanceof Error ? e.message : '操作失败') } finally { working.value = '' }
}
watch(open, value => { if (value) search(); else ++generation })
</script>

