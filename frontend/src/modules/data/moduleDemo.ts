// 本地演示专用数据。仅在 VITE_USE_BACKEND != 1 时使用，不进入生产接口。
export const demoWorkflowRows = [
  {
    reportNo: 'DEMO-R-1001', sampleNo: 'DEMO-S-1001', client: '演示客户一',
    project: '净化设备性能检测', department: '演示检测一部', owner: '演示主检甲',
    template: '产品检测报告', version: 'V1', sign: '未签章', deadline: '2026-08-25',
    status: '检测录入中', sampleStatus: '已领取', date: '2026-08-18',
    samplePickup: { pickupTime: '2026-08-18 09:10' },
    workflowDates: { samplePickupAt: '2026-08-18 09:10' },
  },
  {
    reportNo: 'DEMO-R-1002', sampleNo: 'DEMO-S-1002', client: '演示客户二',
    project: '建筑门窗气密性能', department: '演示检测二部', owner: '演示主检乙',
    template: '工程检测报告', version: 'V2', sign: '未签章', deadline: '2026-08-24',
    status: '检测更改中', sampleStatus: '已领取', date: '2026-08-17',
    returnInfo: { source: '报告审核', note: '请补充环境条件和第二次实测值' },
    samplePickup: { pickupTime: '2026-08-17 10:20' },
    workflowDates: { samplePickupAt: '2026-08-17 10:20' },
  },
  {
    reportNo: 'DEMO-R-1003', sampleNo: 'DEMO-S-1003', client: '演示客户三',
    project: '保温材料导热系数', department: '演示检测一部', owner: '演示主检甲',
    template: '产品检测报告', version: 'V1', sign: '未签章', deadline: '2026-08-23',
    status: '退回待重传', sampleStatus: '已领取', date: '2026-08-16',
    returnInfo: { source: '报告批准', note: '检测依据版本需复核后重新提交' },
    samplePickup: { pickupTime: '2026-08-16 14:30' },
    workflowDates: { samplePickupAt: '2026-08-16 14:30' },
  },
  {
    reportNo: 'DEMO-R-1004', sampleNo: 'DEMO-S-1004', client: '演示客户四',
    project: '建筑材料燃烧性能', department: '演示检测三部', owner: '演示主检丙',
    template: '产品检测报告', version: 'V1', sign: '未签章', deadline: '2026-08-22',
    status: '委托更改中', sampleStatus: '待入库', date: '2026-08-15',
    returnInfo: { source: '合同评审', note: '委托单位申请调整检测参数与报告份数' },
  },
]

const financeBase = {
  contractNo: 'DEMO-HT-2026-01', department: '演示业务部', paymentMethod: '',
  paymentReference: '', paymentDate: '', invoiceNo: '', invoiceType: '', invoiceDate: '',
  settlementNo: '', settlementDate: '', refundDate: '', note: '演示数据，仅供功能体验',
  version: 1, createdBy: 'demo_finance', updatedBy: 'demo_finance',
  createdAt: '2026-08-18 09:00', updatedAt: '2026-08-18 09:00',
}

export const demoFinanceBills = [
  { ...financeBase, id: 9101, billNo: 'DEMO-F-1001', entrustNo: 'DEMO-WT-1001', client: '演示客户一', projectName: '净化设备性能检测', amountDue: '12800.00', pendingPayment: '0.00', amountReceived: '0.00', amountInvoiced: '0.00', amountRefunded: '0.00', netReceived: '0.00', outstanding: '12800.00', status: '待计价' },
  { ...financeBase, id: 9102, billNo: 'DEMO-F-1002', entrustNo: 'DEMO-WT-1002', client: '演示客户二', projectName: '建筑门窗气密性能', amountDue: '8600.00', pendingPayment: '0.00', amountReceived: '0.00', amountInvoiced: '0.00', amountRefunded: '0.00', netReceived: '0.00', outstanding: '8600.00', status: '待收款', priceAt: '2026-08-16' },
  { ...financeBase, id: 9103, billNo: 'DEMO-F-1003', entrustNo: 'DEMO-WT-1003', client: '演示客户三', projectName: '保温材料导热系数', amountDue: '5600.00', pendingPayment: '5600.00', amountReceived: '0.00', amountInvoiced: '0.00', amountRefunded: '0.00', netReceived: '0.00', outstanding: '5600.00', status: '待收款确认', paymentMethod: '银行转账', paymentReference: 'DEMO-LS-1003', paymentDate: '2026-08-17' },
  { ...financeBase, id: 9104, billNo: 'DEMO-F-1004', entrustNo: 'DEMO-WT-1004', client: '演示客户四', projectName: '建筑材料燃烧性能', amountDue: '16800.00', pendingPayment: '0.00', amountReceived: '16800.00', amountInvoiced: '0.00', amountRefunded: '0.00', netReceived: '16800.00', outstanding: '0.00', status: '待开票', paymentDate: '2026-08-16', paymentConfirmedAt: '2026-08-16' },
  { ...financeBase, id: 9105, billNo: 'DEMO-F-1005', entrustNo: 'DEMO-WT-1005', client: '演示客户五', projectName: '幕墙抗风压性能', amountDue: '22000.00', pendingPayment: '0.00', amountReceived: '22000.00', amountInvoiced: '22000.00', amountRefunded: '0.00', netReceived: '22000.00', outstanding: '0.00', status: '待结算', invoiceNo: 'DEMO-FP-1005', invoiceDate: '2026-08-15' },
  { ...financeBase, id: 9106, billNo: 'DEMO-F-1006', entrustNo: 'DEMO-WT-1006', client: '演示客户六', projectName: '室内环境检测', amountDue: '6800.00', pendingPayment: '0.00', amountReceived: '6800.00', amountInvoiced: '6800.00', amountRefunded: '0.00', netReceived: '6800.00', outstanding: '0.00', status: '已结算', settlementNo: 'DEMO-JS-1006', settlementDate: '2026-08-14' },
]

