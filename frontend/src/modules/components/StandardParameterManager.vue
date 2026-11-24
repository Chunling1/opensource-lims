<template>
  <el-dialog :model-value="modelValue" title="标准参数维护" width="1100px" top="5vh" :before-close="closeDialog" @update:model-value="emit('update:modelValue', $event)">
    <template v-if="standard">
      <h5>{{ standard.code }} · {{ standard.name }}</h5>
      <p class="text-muted">已有资质标识与来源保留；新增和复制参数为内部维护参数，不自动取得 CMA/CNAS 授权。</p>
      <div v-if="error" class="alert alert-danger" role="alert">{{ error }}</div>
      <div v-if="notice" class="alert alert-success" role="status">{{ notice }}</div>
      <form v-if="draft" id="standard-parameter-form" @submit.prevent="save">
        <div class="d-flex align-items-center justify-content-between mb-3"><h6 class="mb-0">{{ editing ? '修改参数' : draft.copyFromId ? '复制参数到本标准' : '新增参数' }}</h6><button class="btn btn-light" type="button" :disabled="saving" @click="draft = null">返回列表</button></div>
        <div v-if="editing" class="alert alert-info">{{ editing.accreditation }} · {{ editing.sourceFile }}<span v-if="editing.sourcePage"> · 第 {{ editing.sourcePage }} 页</span>。修改生成新修订，旧样品保留原名称与地点；再次完成登记前需重新确认参数。</div>
        <div v-if="sharedSource" class="alert alert-warning">本标准与同来源版本共用参数；修改会用于该来源组后续的参数选择。</div>
        <div class="row g-3">
          <div v-for="field in textFields" :key="field.key" class="col-12 col-md-6"><label :for="'parameter-'+field.key" class="form-label">{{ field.label }}</label><input :id="'parameter-'+field.key" v-model="draft[field.key]" class="form-control" :maxlength="field.max" :required="field.required" :disabled="saving" /></div>
          <div class="col-12 col-md-6"><label for="parameter-type" class="form-label">参数类型</label><select id="parameter-type" v-model="draft.capabilityType" class="form-select" :disabled="saving || !!editing"><option>检测</option><option>检验</option><option>校准</option></select></div>
          <div class="col-12"><label for="parameter-restriction" class="form-label">限制条件</label><textarea id="parameter-restriction" v-model="draft.restriction" class="form-control" maxlength="4000" :disabled="saving" /></div>
          <p class="col-12 text-muted">部门授权随标准统一维护；获授权部门可使用本标准全部启用参数。</p>
          <div class="col-12"><label class="form-check"><input v-model="draft.active" type="checkbox" class="form-check-input" :disabled="saving" /><span class="form-check-label">启用（停用后不再提供新选择，历史样品保留）</span></label></div>
          <div class="col-12"><label for="parameter-reason" class="form-label">维护说明</label><textarea id="parameter-reason" v-model="draft.reason" class="form-control" maxlength="1000" required :disabled="saving" /></div>
        </div>
      </form>
      <template v-else>
        <div class="d-flex flex-wrap gap-2 mb-3"><button v-if="canCreate" type="button" class="btn btn-primary" :disabled="loading" @click="edit()">新增参数</button><button v-if="canCreate" type="button" class="btn btn-outline-primary" :disabled="loading" @click="openCopy">从其他标准复制</button><button v-if="copying" type="button" class="btn btn-light" @click="returnToTarget">返回本标准</button></div>
        <template v-if="copying && !source">
          <form class="d-flex gap-2 mb-3" @submit.prevent="standardSearch.run()"><input v-model="standardKeyword" class="form-control" placeholder="搜索标准编号或名称" aria-label="复制来源标准搜索" maxlength="200" /><button class="btn btn-primary text-nowrap flex-shrink-0" :disabled="loading">搜索</button></form>
          <p v-if="loading" role="status">正在加载标准…</p><div v-else class="table-responsive"><table class="table text-nowrap"><thead><tr><th>受控号 / 标准编号</th><th>标准名称</th><th>操作</th></tr></thead><tbody><tr v-for="item in standards" :key="item.id"><td>{{ item.controlledNo }} / {{ item.code }}</td><td>{{ item.name }}</td><td><button type="button" class="btn btn-outline-primary btn-sm" @click="chooseSource(item)">选择</button></td></tr><tr v-if="!standards.length"><td colspan="3">没有匹配的标准</td></tr></tbody></table></div>
          <div class="d-flex justify-content-end gap-2"><span>共 {{ standardTotal }} 条 · 第 {{ standardPage }} 页</span><button type="button" class="btn btn-light btn-sm" :disabled="loading || standardPage <= 1" @click="loadStandards(standardPage-1)">上一页</button><button type="button" class="btn btn-light btn-sm" :disabled="loading || standardPage*20 >= standardTotal" @click="loadStandards(standardPage+1)">下一页</button></div>
        </template>
        <template v-else>
          <p v-if="source" class="text-muted">复制来源：{{ source.code }} · {{ source.name }}</p>
          <form class="d-flex gap-2 mb-3" @submit.prevent="parameterSearch.run()"><input v-model="keyword" class="form-control" placeholder="搜索参数、检测对象或场所" aria-label="参数搜索" maxlength="200" /><button class="btn btn-primary text-nowrap flex-shrink-0" :disabled="loading">搜索</button></form>
          <p v-if="loading" role="status">正在加载参数…</p><div v-else class="table-responsive"><table class="table align-middle text-nowrap"><thead><tr><th>参数 / 检测对象</th><th>检测地点</th><th>资质与来源</th><th>状态</th><th>操作</th></tr></thead><tbody>
            <tr v-for="row in rows" :key="row.id"><td>{{ row.itemName }}<small class="d-block text-muted">{{ row.objectName }} · {{ row.capabilityType }}</small></td><td>{{ row.site }}<small class="d-block">{{ row.address || '未维护完整地址' }}</small></td><td><span class="badge bg-primary-subtle text-body">{{ row.accreditation }}</span><small class="d-block">{{ row.sourceFile }}<span v-if="row.sourcePage"> · 第 {{ row.sourcePage }} 页</span></small></td><td>{{ row.superseded ? '历史修订' : row.active ? '启用' : '停用' }}</td><td><div class="d-flex gap-2"><button v-if="!source && canUpdate && !row.superseded" type="button" class="btn btn-outline-primary btn-sm" @click="edit(row)">修改</button><button v-if="canCreate" type="button" class="btn btn-light btn-sm" @click="edit(row,true)">复制</button></div></td></tr><tr v-if="!rows.length"><td colspan="5">暂无参数，可新增或从其他标准复制</td></tr>
          </tbody></table></div>
          <div class="d-flex justify-content-end align-items-center gap-2"><span>共 {{ total }} 项 · 第 {{ page }} 页</span><button type="button" class="btn btn-light btn-sm" :disabled="loading || page <= 1" @click="load(page-1)">上一页</button><button type="button" class="btn btn-light btn-sm" :disabled="loading || page*20 >= total" @click="load(page+1)">下一页</button></div>
        </template>
      </template>
    </template>
    <template #footer><button v-if="draft" type="submit" form="standard-parameter-form" class="btn btn-primary" :disabled="saving">{{ saving ? '保存中…' : '保存参数' }}</button><button type="button" class="btn btn-light" :disabled="saving" @click="emit('update:modelValue',false)">关闭</button></template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElDialog } from 'element-plus'
