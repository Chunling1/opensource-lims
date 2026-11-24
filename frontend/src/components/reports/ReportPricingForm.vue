<script setup lang="ts">
import type { ReportPricingDetail, ReportPricingTotals } from '../../types/reports/reportPricing'
import { tableCellText } from '../../services/common/table'
defineProps<{ detail: ReportPricingDetail }>()
const form = defineModel<ReportPricingTotals>({ required: true })
const totals = [{ key: 'standardPrice', label: '标准价格' }, { key: 'discountPrice', label: '折扣价格' }, { key: 'actualPrice', label: '实际价格' }] as const
const money = (value: number | null) => tableCellText(value, { money: true })
function setPrice(key: keyof ReportPricingTotals, event: Event) {
  const input = event.target as HTMLInputElement
  form.value[key] = input.value === '' ? null : input.valueAsNumber
}
</script>

<template>
  <div class="vstack gap-3">
    <section class="rounded border px-3 py-2" aria-label="计价信息">
      <dl class="row g-2 mb-0">
        <div class="col-12 col-md-6 col-xl-3 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">样品编号</dt><dd class="mb-0 text-break">{{ detail.code }}</dd></div>
        <div class="col-12 col-md-6 col-xl-4 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">检测方案</dt><dd class="mb-0 text-break">{{ detail.testPlan || '—' }}</dd></div>
        <div class="col-12 col-md-6 col-xl-3 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">计价方式</dt><dd class="mb-0">{{ detail.pricingMethod || '—' }}</dd></div>
        <div class="col-12 col-md-6 col-xl-2 d-flex gap-2"><dt class="fw-normal text-muted flex-shrink-0">样品数量</dt><dd class="mb-0">{{ detail.quantity }}</dd></div>
      </dl>
    </section>
    <div class="row g-3">
      <div v-for="field in totals" :key="field.key" class="col-12 col-md-4">
        <div class="row g-2 align-items-center">
          <label :for="`reprice-${field.key}`" class="col-auto col-form-label">{{ field.label }}</label>
          <div class="col"><input :id="`reprice-${field.key}`" :value="form[field.key]" class="form-control" type="number" min="0" max="999999999.99" step="0.01" required @input="setPrice(field.key, $event)" /></div>
        </div>
      </div>
    </div>
    <section v-for="group in [{ title: '检测参数收费项', label: '检测参数', items: detail.parameterItems }, { title: '其他收费项', label: '收费项', items: detail.otherItems }]" :key="group.title">
      <h6 class="mb-2">{{ group.title }}</h6>
      <div class="table-responsive border rounded">
        <table class="table table-sm table-nowrap align-middle mb-0" :aria-label="group.title">
          <thead class="table-light"><tr><th>{{ group.label }}</th><th class="text-end">计价数量取值</th><th class="text-end">标准价格</th><th class="text-end">折扣率</th><th class="text-end">折扣价格</th><th class="text-end">实际价格</th></tr></thead>
          <tbody>
            <tr v-for="item in group.items" :key="item.id"><td class="text-wrap text-break">{{ item.name }}</td><td class="text-end">{{ tableCellText(item.quantity, {}) }}</td><td class="text-end">{{ money(item.standardPrice) }}</td><td class="text-end">{{ money(item.discountRate) }}</td><td class="text-end">{{ money(item.discountPrice) }}</td><td class="text-end">{{ money(item.actualPrice) }}</td></tr>
            <tr v-if="!group.items.length"><td colspan="6" class="text-center text-muted py-2">暂无收费项</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
