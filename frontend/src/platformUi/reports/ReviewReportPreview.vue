<script setup lang="ts">
import {computed,inject,ref,watch,onBeforeUnmount} from 'vue'
import DataEntryPreview from '../../components/testing/DataEntryPreview.vue'
import ErrorNotice from '../../components/common/ErrorNotice.vue'
import type {EntryDetail} from '../../types/testing/dataEntryDetail'
const props=defineProps<{detail:EntryDetail;active:boolean;compact?:boolean;previewTitle?:string}>()
const emit=defineEmits<{refresh:[]}>()
const c=inject<any>('platform-review-controller')!
const url=computed(()=>c.documentPdfUrl||''),blob=ref<Blob>()
let generation=0
watch(url,async value=>{
  const current=++generation;blob.value=undefined
  if(!value)return
  try{const response=await fetch(value);const file=await response.blob();if(current===generation)blob.value=file}catch{ /* Preview error is owned by the report controller. */ }
},{immediate:true})
onBeforeUnmount(()=>{generation++})
const loading=computed(()=>c.decisionPreviewLoading),error=computed(()=>c.decisionPreviewIssue||'')
const original=computed(()=>c.pageKey === 'print')
const filename=computed(()=>`${props.detail.sample.reportCode}-${original.value ? '未签章原件' : '报告'}.pdf`)
const waiting=computed(()=>false)
const emptyText=computed(()=>loading.value?'正在加载报告预览…':error.value?'报告预览尚不可用':'暂无可预览报告')
</script>
<template>
  <section :class="compact ? 'mb-0' : 'mb-4'" aria-label="报告预览工作区" :aria-busy="loading || waiting">
    <DataEntryPreview id="check-report-preview" persistent :hide-print="original" :hide-download="!c.session.canAction('report.pdf.download')" :url="url" :blob="blob" :name="filename" type="application/pdf" :title="previewTitle || (original ? '报告原件（未签字、未盖章）' : '报告预览')">
      <template #before>
        <ErrorNotice :error="error" />
        <button v-if="error || ['stale', 'failed'].includes(detail.reportStatus)" type="button" class="btn btn-light mb-3" :disabled="loading" @click="emit('refresh')">刷新预览</button>
      </template>
      <template #empty><div class="text-center text-muted py-5" role="status"><span v-if="loading || waiting" class="spinner-border spinner-border-sm d-block mx-auto mb-3" aria-hidden="true"></span><i v-else class="ti ti-file-type-pdf display-4 d-block mb-3" aria-hidden="true"></i>{{ emptyText }}</div></template>
    </DataEntryPreview>
  </section>
</template>
