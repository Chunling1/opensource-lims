<script setup lang="ts">
import BootstrapModal from '../../components/common/BootstrapModal.vue'
import WorkflowDatePicker from '@/components/WorkflowDatePicker.vue'
import StorageSampleSummary from './StorageSampleSummary.vue'
import type { SampleRow } from '@/services/pipeline'
defineProps<{
  open: boolean; row?: SampleRow; previousDate: string; canSign: boolean; allowSign: boolean; allowReturn: boolean
  form: { managerId: string; managerName: string; outTime: string; receiverName: string; pickupTime: string; returnNote: string }
}>()
defineEmits<{ close: []; submit: [action: 'sign' | 'return'] }>()
</script>
<template>
  <BootstrapModal :open="open" title="样品出库并领取" size="lg" scrollable fullscreen-mobile @close="$emit('close')">
    <template #title-suffix><span v-if="row?.dataStatus" class="badge bg-info-subtle text-info small ms-2">{{ row.dataStatus }}</span></template>
    <StorageSampleSummary :row="row" />
    <section class="border-top mt-4 pt-4" aria-labelledby="pickup-details-heading">
      <h6 id="pickup-details-heading" class="mb-3">出库领取单</h6>
      <div class="row g-3">
        <div class="col-12 col-sm-6"><label for="pickup-manager-id" class="form-label">样品管理员工号</label><input id="pickup-manager-id" :value="form.managerId" class="form-control" disabled /></div>
        <div class="col-12 col-sm-6"><label for="pickup-manager-name" class="form-label">样品管理员姓名</label><input id="pickup-manager-name" :value="form.managerName" class="form-control" disabled /></div>
        <div class="col-12 col-sm-6"><label for="pickup-out-date" class="form-label">出库领取日期</label><WorkflowDatePicker id="pickup-out-date" v-model="form.outTime" strict-order :previous-date="previousDate" require-previous missing-previous-reason="缺少原入库业务日期，请先核对历史记录恢复；无需重复入库。" aria-describedby="pickup-date-help" /><div id="pickup-date-help" class="form-text">{{ previousDate ? `不得早于入库日期 ${previousDate}` : '请先核对样品入库日期。' }}</div></div>
        <div class="col-12 col-sm-6"><label for="pickup-receiver" class="form-label">领样人姓名</label><input id="pickup-receiver" v-model="form.receiverName" class="form-control" placeholder="填写领样人签字姓名" /></div>
      </div>
    </section>
    <section v-if="allowReturn" class="border-top mt-4 pt-3" aria-labelledby="pickup-return-label">
      <label id="pickup-return-label" for="pickup-return-note" class="form-label">退回原因 <span class="text-muted fw-normal">（仅退回委托更改时填写）</span></label>
      <textarea id="pickup-return-note" v-model="form.returnNote" class="form-control" rows="2" placeholder="请填写需要更改的内容或退回原因"></textarea>
    </section>
    <template #footer>
      <div class="d-flex flex-wrap gap-2 w-100 align-items-center justify-content-end">
        <button v-if="allowReturn" type="button" class="btn btn-outline-danger me-auto" @click="$emit('submit', 'return')">退回（委托更改）</button>
        <button type="button" class="btn btn-light" @click="$emit('close')">关闭</button>
        <button v-if="allowSign" type="button" class="btn btn-primary" :disabled="!canSign" @click="$emit('submit', 'sign')">签字领取</button>
      </div>
    </template>
  </BootstrapModal>
</template>
