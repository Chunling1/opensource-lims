<template>
  <BootstrapModal v-if="modelValue" :open="modelValue" title="选择检测项目 / 参数" size="xl" scrollable fullscreen-mobile fill-height body-class="p-0 mx-3" @close="$emit('update:modelValue', false)">
    <template #toolbar>
      <div class="d-flex flex-wrap justify-content-between gap-3 py-3">
        <form class="flex-grow-1" @submit.prevent="search">
          <label for="sample-capability-keyword" class="form-label">搜索库内项目</label>
          <div class="input-group"><input id="sample-capability-keyword" v-model="keyword" @input="scheduleSearch" class="form-control" type="search" autofocus placeholder="参数名称、检测对象或标准编号" /><button class="btn btn-primary" type="submit"><i class="ti ti-search me-1" aria-hidden="true"></i>查询</button></div>
          <p class="small text-body mt-2 mb-0">{{ standards.length ? "可按地点和 CMA/CNAS 资质筛选所选标准的参数；切换筛选不影响右侧已选项目。" : "请先选择检测依据，再选择库内参数；也可添加库外参数。" }}</p>
        </form>
        <button type="button" class="btn btn-outline-primary align-self-start" :aria-expanded="manualOpen" @click="manualOpen = !manualOpen"><i class="ti ti-plus me-1" aria-hidden="true"></i>添加库外参数</button>
      </div>
      <form v-if="manualOpen" class="p-3 bg-warning-subtle border border-warning-subtle rounded mb-3" @submit.prevent="addManual">
        <label for="picker-manual-input" class="form-label">库外参数名称 <span class="text-body fw-normal">（多项用分号或换行分隔）</span></label>
        <div class="input-group"><textarea id="picker-manual-input" v-model="manualText" class="form-control" rows="2" placeholder="填写库内没有的检测参数" @keydown="manualKeydown"></textarea><button class="btn btn-warning" type="submit" :disabled="!manualText.trim() || (!onsite && !validChoice(manualChoice))">添加到右侧</button></div>
        <ManualLocationChoice v-if="!onsite" v-model="manualChoice" :options="locationOptions" :library-addresses="libraryAddresses" :loading="locationsLoading" :error="locationsError" @retry="$emit('retry-locations')" />
        <p class="small text-body mt-2 mb-0">库外参数以橙色标识，不影响流程流转；CMA/CNAS 授权按所选标准核对。</p>
      </form>
      <nav class="nav nav-tabs nav-justified d-md-none mb-3" aria-label="项目选择栏目">
        <button type="button" class="nav-link" :class="{ active: mobilePane === 'library' }" :aria-pressed="mobilePane === 'library'" @click="mobilePane = 'library'">库内项目</button>
        <button type="button" class="nav-link" :class="{ active: mobilePane === 'selected' }" :aria-pressed="mobilePane === 'selected'" @click="mobilePane = 'selected'">已选项目（{{ draft.length }}）</button>
      </nav>
    </template>
    <div class="d-flex flex-column flex-md-row gap-3 h-100 pb-2">
      <section class="col flex-column border rounded overflow-hidden" :class="mobilePane === 'library' ? 'd-flex' : 'd-none d-md-flex'" aria-label="库内项目">
        <header class="d-flex flex-wrap align-items-center gap-2 p-3 border-bottom"><strong>库内项目</strong><span class="badge bg-light text-body">{{ resultTotal }}</span>
        <div class="row g-2 w-100 m-0">
          <div class="col-12 col-sm-8 ps-0">
            <label for="sample-capability-location" class="small mb-1">地点</label>
            <select id="sample-capability-location" v-model="locationFilter" class="form-select form-select-sm" :disabled="loading && !availableLocations.length" @change="search">
              <option value="">全部地点</option>
              <option v-for="location in availableLocations" :key="location" :value="location">{{ location === '__unspecified__' ? '未维护地点' : location }}</option>
            </select>
          </div>
          <div class="col-12 col-sm-4 ps-0">
            <label for="sample-capability-accreditation" class="small mb-1">资质</label>
            <select id="sample-capability-accreditation" v-model="accreditationFilter" class="form-select form-select-sm" @change="search">
              <option value="">全部资质</option><option value="CMA">CMA</option><option value="CNAS">CNAS</option>
            </select>
          </div>
        </div></header>
        <div class="flex-grow-1 overflow-auto">
          <div v-if="loading" class="p-4 text-body" role="status">正在加载库内项目…</div>
          <div v-else-if="error" class="alert alert-danger m-3" role="alert">{{ error }}<button type="button" class="btn btn-sm btn-outline-danger ms-2" @click="$emit('retry')">重新加载</button></div>
          <table v-else class="table table-hover align-middle mb-0" aria-label="可选库内项目">
            <thead class="table-light sticky-top"><tr><th scope="col">检测项目 / 参数</th><th scope="col" class="text-end">操作</th></tr></thead>
            <tbody><tr v-for="row in pageRows" :key="row.id"><td><div class="d-flex flex-wrap align-items-center gap-2"><span class="fw-medium">{{ row.itemName }}</span><span class="badge bg-light text-body">{{ row.capabilityType }}</span><span v-if="row.superseded" class="badge bg-light text-body">历史修订</span><span v-else-if="row.active === false" class="badge bg-light text-body">停用记录</span><span v-if="row.accreditation" class="badge" :class="row.accreditation === 'CMA' ? 'bg-success-subtle text-success' : 'bg-info-subtle text-info'">{{ row.accreditation }}</span></div><div class="small text-body mt-1">{{ row.standardCode }}</div><div class="small text-body">{{ row.objectName }}<span v-if="row.address || row.site"> · {{ row.address || row.site }}</span></div><small v-if="row.restriction" class="text-body">{{ row.restriction }}</small></td><td class="text-end"><button type="button" class="btn btn-sm" :class="has(row.id) ? 'btn-light' : 'btn-outline-primary'" :disabled="has(row.id)" :aria-label="`添加 ${row.itemName} ${row.id}`" @click="toggle(row.id, true)">{{ has(row.id) ? '已添加' : '添加' }}</button></td></tr>
            <tr v-if="!resultTotal"><td colspan="2" class="text-center text-body py-5">{{ keyword || locationFilter || accreditationFilter ? '没有匹配的项目，请调整关键词、地点或资质筛选。' : '当前条件下没有可选项目。' }}</td></tr></tbody>
          </table>
        </div>
        <footer class="d-flex flex-wrap align-items-center justify-content-between gap-2 p-3 border-top"><span class="small text-body">共 {{ resultTotal }} 项</span><div class="d-flex gap-2 align-items-center"><button class="btn btn-sm btn-light" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button><span class="small">{{ page }} / {{ pageCount }}</span><button class="btn btn-sm btn-light" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button></div></footer>
      </section>
      <section class="col flex-column border rounded overflow-hidden" :class="mobilePane === 'selected' ? 'd-flex' : 'd-none d-md-flex'" aria-label="已选项目与输出顺序">
        <header class="d-flex flex-wrap align-items-center gap-2 p-3 border-bottom"><strong>已选项目</strong><span class="badge bg-light text-body">{{ draft.length }}</span><span class="text-body small ms-auto">库内 {{ libraryCount }} · 库外 {{ draft.length - libraryCount }}</span></header>
        <p class="small text-body px-3 pt-3 mb-2">拖动调整顺序，也可点击上移、下移。委托单按此顺序输出。</p>
        <p v-if="unresolved && !loading" class="small text-danger px-3">部分历史项目当前不可用，请移除或重新选择后确认。</p>
        <div class="flex-grow-1 overflow-auto"><OrderedSelectionList v-if="draft.length" :items="draftRows" label="已选检测项目排序" show-source @reorder="reorder" @remove="remove">
          <template #item-extra="{ item }">
            <span v-if="!item.manual && !isAvailable(item.key) && !loading" class="badge bg-warning-subtle text-warning-emphasis mt-2">当前不可用 · 历史记录保留</span>
            <template v-if="item.manual && !onsite">
              <p class="small mb-1 mt-2">{{ locationLabel(item.label) }}</p>
              <button class="btn btn-sm btn-outline-primary" type="button" :aria-label="`修改地点 ${item.label}`" :aria-expanded="editingLocation === item.label" @click="editingLocation = editingLocation === item.label ? '' : item.label">修改地点</button>
              <ManualLocationChoice v-if="editingLocation === item.label" v-model="draftLocations[item.label]" :options="locationOptions" :library-addresses="libraryAddresses" :loading="locationsLoading" :error="locationsError" @retry="$emit('retry-locations')" />
            </template>
            <span v-else-if="accreditationFor(item.key)" class="badge bg-info-subtle text-info mt-2">{{ accreditationFor(item.key) }}</span>
          </template>
        </OrderedSelectionList><div v-else class="text-center text-body px-3 py-5"><i class="ti ti-list-check d-block fs-2 mb-2" aria-hidden="true"></i>从左侧添加库内项目<br /><small>或点击右上角添加库外参数</small></div></div>
      </section>
    </div>
    <template #footer><span v-if="invalidManualLocations" class="text-danger small w-100">请确认库外项目的检测地点。</span><span class="me-auto text-body small" role="status">已选 {{ draft.length }} 项，确认后应用到样品</span><el-button @click="$emit('update:modelValue', false)">取消</el-button><el-button type="primary" :disabled="loading || Boolean(error) || Boolean(manualText.trim()) || unresolved || invalidManualLocations" @click="confirm">确认选择（{{ draft.length }}）</el-button></template>
  </BootstrapModal>
