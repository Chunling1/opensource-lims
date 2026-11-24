<script setup lang="ts">
import type { ReportDistributionDetail, ReportDistributionDraft } from '../../types/reports/reportDistribution'
import { tableCellText } from '../../services/common/table'
defineProps<{ detail: ReportDistributionDetail }>()
const form = defineModel<ReportDistributionDraft>({ required: true })
const money = (value: number | null) => tableCellText(value, { money: true })
</script>

<template>
  <div class="vstack gap-3">
    <section class="rounded border px-3 py-2" aria-label="合同与委托信息">
      <dl class="row g-2 mb-0">
        <div class="col-12 col-md-6 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">关联合同</dt><dd class="mb-0 text-break">{{ detail.contract || '—' }}</dd></div>
        <div class="col-12 col-md-6 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">委托编号</dt><dd class="mb-0 text-break">{{ detail.commissionCode || '—' }}</dd></div>
        <div class="col-12 col-md-6 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">委托单位</dt><dd class="mb-0 text-break">{{ detail.customer || '—' }}</dd></div>
        <div class="col-12 col-md-6 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">项目名称</dt><dd class="mb-0 text-break">{{ detail.projectName || '—' }}</dd></div>
      </dl>
    </section>
    <section aria-label="费用清单">
      <h6 class="mb-2">费用清单</h6>
      <div class="table-responsive border rounded">
        <table class="table table-sm table-nowrap align-middle mb-0" aria-label="费用清单">
          <thead class="table-light"><tr><th>检测方案</th><th>样品编号</th><th class="text-end">数量</th><th class="text-end">应收费用</th><th>收费状态</th></tr></thead>
          <tbody><tr v-for="fee in detail.fees" :key="fee.id"><td>{{ fee.testPlan || '—' }}</td><td>{{ fee.code }}</td><td class="text-end">{{ fee.quantity }}</td><td class="text-end">{{ money(fee.amount) }}</td><td>{{ fee.paymentStatus || '—' }}</td></tr></tbody>
          <tfoot class="table-light"><tr><th colspan="3">应收总额</th><td class="text-end fw-semibold">{{ money(detail.totalAmount) }}</td><td></td></tr></tfoot>
        </table>
      </div>
    </section>
    <section class="row g-3" aria-label="发放信息">
      <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><label for="release-recipient" class="col-3 col-md-2 col-form-label">领取人</label><div class="col"><input id="release-recipient" v-model="form.recipient" class="form-control" required maxlength="100" /></div></div></div>
      <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><label for="release-date" class="col-3 col-md-2 col-form-label">领取日期</label><div class="col"><input id="release-date" v-model="form.date" class="form-control" type="date" required /></div></div></div>
      <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><label for="release-method" class="col-3 col-md-2 col-form-label">领取方式</label><div class="col"><select id="release-method" v-model="form.method" class="form-select" required :disabled="detail.form === '电子'"><option v-for="method in ['自取', '邮寄', '其他']" :key="method">{{ method }}</option></select></div></div></div>
      <div class="col-12 col-md-6"><div class="row g-2 align-items-center"><label for="release-tracking" class="col-3 col-md-2 col-form-label">快递单号</label><div class="col"><input id="release-tracking" v-model="form.trackingNumber" class="form-control" maxlength="100" :disabled="detail.form !== '纸质' || form.method !== '邮寄'" /></div></div></div>
      <div class="col-12"><div class="row g-2 align-items-center"><label for="release-address" class="col-3 col-md-1 col-form-label">邮寄地址</label><div class="col"><input id="release-address" v-model="form.mailingAddress" class="form-control" maxlength="500" :disabled="detail.form !== '纸质' || form.method !== '邮寄'" /></div></div></div>
      <div class="col-12"><div class="row g-2"><label for="release-notes" class="col-3 col-md-1 col-form-label">备注</label><div class="col"><textarea id="release-notes" v-model="form.notes" class="form-control" rows="2" maxlength="1000"></textarea></div></div></div>
    </section>
  </div>
</template>
