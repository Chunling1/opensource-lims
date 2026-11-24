<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useSessionStore } from '@/stores/session'
import { fetchPendingStages, getEsignSignUrl, refreshMyEsignTask, resumeEsignStage, type StageTask } from '@/services/esign'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
const session = useSessionStore()
const rows = ref<StageTask[]>([]), open = ref(false), busy = ref(false), error = ref('')
const seen = new Set<string>()
const links = ref<Record<string, string>>({})
const taskKey = (row: StageTask) => JSON.stringify([session.account, row.id, row.myRole])
async function load(force = false) {
  if (!session.account || !session.stageSigning || session.businessReadOnly || busy.value) return
  busy.value = true
  const account = session.account
  try {
    const result = await fetchPendingStages()
    if (account !== session.account) return
    rows.value = result
    const keys = new Set(result.map(taskKey))
    links.value = Object.fromEntries(Object.entries(links.value).filter(([key]) => keys.has(key)))
    const fresh = result.some(row => !seen.has(taskKey(row)))
    if (rows.value.length && (force || fresh)) {
      open.value = true
      rows.value.forEach(row => seen.add(taskKey(row)))
    }
    if (!rows.value.length) open.value = false
    error.value = ''
  } catch (e) { if (force) { error.value = e instanceof Error ? e.message : '签署任务读取失败'; open.value = true } }
  finally { busy.value = false }
}
async function prepare(row: StageTask) {
  if (busy.value) return
  busy.value = true; error.value = ''
  const account = session.account
  try {
    const result = await resumeEsignStage(row.id)
    if (account !== session.account) return
    if (result.esignPrepareError) throw new Error(result.esignPrepareError)
    const link = await getEsignSignUrl(row.id)
    if (account !== session.account) return
    const url = link.shortUrl || link.url
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:' || !(parsed.hostname === 'esign.cn' || parsed.hostname.endsWith('.esign.cn'))) throw new Error('签署入口不是e签宝受信任地址')
    links.value[taskKey(row)] = url
  } catch (e) { if (account === session.account) error.value = e instanceof Error ? e.message : '签署入口准备失败' }
  finally { busy.value = false }
}
async function refresh() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    for (const id of new Set(rows.value.filter(r => r.providerFlowId).map(r => r.id))) await refreshMyEsignTask(id)
  } catch (e) { error.value = e instanceof Error ? e.message : '回执核对失败' }
  finally { busy.value = false }
  if (!error.value) await load(true)
}
function confirmed() { void load(true) }
function focused() { if (open.value) { void refresh(); return } void load() }
watch(() => session.account, () => { rows.value = []; links.value = {}; open.value = false; seen.clear(); void load() })
onMounted(() => { void load(); window.addEventListener('esign-stage-confirmed', confirmed); window.addEventListener('focus', focused) })
onBeforeUnmount(() => { window.removeEventListener('esign-stage-confirmed', confirmed); window.removeEventListener('focus', focused) })
</script>
<template>
  <BootstrapModal :open="open" title="本节点待本人电子签署" @close="open = false">
    <p>业务确认已保存。本人签署成功后系统才流转到下一节点；审核、批准人员须各自先完成系统确认。</p>
    <p>可在电脑打开e签宝网页签署，也可在该页面切换微信／e签宝，由本人扫码在手机签署。</p>
    <p v-if="error" class="alert alert-danger" role="alert">{{ error }}</p>
    <ul class="list-unstyled">
      <li v-for="row in rows" :key="`${row.id}:${row.myRole}`" class="border rounded p-3 mb-2">
        <strong>{{ row.reportNo }}</strong> · {{ row.myRole }}
        <p v-if="row.errorMessage" class="text-danger">{{ row.errorMessage }}</p>
        <div class="mt-2">
          <a v-if="links[taskKey(row)]" :href="links[taskKey(row)]" target="_blank" rel="noopener noreferrer" class="btn btn-primary">打开本人签署页</a>
          <button v-else type="button" class="btn btn-primary" :disabled="busy" @click="prepare(row)">准备本人签署入口</button>
        </div>
      </li>
    </ul>
    <template #footer>
      <button type="button" class="btn btn-light" @click="open = false">稍后签署</button>
      <button type="button" class="btn btn-primary" :disabled="busy" @click="refresh">我已签署，核对状态</button>
    </template>
  </BootstrapModal>
</template>