import { useSessionStore } from '@/stores/session'
import { useLiveSearch, useSearchRequest } from '@/composables/liveSearch'
import { loadStandardParameters, searchParameterStandards, saveStandardParameter, type ParameterRow, type ParameterDraft, type ParameterStandard } from '@/services/standardParameters'
const props = defineProps<{modelValue: boolean; standard?: ParameterStandard}>()
const emit = defineEmits<{'update:modelValue':[value:boolean]}>()
function closeDialog(done:()=>void){if(!saving.value)done()}
const session = useSessionStore()
const canCreate = computed(()=>session.canAction('quality.standard.create'))
const canUpdate = computed(()=>session.canAction('quality.standard.update'))
const rows = ref<ParameterRow[]>([]), total=ref(0), page=ref(1), keyword=ref(''), departments=ref<string[]>([])
const loading=ref(false), saving=ref(false), error=ref(''), notice=ref(''), sharedSource=ref(false)
const editing=ref<ParameterRow>(), draft=ref<ParameterDraft|null>(null), copying=ref(false), source=ref<ParameterStandard>()
const standardKeyword=ref(''), standardPage=ref(1), standardTotal=ref(0), standards=ref<ParameterStandard[]>([])
const textFields: {key:'itemName'|'objectName'|'site'|'address'|'methodClause';label:string;max:number;required:boolean}[] = [
  {key:'itemName',label:'参数名称',max:400,required:true},{key:'objectName',label:'检测对象',max:400,required:true},
  {key:'site',label:'场所名称',max:80,required:true},{key:'address',label:'完整检测地址',max:1000,required:true},
  {key:'methodClause',label:'方法条款',max:600,required:false}]