export const demoPersonnel = [
  { id: 9201, name: '演示人员甲', code: 'demo_tester_a', dept: '演示检测一部', title: '工程师', position: '主检', roleName: '检测人员', departmentId: 1, accountEnabled: true, accountStatus: '正常', assignedDepts: ['演示检测一部'], permissions: ['检测数据录入', '电子原始记录'] },
  { id: 9202, name: '演示人员乙', code: 'demo_reviewer', dept: '演示检测一部', title: '高级工程师', position: '审核人', roleName: '报告审核', departmentId: 1, accountEnabled: true, accountStatus: '正常', assignedDepts: ['演示检测一部'], permissions: ['报告审核'] },
  { id: 9203, name: '演示人员丙', code: 'demo_approver', dept: '演示质量部', title: '正高级工程师', position: '批准人', roleName: '报告批准', departmentId: 2, accountEnabled: true, accountStatus: '正常', assignedDepts: ['演示质量部'], permissions: ['报告批准'] },
  { id: 9204, name: '演示样品员', code: 'demo_sample', dept: '演示样品室', title: '助理工程师', position: '样品管理员', roleName: '样品管理', departmentId: 3, accountEnabled: true, accountStatus: '正常', assignedDepts: ['演示样品室'], permissions: ['样品入库', '样品出库'] },
]

export const demoEquipment = [
  { id: 9301, archiveNo: 'DEMO-EQ-001', name: '导热系数测定仪', spec: 'DRY-300', dept: '演示检测一部', status: '可用', keeper: '演示人员甲', lastCalDate: '2026-01-15', planCalDate: '2027-01-14', validUntil: '2027-01-14', maker: '演示设备厂商', factoryNo: 'DEMO-2025-001' },
  { id: 9302, archiveNo: 'DEMO-EQ-002', name: '门窗物理性能检测装置', spec: 'MC-6000', dept: '演示检测二部', status: '可用', keeper: '演示人员乙', lastCalDate: '2026-03-10', planCalDate: '2027-03-09', validUntil: '2027-03-09', maker: '演示设备厂商', factoryNo: 'DEMO-2025-002' },
  { id: 9303, archiveNo: 'DEMO-EQ-003', name: '材料燃烧性能试验箱', spec: 'B1-2026', dept: '演示检测三部', status: '限制使用', keeper: '演示人员丙', lastCalDate: '2025-09-01', planCalDate: '2026-09-01', validUntil: '2026-09-01', maker: '演示设备厂商', factoryNo: 'DEMO-2024-003', remark: '待完成期间核查' },
]

export const demoStandardMasters = [
  { id: 9401, code: 'GB/T DEMO-1001', name: '演示用建筑材料热工性能试验方法', category: '国家标准', authKind: 'CMA/CNAS', department: '演示检测一部', status: '现行', expired: false },
  { id: 9402, code: 'JGJ/T DEMO-1002', name: '演示用建筑门窗性能检测方法', category: '行业标准', authKind: 'CMA', department: '演示检测二部', status: '现行', expired: false },
  { id: 9403, code: 'T/DEMO 1003', name: '演示用环境热工现场检测规程', category: '团体标准', authKind: '非资质', department: '演示检测三部', status: '待实施', expired: false },
]

export const demoControlledStandards = demoStandardMasters.map((item, index) => ({
  id: item.id, controlledNo: `DEMO-SD-${String(index + 1).padStart(3, '0')}`, code: item.code,
  name: item.name, authKind: item.authKind, outOfScope: item.authKind === '非资质', category: item.category,
  location: `演示资料柜-${index + 1}`, issueCount: '1', issuer: '演示资料员', useDepts: [item.department],
  implDate: index === 2 ? '2026-10-01' : '2026-01-01', voidDate: '', delayDays: '0', replaceNo: '',
  isEnglish: false, remark: '演示数据，仅供功能体验', status: item.status,
}))
