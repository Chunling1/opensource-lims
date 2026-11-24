<template>
  <ModuleWorkspace :title="pageName" :area-name="areaName" :module-name="moduleName" :path="route.path" :pages="pages" :active-key="pageKey" :show-command="false" :show-content="false">

  <el-alert
    v-if="!available"
    type="info"
    :closable="false"
    show-icon
    title="本地演示模式：可查看委托更改工作台，提交动作不会写入任何平台。"
  />

  <div class="row g-3">
    <ReportListPanel
      title="委托更改中"
      :rows="changeRows"
      :selected="selectedNo"
      :search-fields="['reportNo', 'client', 'project']"
      placeholder="报告编号 / 委托单位 / 项目"
      empty-text="暂无委托更改中的单据"
      @select="selectedNo = $event"
    >
      <template #item="{ row }">
        <strong>{{ row.reportNo }}</strong>
        <span>{{ row.client }} / {{ row.project }}</span>
        <small>{{ row.status }}</small>
      </template>
    </ReportListPanel>

    <div class="col-12 col-xl-6">
      <el-card v-if="selected" shadow="never" >
        <template #header>
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
            <strong>委托更改 · 修改后提交完成</strong>
            <el-tag type="warning" size="small">{{ selected.status }}</el-tag>
          </div>
        </template>

        <el-alert v-if="changeNote" type="info" :closable="false" class="text-muted small" :title="`退回原因：${changeNote}`" />

        <section class="mb-4">
          <h4 class="h5 mb-3">可修改的委托/样品信息</h4>
          <div class="row g-3">
            <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">委托单位</label><div class="col"><el-input v-model="form.client" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">工程名称</label><div class="col"><el-input v-model="form.projectName" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">样品编号</label><div class="col"><el-input v-model="form.sampleNo" /></div></div></div>
            <div class="col-12 col-lg-4"><div class="row g-2 align-items-center"><label class="col-12 col-sm-auto col-form-label w-auto">检测项目</label><div class="col"><el-input v-model="form.project" /></div></div></div>
          </div>
        </section>

        <el-input v-model="form.note" type="textarea" :rows="2" placeholder="更改说明（可选）" />
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
          <el-button v-if="canCompleteChange" type="primary" @click="submit">提交委托更改完成</el-button>
          <span v-else class="text-muted">无「提交委托更改完成」权限</span>
        </div>
      </el-card>

      <el-empty v-else description="请选择左侧委托更改中的单据" />
    </div>

    <el-card shadow="never" class="col-12 col-xl-6">
      <template #header>
        <div class="d-flex flex-wrap align-items-center justify-content-between gap-2"><strong>说明</strong></div>
      </template>
      <div class="text-muted small">
        <p>合同评审/样品出库「退回」的单据进入此处。</p>
        <ul>
          <li>修改委托/样品基本信息后「提交委托更改完成」。</li>
          <li>提交后按退回流程继续办理；需重新合同评审的，评审通过后按退回来源恢复环节。</li>
          <li>从样品出库退回的，评审通过后恢复「样品出库领取中」，保留入库记录，无需再次入库。</li>
        </ul>
      </div>
    </el-card>
  </div>
  </ModuleWorkspace>
</template>

<script setup lang="ts">
import { shallowRef, computed, reactive, ref, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { modules } from '@/data/modules'
import { reportWorkRows } from '@/data/mock'
import { fetchReportRows, type ReportRow } from '@/services/auth'
import { fetchReportDetail } from '@/services/reports'
import { PIPELINE_AVAILABLE, changeResubmit } from '@/services/pipeline'
import { useSessionStore } from '@/stores/session'
import ModuleWorkspace from '@/components/ModuleWorkspace.vue'
import ReportListPanel from '@/components/ReportListPanel.vue'

const route = useRoute()
const session = useSessionStore()
const canCompleteChange = computed(() => (
  session.can('entrust.change.view')
  || session.canAction('entrust.change.resubmit')
))
const available = PIPELINE_AVAILABLE
const pageName = computed(() => String(route.meta.pageName ?? '委托更改'))
const areaName = computed(() => String(route.meta.areaName ?? ''))
const moduleName = computed(() => String(route.meta.moduleName ?? ''))
const pageKey = computed(() => String(route.meta.pageKey ?? 'change'))
const pages = computed(() => modules.find((m) => m.key === 'entrust')?.pages ?? [])

const allRows = shallowRef<ReportRow[]>([])
const selectedNo = ref('')
const form = reactive({ client: '', projectName: '', sampleNo: '', project: '', note: '' })
const changeNote = ref('')
const editVersion = ref<number>()

const changeRows = computed(() => allRows.value.filter((r) => r.status === '委托更改中'))
const selected = computed(() => changeRows.value.find((r) => r.reportNo === selectedNo.value) ?? changeRows.value[0])

async function load() {
  if (!available) return
  allRows.value = await fetchReportRows(reportWorkRows, session.dataScope, session.userName)
}
watchEffect(load)

watchEffect(async () => {
  const row = selected.value
  if (!row) return
  form.client = row.client
  form.project = row.project
  const d = await fetchReportDetail(row.reportNo, 'entrust_change')
  if (selected.value?.reportNo !== row.reportNo) return
  editVersion.value = d?.editVersion
  const summary = d?.summary ?? []
  const find = (sec: string, key: string) =>
    (summary.find((s) => s.title === sec)?.fields.find(([k]) => k === key)?.[1] as string) || ''
  form.projectName = d?.projectName || find('委托信息', '工程名称')
  form.sampleNo = find('样品信息', '样品编号')
  changeNote.value = (d as unknown as { changeNote?: string })?.changeNote || ''
})

async function submit() {
  const row = selected.value
  if (!row) return
  try {
    const res = await changeResubmit(row.reportNo, { ...form, editVersion: editVersion.value })
    const dest = res?.status === '检测更改中' ? '进入检测更改' : '重新进入合同评审'
    ElMessage.success(`${row.reportNo} 委托更改完成，${dest}`)
    await load()
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '提交失败')
  }
}
</script>