const requestCurrent = useSearchRequest(()=>[props.modelValue,props.standard?.id,source.value?.id,copying.value,keyword.value,standardKeyword.value])
async function load(next=1) {
  const id=source.value?.id || props.standard?.id; if(!id)return
  const current=requestCurrent(); loading.value=true; error.value=''; page.value=next; rows.value=[]; total.value=0
  try {const data=await loadStandardParameters(id,keyword.value,next);if(!current())return;rows.value=data.rows;total.value=data.total;if(!source.value){departments.value=data.departments;sharedSource.value=data.sharedSource}}
  catch(e){if(current())error.value=String((e as Error).message||e)}finally{if(current())loading.value=false}
}
async function loadStandards(next=1){const current=requestCurrent();loading.value=true;error.value='';standardPage.value=next;standards.value=[];standardTotal.value=0;try{const data=await searchParameterStandards(standardKeyword.value,next);if(current()){standards.value=data.rows;standardTotal.value=data.total}}catch(e){if(current())error.value=String((e as Error).message||e)}finally{if(current())loading.value=false}}
const parameterSearch=useLiveSearch(keyword,()=>load(1),()=>props.modelValue && (!copying.value || !!source.value))
const standardSearch=useLiveSearch(standardKeyword,()=>loadStandards(1),()=>props.modelValue && copying.value && !source.value)
function openCopy(){copying.value=true;source.value=undefined;notice.value='';void loadStandards(1)}
function loadFirstPage(){if(keyword.value)keyword.value='';else void load(1)}
function chooseSource(item:ParameterStandard){source.value=item;loadFirstPage()}
function returnToTarget(){copying.value=false;source.value=undefined;loadFirstPage()}
function edit(row?:ParameterRow, copy=false){error.value='';notice.value='';editing.value=copy?undefined:row;draft.value={itemName:row?.itemName||'',objectName:row?.objectName||'',site:row?.site||'',address:row?.address||'',capabilityType:row?.capabilityType||'检测',methodClause:row?.methodClause||'',restriction:row?.restriction||'',active:row&&!copy?row.active:true,reason:'',...(row&&!copy?{version:row.version}:{}),...(row&&copy?{copyFromId:row.id}:{})}}
async function save(){if(!draft.value||!props.standard||saving.value)return;saving.value=true;error.value='';try{await saveStandardParameter(props.standard.id,draft.value,editing.value?.id);draft.value=null;notice.value='参数已保存';returnToTarget()}catch(e){error.value=String((e as Error).message||e)}finally{saving.value=false}}
watch(()=>[props.modelValue,props.standard?.id],()=>{if(!props.modelValue)return;draft.value=null;editing.value=undefined;copying.value=false;source.value=undefined;departments.value=[];sharedSource.value=false;notice.value='';loadFirstPage()},{immediate:true})
</script>
