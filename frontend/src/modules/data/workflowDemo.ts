import type { SampleRow } from '@/services/pipeline'

const shared = {
  department: '演示检测部',
  owner: '演示主检',
  registrar: '演示登记员',
  registrarDepartment: '演示受理部',
  handler: '演示经办人',
  handlerDepartment: '演示受理部',
  testDepartment: '演示检测部',
  erpProjectType: '演示项目',
  reportCategory: '普通委托',
  reportFormat: '产品报告',
  testCategory: '委托',
  sealRequirement: 'CMA + CNAS',
} satisfies Partial<SampleRow>

export const sampleRegisterDemoRows: SampleRow[] = [
  {
    ...shared,
    entrustNo: 'DEMO-WT-0001',
    sampleNo: 'DEMO-S-0001',
    reportNo: 'DEMO-R-0001',
    project: '净化能效',
    projectName: '演示净化设备',
    sampleOrProjectName: '演示净化设备',
    testItems: '净化能效、风量',
    client: '演示客户一',
    status: '样品登记中',
    sampleRegState: '登记中',
    sampleStatus: '待登记',
    dataStatus: '样品登记中',
    schemeDisplay: 'DEMO-FA-01 · 净化设备检测方案',
    amount: '1200.00',
    sampleRegisteredAt: '2026-08-18',
    sendDate: '2026-08-18',
    reportTitle: '演示净化设备检测报告',
  },
  {
    ...shared,
    entrustNo: 'DEMO-WT-0002',
    sampleNo: 'DEMO-S-0002',
    reportNo: 'DEMO-R-0002',
    project: '门窗气密性',
    projectName: '演示建筑门窗',
    sampleOrProjectName: '演示建筑门窗',
    testItems: '气密性、水密性',
    client: '演示客户二',
    status: '待合同评审',
    sampleRegState: '登记完成',
    sampleStatus: '待评审',
    dataStatus: '待合同评审',
    schemeDisplay: 'DEMO-FA-02 · 建筑门窗检测方案',
    amount: '2600.00',
    sampleRegisteredAt: '2026-08-17',
    sendDate: '2026-08-17',
    reportTitle: '演示建筑门窗检测报告',
  },
]

export const sampleInboundDemoRows: SampleRow[] = [
  {
    ...sampleRegisterDemoRows[1],
    status: '待入库',
    sampleStatus: '待入库',
    dataStatus: '合同评审已通过',
  },
  {
    ...shared,
    entrustNo: 'DEMO-WT-0003',
    sampleNo: 'DEMO-S-0003',
    reportNo: 'DEMO-R-0003',
    project: '保温材料导热系数',
    projectName: '演示保温材料',
    client: '演示客户三',
    status: '待入库',
    sampleStatus: '待入库',
    dataStatus: '合同评审已通过',
  },
]

export const sampleOutboundDemoRows: SampleRow[] = [
  {
    ...sampleInboundDemoRows[0],
    status: '待领取',
    sampleStatus: '已入库',
    dataStatus: '待出库领取',
  },
  {
    ...sampleInboundDemoRows[1],
    status: '检测录入中',
    sampleStatus: '已领取',
    dataStatus: '尚未保存检测数据',
    dataEntryStarted: false,
    canRecallSampleOutbound: true,
  },
]
