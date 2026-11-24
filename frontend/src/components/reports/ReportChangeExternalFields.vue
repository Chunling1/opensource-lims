<script setup lang="ts">
import { ref } from 'vue'
import AttachmentDraftStatus from '../common/AttachmentDraftStatus.vue'
import SingleChoice from '../common/SingleChoice.vue'
import PersonnelAttachments from '../quality/PersonnelAttachments.vue'
import type { ReportChangeDraft } from '../../types/reports/reportChange'
const props = defineProps<{ draft: ReportChangeDraft; readonly: boolean; busy: boolean }>()
const emit = defineEmits<{ handler: [] }>()
const attachmentsOpen = ref(false), uploadRevision = ref(0)
</script>
<template>
  <template v-if="draft.external">
    <fieldset :disabled="readonly || busy" class="vstack gap-2">
      <div class="row g-2">
        <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><label for="external-responsibility" class="col-sm-4 col-form-label">更改责任方</label><div class="col"><input id="external-responsibility" data-validation-key="responsibility" v-model="draft.responsibility" class="form-control" maxlength="200" /></div></div></div>
        <div class="col-12 col-md-6"><div class="d-flex align-items-center gap-2" data-field-control><label for="external-handler" class="col-form-label text-nowrap">指定处理人</label><input id="external-handler" data-validation-key="handlerId" class="form-control" :value="draft.external.handlerName" readonly size="1" /><button id="external-handler-select" type="button" class="btn btn-light text-nowrap" @click="emit('handler')">选择</button><button type="button" class="btn btn-light text-nowrap" :disabled="!draft.external.handlerId" @click="draft.external.handlerId = ''; draft.external.handlerName = ''">清除</button></div></div>
      </div>
      <div class="row g-2">
        <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><span class="col-sm-4 col-form-label">是否需要收费</span><div class="col d-flex gap-3" role="group" aria-label="是否需要收费"><label v-for="value in [true, false]" :key="String(value)" class="d-flex align-items-center gap-2 mb-0"><SingleChoice name="external-charge" :value="String(value)" :checked="draft.charge === value" :label="value ? '是' : '否'" :disabled="readonly || busy" @change="draft.charge = value; if (!value) draft.amount = 0" />{{ value ? '是' : '否' }}</label></div></div></div>
        <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><label for="external-amount" class="col-sm-4 col-form-label">收费金额</label><div class="col"><input id="external-amount" data-validation-key="amount" v-model.number="draft.amount" type="number" min="0" max="999999999" step="0.01" class="form-control" :disabled="!draft.charge" /></div></div></div>
      </div>
      <div class="row g-2 align-items-center"><label for="external-before" class="col-12 col-sm-2 col-form-label">更改前内容</label><div class="col"><input id="external-before" data-validation-key="before" v-model="draft.before" class="form-control" maxlength="1000" /></div></div>
      <div class="row g-2 align-items-center"><label for="external-after" class="col-12 col-sm-2 col-form-label">更改后内容</label><div class="col"><input id="external-after" data-validation-key="after" v-model="draft.after" class="form-control" maxlength="1000" /></div></div>
    </fieldset>
    <slot name="reason" />
    <div class="row g-2 align-items-center"><span class="col-12 col-sm-2 col-form-label">提供证据</span><div class="col d-flex align-items-center gap-2"><span class="text-muted">{{ draft.external.evidence.length }} 个附件</span><button type="button" class="btn btn-light" :aria-expanded="attachmentsOpen" aria-controls="external-evidence" @click="attachmentsOpen = !attachmentsOpen">附件</button></div></div>
    <div v-if="attachmentsOpen" id="external-evidence" class="border rounded p-3"><PersonnelAttachments :key="uploadRevision" :files="draft.external.evidence" :readonly="readonly || busy" label="报告更改证据附件" /></div>
    <AttachmentDraftStatus @reset="uploadRevision++" v-if="!attachmentsOpen" :files="draft.external.evidence" />
    <div class="row g-2 align-items-center">
      <div class="col-12 col-md-7"><div class="d-flex flex-wrap align-items-center gap-2" role="group" aria-labelledby="external-customer-label"><span id="external-customer-label" class="col-form-label">申请单位是否为委托单位</span><label v-for="value in [true, false]" :key="String(value)" class="d-flex align-items-center gap-1 mb-0"><SingleChoice name="external-customer" :value="String(value)" :checked="draft.external.isCommissionCustomer === value" :label="value ? '是' : '否'" :disabled="readonly || busy" @change="draft.external.isCommissionCustomer = value" />{{ value ? '是' : '否' }}</label></div></div>
      <div class="col-12 col-md-5"><div class="d-flex flex-wrap align-items-center gap-2" role="group" aria-labelledby="external-returned-label"><span id="external-returned-label" class="col-form-label">原报告是否全部收回</span><label v-for="value in [true, false]" :key="String(value)" class="d-flex align-items-center gap-1 mb-0"><SingleChoice name="external-returned" :value="String(value)" :checked="draft.external.allReturned === value" :label="value ? '是' : '否'" :disabled="readonly || busy" @change="draft.external.allReturned = value" />{{ value ? '是' : '否' }}</label></div></div>
    </div>
  </template>
</template>