</template>
<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import OrderedSelectionList from './OrderedSelectionList.vue'
import ManualLocationChoice from './ManualLocationChoice.vue'
import { parameterAddresses, parameterAddressKey, type ManualParameterLocations, type ManualParameterLocation } from '@/data/parameterLocations'
import type { CapabilityItemRow } from '@/services/pipeline'
import { reconcileTestItemOrder, testItemKey, testItemRows, type TestItemRef } from '@/composables/testItemOrder'
const props = withDefaults(defineProps<{modelValue: boolean; rows: CapabilityItemRow[]; selectedIds: number[]; standards: string[]; manualItems?: string[]; itemOrder?: TestItemRef[]; selectedRows?: CapabilityItemRow[]; historyRows?: CapabilityItemRow[]; loading?: boolean; error?: string; contextKey: string; total?: number; catalogLocations?: string[]; manualLocations?: ManualParameterLocations | null; legacyManualLocation?: string; onsite?: boolean; locationOptions?: string[]; locationsLoading?: boolean; locationsError?: string}>(), {loading:false,error:'',manualItems:()=>[],itemOrder:()=>[],selectedRows:()=>[],historyRows:()=>[],catalogLocations:()=>[],locationOptions:()=>[],legacyManualLocation:'',locationsError:''})
const emit = defineEmits<{'update:modelValue':[value:boolean];confirm:[ids:number[],manual:string[],order:TestItemRef[],locations:ManualParameterLocations];retry:[];'retry-locations':[];query:[value:{keyword:string;locationFilter:string;accreditationFilter:string;page:number;size:number;selectedStandardsOnly:boolean}]}>()
const mobilePane=ref('library')
const keyword=ref(''),locationFilter=ref(''),accreditationFilter=ref(''),page=ref(1),size=ref(20),draft=ref<TestItemRef[]>([]),manualOpen=ref(false),manualText=ref(''),selectedStandardsOnly=ref(true)
const draftLocations=ref<ManualParameterLocations>({}),manualChoice=ref<ManualParameterLocation>({mode:'library',addresses:[]}),editingLocation=ref('')
const libraryAddresses=computed(()=>{const byId=new Map([...props.selectedRows,...props.rows].map(row=>[row.id,row]));return parameterAddresses(draft.value.flatMap(item=>item.kind==='library'&&byId.get(item.id)?.address ? [byId.get(item.id)!] : []))})
function validChoice(choice?:ManualParameterLocation){return !!choice && (choice.mode==='library' ? libraryAddresses.value.length>0 : choice.addresses.length>0 && !props.locationsLoading && !props.locationsError && choice.addresses.every(address=>props.locationOptions.includes(address)))}
const invalidManualLocations=computed(()=>!props.onsite && draft.value.some(item=>item.kind==='manual'&&!validChoice(draftLocations.value[item.name])))
function locationLabel(name:string){const choice=draftLocations.value[name];return choice?.mode==='library' ? '地点：与库内项目一致' : `地点：${choice?.addresses.join('；') || '未选择'}`}
function accreditationFor(key:string){return [...props.selectedRows,...props.rows].find(row=>key===`library:${row.id}`)?.accreditation || ''}
const normalized=(value:unknown)=>String(value??'').normalize('NFKC').toLowerCase()
const remote=computed(()=>props.total !== undefined)
const rowLocation=(row:CapabilityItemRow)=>parameterAddressKey(row.address || row.site || '') || '__unspecified__'
const standardRows=computed(()=>props.rows.filter(row=>props.standards.some(code=>normalized(code).replace(/\s/g,'')===normalized(row.standardCode).replace(/\s/g,''))))
const availableLocations=computed(()=>remote.value ? props.catalogLocations : [...new Set(standardRows.value.map(rowLocation))].sort())
const filtered=computed(()=>{const terms=normalized(keyword.value).trim().split(/\s+/).filter(Boolean);return standardRows.value.filter(row=>(!locationFilter.value || rowLocation(row)===locationFilter.value)&&(!accreditationFilter.value || row.accreditation===accreditationFilter.value)&&terms.every(term=>normalized([row.standardCode,row.standardName,row.objectName,row.itemName,row.address,row.site,row.restriction].join(' ')).includes(term)))})
const resultTotal=computed(()=>remote.value ? props.total! : filtered.value.length)
const pageCount=computed(()=>Math.max(1,Math.ceil(resultTotal.value/size.value)))
const pageRows=computed(()=>remote.value ? props.rows : filtered.value.slice((page.value-1)*size.value,page.value*size.value))
const draftRows=computed(()=>testItemRows(draft.value,[...props.historyRows,...props.selectedRows,...props.rows]))
const libraryCount=computed(()=>draft.value.filter(item=>item.kind==='library').length)
function isAvailable(key:string){return (remote.value ? [...props.selectedRows,...props.rows] : props.rows).some(row=>key===`library:${row.id}`)}
const unresolved=computed(()=>draft.value.some(item=>item.kind==='library'&&!(remote.value ? [...props.selectedRows,...props.rows] : props.rows).some(row=>row.id===item.id)))
let searchTimer: ReturnType<typeof setTimeout> | undefined
function requestPage(){if(remote.value && props.modelValue)emit('query',{keyword:keyword.value.trim(),locationFilter:locationFilter.value,accreditationFilter:accreditationFilter.value,page:page.value,size:size.value,selectedStandardsOnly:selectedStandardsOnly.value})}
function search(){clearTimeout(searchTimer);page.value=1;requestPage()}
function scheduleSearch(){clearTimeout(searchTimer);if(remote.value)searchTimer=setTimeout(search,350)}
function goPage(value:number){clearTimeout(searchTimer);page.value=value;requestPage()}
onBeforeUnmount(()=>clearTimeout(searchTimer))
watch([keyword,locationFilter,accreditationFilter,size,selectedStandardsOnly],()=>{page.value=1})
watch(pageCount,count=>{if(!remote.value)page.value=Math.min(page.value,count)})
watch(()=>props.modelValue,open=>{if(open){mobilePane.value='library';keyword.value='';locationFilter.value='';accreditationFilter.value='';page.value=1;selectedStandardsOnly.value=true;editingLocation.value='';manualChoice.value={mode:'library',addresses:[]};draftLocations.value=Object.fromEntries(props.manualItems.map(name=>[name,props.manualLocations?.[name] ? { ...props.manualLocations[name],addresses:[...props.manualLocations[name].addresses] } : props.legacyManualLocation.trim() ? {mode:'selected',addresses:props.legacyManualLocation.split(/[；;\n]+/).map(parameterAddressKey).filter(Boolean)} : {mode:'library',addresses:[]}]));manualOpen.value=false;manualText.value='';draft.value=reconcileTestItemOrder(props.itemOrder,props.selectedIds,props.manualItems);requestPage()}else{clearTimeout(searchTimer)}},{immediate:true})
watch(()=>props.contextKey,()=>{if(props.modelValue)emit('update:modelValue',false)})
const has=(id:number)=>draft.value.some(item=>item.kind==='library'&&item.id===id)
function toggle(id:number,selected:boolean){if(selected&&!has(id))draft.value.push({kind:'library',id});else if(!selected)remove(`library:${id}`)}
function remove(key:string){draft.value=draft.value.filter(item=>testItemKey(item)!==key)}
function reorder(keys:string[]){const map=new Map(draft.value.map(item=>[testItemKey(item),item]));draft.value=keys.map(key=>map.get(key)!).filter(Boolean)}
function addManual(){if(!props.onsite&&!validChoice(manualChoice.value))return;for(const name of manualText.value.split(/[;；\r\n]+/).map(value=>value.trim()).filter(Boolean)){if(!draft.value.some(item=>item.kind==='manual'&&item.name===name)){draft.value.push({kind:'manual',name});draftLocations.value[name]={mode:manualChoice.value.mode,addresses:[...manualChoice.value.addresses]}}}manualText.value=''}
function manualKeydown(event:KeyboardEvent){if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing&&event.keyCode!==229){event.preventDefault();addManual()}}
function confirm(){if(props.loading||props.error||manualText.value.trim()||unresolved.value||invalidManualLocations.value)return;const ids=draft.value.flatMap(item=>item.kind==='library'?[item.id]:[]),manual=draft.value.flatMap(item=>item.kind==='manual'?[item.name]:[]);emit('confirm',ids,manual,draft.value.map(item=>({...item})),Object.fromEntries(manual.map(name=>[name,{...draftLocations.value[name],addresses:[...(draftLocations.value[name]?.addresses || [])]}])))}
</script>
