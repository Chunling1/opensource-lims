<script setup lang="ts">
import {computed,ref,watch} from 'vue'
const props=defineProps<{steps:{key:string;title:string;description:string;complete:boolean}[];busy?:boolean}>()
const tabs=computed(()=>props.steps.map(s=>({...s,label:s.title+' · '+s.description,tabId:'signing-step-'+s.key,icon:s.complete?'ti ti-check':'ti ti-clock'})))
const currentStep=computed(()=>{const i=props.steps.findIndex(s=>!s.complete);return i<0?props.steps.length:i})
const confirmed=computed(()=>props.steps.length>0&&props.steps.every(s=>s.complete))
const activeTab=ref(''),changing=false,canConfirm=true,showConfirmationHint=false
watch(()=>props.steps,()=>{activeTab.value=props.steps[currentStep.value]?.key||props.steps.at(-1)?.key||''},{immediate:true})
</script>
<template>    <div class="step-arrow-nav mt-n3 mx-n3 mb-3">
      <ul class="nav nav-pills nav-justified custom-nav" role="tablist" aria-label="电子签发流程">
        <li v-for="(step, index) in tabs" :key="step.key" class="nav-item" role="presentation">
          <button :id="step.tabId" class="nav-link text-body-emphasis fs-5 p-2 p-md-3 h-100 w-100" :class="{ active: activeTab === step.key, done: confirmed || index < currentStep }" type="button" role="tab" :disabled="busy || changing || step.key === 'complete' && !confirmed && !canConfirm" :aria-label="step.label"   :aria-selected="activeTab === step.key" :aria-current="activeTab === step.key ? 'step' : undefined" @click="activeTab = step.key"><span class="d-block d-md-inline mb-2 mb-md-0"><i :class="step.icon" class="fs-4 p-2 bg-primary-subtle text-body-emphasis rounded-circle align-middle me-md-2" aria-hidden="true"></i></span>{{ step.label }}<small v-if="step.key === 'complete' && showConfirmationHint" id="report-confirmation-hint" class="d-block text-muted fw-normal small mt-1">报告预览就绪后可确认</small></button>
        </li>
      </ul>
    </div>
</template>
