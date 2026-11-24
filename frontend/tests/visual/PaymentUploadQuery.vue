<script setup lang="ts">
import { reactive } from 'vue'
import Query from '../../src/platformUi/reports/ReportQueryListPresentation.vue'
import SchemaForm from '../../src/components/forms/SchemaForm.vue'
import { createReportOutputPresentation } from '../../src/platformUi/reports/reportOutputPresentation'
import { sampleSchema } from '../../src/views/commissions/forms/sampleSchema'
import { emptySampleDetails } from '../../src/types/commissions/sampleForm'


 const c=reactive<any>({pageKey:'query',pageName:'报告查询',workRows:[{reportNo:'QA-2026YP-0001',sampleNo:'2026YP-0001',client:'虚拟委托单位',project:'气密性能、水密性能、抗风压性能',dataStatus:'报告签发中',sampleStatus:'已领取',version:'V1',deadline:'2026-10-30',sampleOrProjectName:'隔热铝合金窗',testDepartment:'虚拟检测部门',sampleInboundDate:'2026-10-22',sampleReceiver:'领样人员甲',reportReviewedBy:'审核人员乙',reportApprovedBy:'批准人员丙',sealConfirmedBy:'',reportReviewedAt:'2026-10-28 09:30:00'}],session:{canAction:()=>true},openForm:()=>{},refreshReportList:async()=>{}})
 const context=createReportOutputPresentation(c)
 const model=reactive<any>({form:{details:emptySampleDetails()},options:{choices:{}}})
 const fields=sampleSchema({choices:{}} as any).sections.find(s=>s.id==='sample-fees')!.fields.filter(f=>f.id==='sample-paymentMethod')
 const schema={sections:[{id:'payment',title:'结算信息',fields}]}

</script>
<template><main class="container-fluid p-3 p-lg-4"><div class="d-flex flex-wrap justify-content-between mb-3"><h4>报告查询与支付方式</h4><span class="badge bg-warning-subtle text-warning">本地验收 · 全部为虚拟数据</span></div><SchemaForm :schema="schema" :model="model"/><Query :context="context"/></main></template>
