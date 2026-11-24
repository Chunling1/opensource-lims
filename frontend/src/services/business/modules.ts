import type { ActionDefinition, FieldDefinition, ModuleDefinition } from '../../types/lims'
const text = (key: string, label: string, required = false): FieldDefinition => ({ key, label, required })
const ref = (key: string, label: string, reference: string, required = true): FieldDefinition => ({ key, label, reference, required, type: 'select' })
const num = (key: string, label: string, min = 0, required = true): FieldDefinition => ({ key, label, type: 'number', min, required, default: min })
const date = (key: string, label: string, required = true): FieldDefinition => ({ key, label, type: 'date', required })
const select = (key: string, label: string, options: string[], required = true): FieldDefinition => ({ key, label, type: 'select', options, required, default: options[0] })
const notes: FieldDefinition = { key: 'notes', label: '备注', type: 'textarea' }
const submit: ActionDefinition = { id: 'submit', label: '提交审批', from: ['草稿', '已退回'], to: '审批中', approval: true }
const masterActions: ActionDefinition[] = [{ id: 'activate', label: '启用', from: ['草稿', '已停用'], to: '有效' }, { id: 'disable', label: '停用', from: ['有效'], to: '已停用', reason: true }]
const approvedActions: ActionDefinition[] = [submit, { id: 'archive', label: '归档', from: ['已批准'], to: '已归档' }]
function module(id: string, title: string, group: string, prefix: string, fields: FieldDefinition[], options: Partial<ModuleDefinition> = {}): ModuleDefinition {
  return { id, title, group, prefix, icon: 'ti ti-file-description', fields: [...fields, notes], initial: '草稿', editable: ['草稿', '已退回'], actions: approvedActions, roles: [group], ...options }
}
function master(id: string, title: string, group: string, prefix: string, fields: FieldDefinition[], options: Partial<ModuleDefinition> = {}) {
  return module(id, title, group, prefix, fields, { actions: masterActions, editable: ['草稿', '有效', '已停用'], ...options })
}
const order = () => ref('commissionId', '委托', 'commissions')
const sample = () => ref('sampleId', '样品', 'samples')
const project = () => ref('projectId', '检测项目', 'projects')
const money = (key = 'amount', label = '金额（元）') => num(key, label, 0.01)
const qualityActions: ActionDefinition[] = [
  { id: 'assign', label: '分派', from: ['待分派'], to: '处理中', fields: [ref('assigneeId', '责任人', 'actors')] },
  { id: 'resolve', label: '提交验证', from: ['处理中'], to: '待验证', reason: true, approval: true },
  { id: 'close', label: '关闭', from: ['已验证'], to: '已关闭' },
]
export const modules: ModuleDefinition[] = [
  master('customers', '客户与联系人', 'commissions', 'KH', [text('contact', '联系人', true), text('phone', '联系电话', true), text('address', '地址'), text('taxId', '纳税人识别号'), num('creditLimit', '信用额度（元）'), num('creditDays', '账期（天）'), date('creditUntil', '授信有效期', false)]),
  module('quotations', '报价管理', 'commissions', 'BJ', [ref('customerId', '客户', 'customers'), { key: 'projectIds', label: '检测项目', type: 'multi', reference: 'projects', required: true }, num('discount', '折扣（%）', 0, true), num('taxRate', '税率（%）'), date('validUntil', '报价有效期')]),
  module('contracts', '合同登记与评审', 'commissions', 'HT', [ref('customerId', '客户', 'customers'), ref('quotationId', '报价单', 'quotations', false), money(), date('startDate', '起始日期'), date('endDate', '截止日期'), text('requirements', '合同要求', true)]),
  module('commissions', '委托登记与查询', 'commissions', 'WT', [ref('customerId', '客户', 'customers'), ref('contractId', '合同', 'contracts', false), { key: 'projectIds', label: '检测项目', type: 'multi', reference: 'projects', required: true }, select('source', '样品来源', ['客户送样', '现场采样']), select('settlement', '结算条件', ['预付', '信用']), num('discount', '折扣（%）'), num('taxRate', '税率（%）'), date('dueDate', '要求完成日期'), text('requirements', '客户要求', true)], { actions: [
    { ...submit, label: '提交合同评审', to: '待评审' },
    { id: 'start', label: '开始执行', from: ['已受理'], to: '执行中' },
    { id: 'complete', label: '完成委托', from: ['执行中'], to: '已完成' },
    { id: 'archive', label: '归档', from: ['已完成'], to: '已归档' },
    { id: 'change', label: '申请更改', from: ['已受理', '执行中'], to: '更改审批中', approval: true, reason: true, fields: [text('requirements', '更改后的客户要求', true), date('dueDate', '更改后的要求完成日期')] },
    { id: 'cancel', label: '申请作废', from: ['已受理', '执行中'], to: '作废审批中', approval: true, reason: true },
  ] }),
  module('sampling', '采样计划与现场记录', 'sampling', 'CY', [order(), text('point', '采样点', true), date('scheduledDate', '计划日期'), ref('assigneeId', '采样人员', 'actors'), text('containers', '容器与保存条件', true)], { actions: [
    { id: 'dispatch', label: '下达任务', from: ['草稿'], to: '待采样' },
    { id: 'collect', label: '完成现场采样', from: ['待采样', '补采中'], to: '待交接', fields: [text('fieldRecord', '现场记录', true), num('quantity', '数量', 0.001), text('unit', '单位', true), text('temperature', '运输温度', true)] },
    { id: 'handover', label: '交接登记样品', from: ['待交接'], to: '已交接', fields: [text('handover', '交接记录', true)] },
    { id: 'resample', label: '安排补采', from: ['待交接', '已交接'], to: '补采中', reason: true },
  ] }),
  module('sampleLinks', '委托样品关联', 'samples', 'GL', [sample(), order()], { actions: [{ id: 'link', label: '确认关联', from: ['草稿'], to: '已关联' }] }),
  module('movements', '样品流转', 'samples', 'LZ', [sample(), select('operation', '操作类型', ['入库', '领用', '归还', '留样', '分样', '处置']), ref('locationId', '库位', 'locations', false), num('quantity', '数量', 0.001), ref('assigneeId', '经手人', 'actors'), text('destination', '用途或去向', true)], { actions: [{ id: 'post', label: '确认流转', from: ['草稿'], to: '已完成', reason: true }] }),
  master('locations', '库位管理', 'samples', 'KW', [text('room', '房间', true), text('conditions', '保存条件', true), num('capacity', '容量', 1)]),
  module('batches', '检测批次', 'testing', 'PC', [project(), ref('methodId', '检测方法', 'methods'), ref('assigneeId', '负责人', 'actors'), date('plannedDate', '检测日期')], { actions: [{ id: 'start', label: '启动批次', from: ['草稿'], to: '执行中' }, { id: 'complete', label: '结束批次', from: ['执行中'], to: '已完成' }] }),
  module('tasks', '检测任务与原始记录', 'testing', 'JC', [order(), sample(), project(), ref('methodId', '方法', 'methods'), ref('batchId', '批次', 'batches', false), ref('assigneeId', '检测人员', 'actors'), ref('equipmentId', '设备', 'equipment'), ref('lotId', '物料批次', 'inventory', false), num('consumption', '物料用量'), date('dueDate', '完成期限')], { initial: '待分派', editable: ['待分派'], actions: [
    { id: 'assign', label: '分派任务', from: ['待分派'], to: '待执行', fields: [ref('assigneeId', '检测人员', 'actors')] },
    { id: 'reassign', label: '重新分派', from: ['待执行'], to: '待执行', reason: true, fields: [ref('assigneeId', '检测人员', 'actors')] },
    { id: 'start', label: '领取样品并开始', from: ['待执行'], to: '执行中' },
    { id: 'record', label: '保存原始记录', from: ['执行中'], to: '执行中', fields: [select('resultType', '结果类型', ['定量', '定性']), num('rawValue', '原始读数', -1000000000), text('qualitative', '定性结果'), text('rawRecord', '原始记录', true), select('qc', '质量控制', ['通过', '失败'])] },
    { id: 'submit', label: '提交结果复核', from: ['执行中'], to: '待复核', approval: true },
    { id: 'retest', label: '创建复测任务', from: ['已完成'], to: '已完成', reason: true },
    { id: 'copyStructure', label: '复制记录结构', from: ['已完成'], to: '已完成', reason: true },
    { id: 'change', label: '申请数据更改', from: ['已完成'], to: '更改审批中', approval: true, reason: true },
    { id: 'finishSample', label: '检毕样品归还', from: ['已完成'], to: '已完成', fields: [ref('locationId', '归还库位', 'locations')] },
  ] }),
  module('outsourcing', '外包检测与验收', 'testing', 'WB', [order(), sample(), project(), ref('methodId', '方法', 'methods'), ref('supplierId', '供应商', 'suppliers'), money('amount', '外包费用（元）'), date('dueDate', '交付日期')], { actions: [submit, { id: 'deliver', label: '登记交付', from: ['已批准'], to: '待验收', fields: [text('result', '外包结果', true), text('certificate', '供应商报告编号', true)] }, { id: 'accept', label: '提交验收', from: ['待验收'], to: '验收中', approval: true }] }),
  module('reports', '报告编制与查询', 'reports', 'BG', [order(), ref('templateId', '报告模板', 'reportTemplates'), text('conclusion', '结论', true)], { actions: [
    { id: 'submit', label: '提交审核', from: ['草稿', '已退回'], to: '待审核', approval: true },
    { id: 'sign', label: '提交批准签发', from: ['已审核'], to: '待批准', approval: true, roles: ['reviewer'] },
    { id: 'release', label: '发放报告', from: ['已签发'], to: '已发放' },
    { id: 'exception', label: '申请例外发放', from: ['已签发'], to: '例外审批中', approval: true, reason: true, roles: ['finance'] },
    { id: 'archive', label: '归档', from: ['已发放'], to: '已归档' },
  ] }),
  module('reportChanges', '报告更改申请', 'reports', 'BGG', [ref('reportId', '原报告', 'reports'), select('source', '申请来源', ['内部申请', '外部申请']), text('reason', '更改原因', true), text('conclusion', '修订结论', true)], { actions: [submit] }),
  master('reportTemplates', '报告模板', 'reports', 'MB', [text('header', '报告抬头', true), text('title', '报告标题', true), { key: 'basicFields', label: '基本资料', type: 'multi', options: ['客户', '委托编号', '样品', '方法'], required: true }, text('resultColumns', '结果表列名（逗号分隔）', true), text('signatureLabel', '签署区名称', true), text('appendix', '附录'), text('footer', '页脚', true)]),
  master('prices', '计价规则与调整', 'finance', 'JG', [project(), money('price', '单价（元）'), num('laborCost', '人工成本（元）'), date('effectiveDate', '生效日期')]),
  module('receivables', '应收账款', 'finance', 'YS', [order(), money(), date('dueDate', '到期日期')], { initial: '待收款', editable: [], actions: [] }),
  module('payments', '收款与核销', 'finance', 'SK', [order(), money(), select('method', '收款方式', ['银行转账', '现金', '其他']), text('reference', '收款凭证号', true), date('paidDate', '收款日期')], { actions: [{ id: 'post', label: '入账核销', from: ['草稿'], to: '已入账' }] }),
  module('refunds', '退款与冲销', 'finance', 'TK', [ref('paymentId', '原收款', 'payments'), money(), select('type', '调整类型', ['退款', '冲销']), text('reason', '原因', true)], { actions: [submit] }),
  module('invoices', '开票登记', 'finance', 'FP', [order(), text('invoiceNumber', '发票号码', true), money(), date('invoiceDate', '开票日期'), text('buyerTaxId', '购方税号', true)], { actions: [{ id: 'post', label: '确认登记', from: ['草稿'], to: '已登记' }] }),
  module('payables', '外包应付', 'finance', 'YF', [ref('outsourcingId', '外包单', 'outsourcing'), money(), date('dueDate', '付款期限')], { initial: '待付款', editable: [], actions: [{ id: 'pay', label: '登记付款', from: ['待付款'], to: '已付款', fields: [text('reference', '付款凭证号', true)] }] }),
  master('personnel', '人员档案与能力', 'quality', 'RY', [ref('actorId', '系统人员', 'actors'), text('position', '岗位', true), { key: 'projectIds', label: '授权检测项目', type: 'multi', reference: 'projects', required: true }, date('validUntil', '授权有效期'), text('qualification', '资质证明', true)]),
  module('training', '培训与考核', 'quality', 'PX', [ref('personnelId', '人员', 'personnel'), date('scheduledDate', '培训日期'), text('content', '培训内容', true), text('assessment', '考核结果', true)]),
  master('equipment', '仪器设备台账', 'quality', 'SB', [text('serial', '出厂编号', true), text('model', '型号', true), text('location', '位置', true), date('validUntil', '检定/校准有效期'), date('checkUntil', '期间核查有效期'), select('condition', '设备状态', ['正常', '维修', '停用'])]),
  module('equipmentPlans', '设备计划与执行', 'quality', 'SBJ', [ref('equipmentId', '设备', 'equipment'), select('type', '计划类型', ['周期检定', '校准', '期间核查', '维护', '维修']), date('scheduledDate', '计划日期'), ref('assigneeId', '执行人', 'actors')], { actions: [{ id: 'execute', label: '记录执行', from: ['草稿', '已退回'], to: '待验证', approval: true, fields: [select('result', '执行结论', ['合格', '不合格']), date('validUntil', '下次到期日期'), text('record', '执行记录', true)] }] }),
  module('equipmentLoans', '设备领用与归还', 'quality', 'SBL', [ref('equipmentId', '设备', 'equipment'), ref('assigneeId', '领用人', 'actors'), date('dueDate', '预计归还日期')], { actions: [{ id: 'borrow', label: '确认领用', from: ['草稿'], to: '使用中' }, { id: 'return', label: '归还设备', from: ['使用中'], to: '已归还', fields: [text('condition', '归还状态', true)] }] }),
  master('suppliers', '供应商及评价', 'quality', 'GYS', [text('contact', '联系人', true), text('qualification', '资质与外包能力', true), date('validUntil', '资质有效期'), num('score', '评价分数', 0), text('evaluation', '评价记录', true)]),
  module('purchases', '采购申请与验收', 'quality', 'CG', [ref('supplierId', '供应商', 'suppliers'), text('material', '物料名称', true), num('quantity', '数量', 0.001), text('unit', '单位', true), money(), date('dueDate', '到货日期')], { actions: [submit, { id: 'receive', label: '验收入库', from: ['已批准'], to: '已入库', fields: [text('batch', '批号', true), date('validUntil', '有效期'), text('certificate', '证书或验收记录', true)] }] }),
  master('inventory', '试剂耗材与标准物质', 'quality', 'WL', [select('type', '物料类型', ['试剂', '耗材', '标准物质']), text('batch', '批号', true), num('quantity', '初始库存', 0), text('unit', '单位', true), money('unitCost', '单位成本（元）'), date('validUntil', '有效期'), text('certificate', '证书编号'), ref('supplierId', '供应商', 'suppliers', false)], { editable: ['草稿'] }),
  module('stockMoves', '领退料、盘点与报废', 'quality', 'WLL', [ref('lotId', '物料批次', 'inventory'), select('operation', '操作类型', ['领用', '退库', '盘盈', '盘亏', '报废']), num('quantity', '数量', 0.001), order(), text('reason', '事由', true)], { actions: [{ id: 'post', label: '确认库存变动', from: ['草稿'], to: '已完成' }] }),
  module('accreditations', '认可能力管理', 'quality', 'RK', [text('certificate', '认可证书编号', true), text('revision', '范围版本', true), ref('siteId', '检测场所', 'sites'), { key: 'projectIds', label: '认可项目', type: 'multi', reference: 'projects', required: true }, { key: 'methodIds', label: '方法范围', type: 'multi', reference: 'methods', required: true }, text('limits', '限制条件'), date('validUntil', '有效期')]),
  module('documents', '受控文件与检测标准', 'quality', 'WJ', [select('type', '文件类别', ['体系文件', '作业指导书', '检测标准', '知识资料']), text('revision', '版本', true), date('effectiveDate', '生效日期'), { key: 'methodIds', label: '关联方法', type: 'multi', reference: 'methods' }, text('content', '文件内容摘要', true)], { actions: [submit, { id: 'publish', label: '发布生效', from: ['已批准'], to: '已发布' }, { id: 'void', label: '作废', from: ['已发布'], to: '已作废', reason: true }] }),
  module('qualityCases', '质量事项与改进', 'quality', 'ZL', [select('type', '事项类别', ['质控异常', '不符合项', '投诉', '内部审核', '管理评审', '风险与改进']), ref('commissionId', '关联委托', 'commissions', false), ref('taskId', '关联任务', 'tasks', false), select('blocking', '是否阻断签发', ['是', '否']), text('description', '问题描述', true), date('dueDate', '整改期限')], { initial: '待分派', editable: ['待分派', '处理中'], actions: qualityActions }),
  master('projects', '检测项目', 'system', 'XM', [text('unit', '结果单位', true), select('resultType', '结果类型', ['定量', '定性']), num('precision', '小数位数'), num('lower', '下限', -1000000000), num('upper', '上限', -1000000000), money('price', '默认单价（元）'), num('laborCost', '人工成本（元）')]),
  master('methods', '检测方法与记录配置', 'system', 'FF', [project(), text('standard', '标准编号', true), text('revision', '方法版本', true), text('formula', '计算公式（变量 x）', true), text('recordFields', '记录字段（逗号分隔）', true), text('tableColumns', '明细表列（逗号分隔）'), date('validUntil', '有效期')]),
  master('departments', '组织架构', 'system', 'BM', [text('parent', '上级机构'), text('manager', '负责人', true)]),
  master('sites', '检测场所', 'system', 'CS', [ref('departmentId', '所属部门', 'departments'), text('address', '地址', true), text('conditions', '环境条件', true)]),
  master('users', '用户与角色', 'system', 'YH', [text('login', '账号', true), ref('departmentId', '部门', 'departments'), { key: 'roles', label: '角色', type: 'multi', options: ['admin', 'commissions', 'sampling', 'samples', 'testing', 'reviewer', 'approver', 'reports', 'finance', 'quality', 'system'], required: true }, select('scope', '数据范围', ['department', 'all'])]),
  master('approvalConfigs', '审批配置', 'system', 'SPP', [select('moduleId', '业务模块', ['commissions', 'quotations', 'contracts', 'tasks', 'reports', 'reportChanges', 'refunds', 'outsourcing', 'qualityCases', 'equipmentPlans', 'training', 'purchases', 'accreditations', 'documents']), { key: 'approverIds', label: '指定审批人', type: 'multi', reference: 'actors', required: true }]),
  master('dictionaries', '基础字典', 'system', 'ZD', [select('category', '字典分类', ['样品类别', '单位', '保存条件']), text('value', '字典值', true)]),
  master('settings', '系统设置与编号规则', 'system', 'SZ', [select('setting', '设置项', ['机构名称', '联系电话', '机构地址', '编号前缀']), text('moduleId', '适用模块'), text('value', '设置值', true)]),
]
for (const m of modules) {
  if (['equipment', 'equipmentPlans', 'equipmentLoans'].includes(m.id)) m.roles = ['quality', 'equipment']
  if (['inventory', 'stockMoves', 'purchases', 'suppliers'].includes(m.id)) m.roles = ['quality', 'inventory']
}
const roleField = modules.find(m => m.id === 'users')!.fields.find(f => f.key === 'roles')!
roleField.options!.push('equipment', 'inventory')
export const moduleMap = Object.fromEntries(modules.map(m => [m.id, m])) as Record<string, ModuleDefinition>
export const groupLabels: Record<string, string> = { commissions: '委托管理', sampling: '采样管理', samples: '样品管理', testing: '检测管理', reports: '报告管理', finance: '财务管理', quality: '质量体系', system: '系统管理' }
export function initialFields(definition: ModuleDefinition) { return Object.fromEntries(definition.fields.map(f => [f.key, f.default ?? (f.type === 'multi' ? [] : '')])) }
