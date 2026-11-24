<template>
  <el-dialog v-model="opened" title="管理员修订合同显示内容" width="700px" append-to-body>
    <el-alert :closable="false" type="info" title="修订只用于合同目录显示，保留外部ERP原文、历史样品及签章快照。新的来源版本到达后需重新核对修订。" />
    <p>{{ number }}</p>
    <el-alert v-if="row?.displayOverrideStale" :closable="false" type="warning" title="来源已更新，旧修订已停止应用，请重新核对。" />
    <el-form v-if="row" label-width="130px">
      <el-form-item v-for="f in fields" :key="f.key" :label="f.label">
        <el-select v-if="f.key === 'erpType'" v-model="draft[f.key]" clearable><el-option v-for="t in ['标准合同','框架','虚拟框架']" :key="t" :label="t" :value="t" /></el-select>
        <el-input v-else v-model="draft[f.key]" :maxlength="500" :placeholder="f.hint" />
      </el-form-item>
      <el-form-item label="修订依据"><el-input v-model="reason" type="textarea" :maxlength="1000" placeholder="填写核实依据或留空原因" /></el-form-item>
    </el-form>
    <el-collapse><el-collapse-item title="最近修改记录"><div v-for="h in history" :key="h.id"><p>{{ h.created_at }} · {{ h.actor }} · {{ h.reason }}</p><pre>{{ h.after_json }}</pre></div></el-collapse-item></el-collapse>
    <template #footer><el-button @click="opened = false">关闭</el-button><el-button :disabled="!row || busy" @click="save(true)">撤销显示修订</el-button><el-button type="primary" :loading="busy" :disabled="!row" @click="save(false)">保存修订</el-button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { request } from '@/services/http'
const emit = defineEmits<{ saved: [] }>()
const opened=ref(false), busy=ref(false), number=ref(''), reason=ref('')
type DisplayRow = Record<string, unknown> & { displayRevision: number; displaySourceHash: string; displayOverrideStale: boolean }
const row=ref<DisplayRow | null>(null)
const history=ref<{id:string;actor:string;created_at:string;reason:string;after_json:string}[]>([])
const draft=reactive<Record<string,string>>({})
const fields=[{key:'client',label:'客户名称'},{key:'erpType',label:'外部ERP项目类型'}, {key:'projectName',label:'项目名称'}, {key:'bizDept',label:'业务所属部门'}, {key:'auditTime',label:'项目审核时间',hint:'YYYY-MM-DD HH:mm:ss.SSS，按核实的原始精度填写'}, {key:'contractStartDate',label:'合同开始日期',hint:'YYYY-MM-DD'}]
async function open(value:string) {
  number.value=value; row.value=null; reason.value=''; history.value=[]; opened.value=true
  try {
    const d=await request<{row:DisplayRow;history:typeof history.value}>('/api/contract-display/'+encodeURIComponent(value))
    row.value=d.row; history.value=d.history
    for(const f of fields) draft[f.key]=String(d.row[f.key] || '')
  } catch(e) { ElMessage.error(e instanceof Error ? e.message : '读取失败') }
}
async function save(clear:boolean) {
  if(!row.value || busy.value)return
  if(reason.value.trim().length<2)return ElMessage.warning('请填写修订依据')
  busy.value=true
  try {
    await request('/api/contract-display/'+encodeURIComponent(number.value),{method:'PUT',body:JSON.stringify({revision:row.value.displayRevision, sourceHash:row.value.displaySourceHash,fields:clear?{}:{...draft},reason:reason.value})})
    ElMessage.success('显示修订已保存');opened.value=false;emit('saved')
  } catch(e) { ElMessage.error(e instanceof Error ? e.message : '保存失败') }
  finally { busy.value=false }
}
defineExpose({open})
</script>
