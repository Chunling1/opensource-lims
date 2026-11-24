<template>
  <el-card shadow="never" class="mb-3">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <strong>项目能力范围</strong>
      <el-tag :type="data?.state === 'out_of_scope' ? 'danger' : data?.state === 'in_scope' ? 'success' : 'warning'">{{ label }}</el-tag>
      <span v-if="data?.reviewApplied">已由 {{ data.review.actorName }} 复核</span>
      <el-button link @click="expanded = !expanded">{{ expanded ? '收起依据' : '查看逐项依据' }}</el-button>
      <el-button v-if="data?.canReview && !session.businessReadOnly && !readOnly" @click="openReview">范围复核纠正</el-button>
      <el-button link :loading="loading" @click="load">重新核查</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="data?.reviewStale" title="此前复核依据已变化，已恢复自动判定，请重新复核。" type="warning" :closable="false" />
    <div v-if="expanded && data">
      <p>{{ data.note || '所选能力项目在当前部门、日期和地点范围内。' }}</p>
      <p>按本次实际选择的能力项目核查；CMA、CNAS 分别显示，不要求每个项目同时具有两种授权。报告标识及适用范围说明仍需审核确认。</p>
      <el-table :data="data.rows" border size="small">
        <el-table-column prop="standard" label="标准" min-width="140" />
        <el-table-column prop="item" label="所选项目/参数" min-width="170" />
        <el-table-column prop="mark" label="能力依据" width="90" />
        <el-table-column label="核查说明" min-width="240"><template #default="{row}">{{ [...row.reasons, ...row.pending].join('；') || '授权范围内' }}</template></el-table-column>
      </el-table>
      <p v-if="data.reviewApplied">复核理由：{{ data.review.reason }}</p>
    </div>
    <el-dialog v-model="editing" title="范围分类复核" append-to-body width="620px">
      <el-alert title="复核只纠正本报告的范围分类，不修改能力授权、设备有效期、审核结论或已签署文件。依据变化后自动重新核查。" type="info" :closable="false" />
      <el-radio-group v-model="decision" >
        <el-radio value="in_scope">经核实在范围内</el-radio>
        <el-radio value="out_of_scope">确认超范围</el-radio>
        <el-radio value="reset">恢复自动判定</el-radio>
      </el-radio-group>
      <el-input v-model="reason" type="textarea" :rows="4" maxlength="1000" show-word-limit placeholder="填写核对的能力项目、授权依据及纠正原因（至少5字）" />
      <template #footer><el-button @click="editing=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="reason.trim().length < 5" @click="save">保存复核记录</el-button></template>
    </el-dialog>
  </el-card>
</template>
<script setup lang="ts">
import {computed, ref, watch} from 'vue'
import {ElMessage} from 'element-plus'
import {request} from '@/services/http'
import {useSessionStore} from '@/stores/session'
const props=defineProps<{reportNo:string;view:string;readOnly?:boolean}>()
const emit=defineEmits<{changed:[value:{outOfScope:boolean;note:string;state:string}]}>()
type Verdict={state:string;computedState:string;outOfScope:boolean;note:string;fingerprint:string;canReview:boolean;reviewApplied:boolean;reviewStale:boolean;review:{actorName?:string;reason?:string};rows:{id:number;standard:string;item:string;mark:string;reasons:string[];pending:string[]}[]}
const session=useSessionStore(), data=ref<Verdict|null>(null), error=ref(''), expanded=ref(false),editing=ref(false),loading=ref(false),saving=ref(false)
const decision=ref('in_scope'),reason=ref('')
let generation=0
const label=computed(()=>data.value?.state==='in_scope'?'范围内':data.value?.state==='out_of_scope'?'超范围':'待核实')
const endpoint=()=>`/api/reports/${encodeURIComponent(props.reportNo)}/scope-review?view=${encodeURIComponent(props.view)}`
async function load(){const id=++generation;loading.value=true;error.value='';try{const value=await request<Verdict>(endpoint());if(id===generation)data.value=value}catch(e){if(id===generation){data.value=null;error.value=e instanceof Error?e.message:'范围核查失败'}}finally{if(id===generation)loading.value=false}}
function openReview(){if(props.readOnly)return;reason.value='';decision.value='in_scope';editing.value=true}
async function save(){if(props.readOnly||!data.value||saving.value)return;const id=generation; saving.value=true;try{const value=await request<Verdict>(endpoint(),{method:'POST',body:JSON.stringify({decision:decision.value,reason:reason.value.trim(),fingerprint:data.value.fingerprint})});if(id!==generation)return;data.value=value;editing.value=false;emit('changed',value);ElMessage.success('范围分类已更新，复核依据已记录')}catch(e){if(id===generation)ElMessage.error(e instanceof Error?e.message:'保存失败')}finally{saving.value=false}}
watch(()=>[props.reportNo,props.view],()=>{data.value=null;expanded.value=false;editing.value=false;void load()},{immediate:true})
</script>

