export const sampleRows = [
  {
    sampleNo: 'HN-S-202512-001',
    reportNo: 'BG-202512-0148',
    project: '混凝土抗压',
    client: '示例建设集团',
    projectName: '星河湾三期',
    status: '检测数据录入',
    tag: '超期',
    owner: '李主检',
    date: '2025-12-04',
  },
  {
    sampleNo: 'HN-S-202512-002',
    reportNo: 'BG-202512-0152',
    project: '钢筋拉伸',
    client: '示例华东客户',
    projectName: '云岭学校扩建',
    status: '报告审核',
    tag: '正常',
    owner: '周审核',
    date: '2025-12-05',
  },
  {
    sampleNo: 'HN-S-202512-003',
    reportNo: 'BG-202512-0155',
    project: '防水卷材',
    client: '城投开发',
    projectName: '西站综合体',
    status: '报告批准',
    tag: '加急',
    owner: '赵批准',
    date: '2025-12-06',
  },
  {
    sampleNo: 'HN-S-202512-004',
    reportNo: 'BG-202512-0160',
    project: '砂浆配合比',
    client: '市政二公司',
    projectName: '滨河路改造',
    status: '样品出库',
    tag: '正常',
    owner: '王样管',
    date: '2025-12-06',
  },
  {
    sampleNo: 'HN-S-202512-005',
    reportNo: 'BG-202512-0163',
    project: '门窗气密性',
    client: '恒远置业',
    projectName: '湖畔名苑',
    status: '任务处理',
    tag: '外检',
    owner: '陈工',
    date: '2025-12-07',
  },
]

export const workflowProfiles = {
  entrust: {
    title: '委托流程',
    note: '合同评审通过后进入样品接收，外部ERP合同编号会同步到财务和报告。',
    steps: ['委托登记', '资料校验', '合同评审', '计价确认', '外部ERP推送', '样品接收'],
    activeByPage: {
      registration: 0,
      contract_review: 2,
      query: 5,
      change: 3,
      void_approval: 2,
    },
  },
  sample: {
    title: '样品流转流程',
    note: '外检样品可跳过入库/出库，直接进入任务处理和检测记录。',
    steps: ['样品接收', '样品入库', '任务关联', '样品出库', '样品领取', '留样/处置'],
    activeByPage: {
      inbound: 1,
      outbound: 3,
      disposal: 5,
      flow_query: 4,
    },
  },
  testing: {
    title: '检测流程',
    note: '自动采集异常时需填写异常原因，校核通过后才能进入报告生成。',
    steps: ['任务分配', '样品领取', '检测准备', '数据录入', '自动采集', '数据校核', '原始记录确认'],
    activeByPage: {
      assignment: 0,
      sample_pickup: 1,
      task_query: 2,
      data_entry: 3,
      data_check: 5,
      data_change: 5,
      completed_sample_handling: 6,
    },
  },
  report: {
    title: '报告流程',
    note: '委托/样品登记 → 合同评审 → 样品入库 → 检测数据录入 → 报告审核 → 批准 → 打印 → 发放。',
    steps: ['委托/样品登记', '合同评审', '样品入库', '检测数据录入', '报告审核', '报告批准', '报告签发', '报告归档', '查询/更改'],
    activeByPage: {
      contract_review: 1,
      review: 4,
      approval: 5,
      print: 6,
      archive: 7,
      query: 9,
      interim_report: 4,
      change_request: 9,
    },
  },
  finance: {
    title: '财务流程',
    note: '计价、收款、开票、结算与外部ERP同步保持一致。',
    steps: ['费用计价', '收款登记', '收款确认', '发票管理', '结算确认', '退款处理'],
    activeByPage: {
      pricing: 0,
      payment_registration: 1,
      payment_confirmation: 2,
      invoice: 3,
      settlement: 4,
      account_refund: 5,
    },
  },
  quality: {
    title: '质量体系流程',
    note: '科室版页面复用全局页面组件，仅通过权限和数据范围过滤。',
    steps: ['台账维护', '计划制定', '期间核查', '周期检定', '供应商评价', '记录归档'],
    activeByPage: {
      personnel_registration: 0,
      equipment_ledger: 0,
      equipment_ledger_department: 0,
      monthly_calibration_plan: 1,
      supplier_evaluation: 4,
      reference_material: 0,
      consumables: 0,
      standard_library: 0,
      standard_library_department: 0,
      test_environment: 2,
      daily_affairs: 3,
      daily_affairs_approval: 5,
    },
  },
  system: {
    title: '系统配置流程',
    note: '系统配置变更需留痕，涉及流程和接口的配置建议走审批。',
    steps: ['参数维护', '审批设置', '项目流程', '接口配置', '用户权限', '日志审计'],
    activeByPage: {
      runtime_parameters: 0,
      approval_settings: 1,
      project_workflow: 2,
      custom_project: 2,
      integration_erp: 3,
      sms_settings: 3,
      user: 4,
      logs: 5,
    },
  },
} as const

export const entrustRows = [
  {
    no: 'WT-202512-0031',
    client: '示例建设集团',
    projectName: '星河湾三期',
    contractNo: 'KD-2025-1188',
    projectType: '见证取样',
    amount: '¥18,600',
    status: '合同评审',
    owner: '市场受理',
    date: '2025-12-04',
  },
  {
    no: 'WT-202512-0032',
    client: '示例华东客户',
    projectName: '云岭学校扩建',
    contractNo: 'KD-2025-1193',
    projectType: '委托检测',
    amount: '¥9,420',
    status: '已推送外部ERP',
    owner: '受理专员',
    date: '2025-12-05',
  },
  {
    no: 'WT-202512-0033',
    client: '城投开发',
    projectName: '西站综合体',
    contractNo: '待生成',
    projectType: '监督抽检',
    amount: '待计价',
    status: '待补资料',
    owner: '客户经理',
    date: '2025-12-06',
  },
]

export const testingRows = [
  {
    taskNo: 'JC-202512-0216',
    sampleNo: 'HN-S-202512-001',
    project: '混凝土抗压',
    standard: 'GB/T 50081-2019',
    instrument: '压力试验机 YAW-2000',
    collectStatus: '自动采集完成',
    result: '待主检确认',
    owner: '李主检',
    date: '2025-12-04',
  },
  {
    taskNo: 'JC-202512-0217',
    sampleNo: 'HN-S-202512-002',
    project: '钢筋拉伸',
    standard: 'GB/T 228.1-2021',
    instrument: '万能材料试验机',
    collectStatus: '人工录入',
    result: '数据校核中',
    owner: '陈工',
    date: '2025-12-05',
  },
  {
    taskNo: 'JC-202512-0218',
    sampleNo: 'HN-S-202512-003',
    project: '防水卷材',
    standard: 'GB/T 328.8-2007',
    instrument: '拉力试验机',
    collectStatus: '采集异常',
    result: '需填写异常原因',
    owner: '周工',
    date: '2025-12-06',
  },
]

export const financeRows = [
  {
    billNo: 'FY-202512-0081',
    entrustNo: 'WT-202512-0031',
    client: '示例建设集团',
    amount: '¥18,600',
    paid: '¥10,000',
    invoice: '未开票',
    erp: '已推送',
    status: '待收款',
    date: '2025-12-04',
  },
  {
    billNo: 'FY-202512-0082',
    entrustNo: 'WT-202512-0032',
    client: '示例华东客户',
    amount: '¥9,420',
    paid: '¥9,420',
    invoice: '已开票',
    erp: '已推送',
    status: '已结算',
    date: '2025-12-05',
  },
  {
    billNo: 'FY-202512-0083',
    entrustNo: 'WT-202512-0033',
    client: '城投开发',
    amount: '待计价',
    paid: '-',
    invoice: '未开票',
    erp: '待推送',
    status: '待计价',
    date: '2025-12-06',
  },
  {
    billNo: 'FY-VH-2026-0705',
    entrustNo: 'WT-VH-2026-0705',
    client: '城建节能科技有限公司',
    amount: '¥12,800',
    paid: '¥0',
    invoice: '未开票',
    erp: '待推送',
    status: '虚拟核查 - 待计价',
    date: '2026-07-09',
  },
]

export const qualityRows = [
  {
    code: 'EQ-2025-0118',
    name: '压力试验机 YAW-2000',
    category: '检测设备',
    department: '建材检测室',
    status: '在用',
    plan: '期间核查',
    dueDate: '2025-12-20',
  },
  {
    code: 'RM-2025-0042',
    name: '水泥标准样',
    category: '标准物质',
    department: '质量部',
    status: '有效',
    plan: '到期复核',
    dueDate: '2026-01-10',
  },
  {
    code: 'SP-2025-0016',
    name: '万能材料试验机供应商',
    category: '供应商评价',
    department: '设备管理',
    status: '待评价',
    plan: '年度评价',
    dueDate: '2025-12-31',
  },
  {
    code: 'QMS-VH-2026-0701',
    name: '虚拟核查项目 - 内部审核整改记录',
    category: '质量体系整改',
    department: '质量管理部',
    status: '待验证',
    plan: '核查整改闭环及验证记录',
    dueDate: '2026-07-16',
  },
  {
    code: 'DOC-VH-2026-0702',
    name: '虚拟核查项目 - 报告模板受控文件',
    category: '文件控制',
    department: '质量管理部',
    status: '待评审',
    plan: '核对封面首页字段与版本状态',
    dueDate: '2026-07-12',
  },
  {
    code: 'EQ-VH-2026-0703',
    name: '虚拟核查项目 - 导热系数测定仪',
    category: '检测设备',
    department: '综合业务部',
    status: '核查中',
    plan: '期间核查与校准证书复核',
    dueDate: '2026-07-18',
  },
]

export const systemRows = [
  {
    key: '审批流引擎',
    scope: '报告更改/合同更改/价格调整',
    value: '启用多级审批',
    owner: '系统管理员',
    updatedAt: '2025-12-08',
  },
  {
    key: '检测项目流程',
    scope: '委托-样品-检测-报告',
    value: '按项目分类配置',
    owner: '质量部',
    updatedAt: '2025-12-07',
  },
  {
    key: '日志保留策略',
    scope: '登录/审批/接口/报告',
    value: '保留 5 年',
    owner: '信息管理员',
    updatedAt: '2025-12-01',
  },
]

export const pageProfiles = {
  entrust: {
    title: '委托受理工作台',
    primaryAction: '新增委托',
    secondaryActions: ['合同评审', '重新推送外部ERP', '导出'],
    leftTitle: '业务来源',
    categories: [
      ['网上委托', '24'],
      ['现场委托', '18'],
      ['监督抽检', '9'],
      ['见证取样', '16'],
      ['合同变更', '5'],
    ],
    sideTitle: '委托要点',
    sideFields: [
      ['外部ERP合同编号', 'KD-2025-1188'],
      ['外部ERP项目类型', '见证取样'],
      ['计价状态', '已计价'],
      ['资料完整性', '缺检测协议附件'],
    ],
  },
  sample: {
    title: '样品流转工作台',
    primaryAction: '样品入库',
    secondaryActions: ['批量出库', '留样处置', '导出'],
    leftTitle: '样品分类',
    categories: [
      ['混凝土类', '18'],
      ['钢筋及连接', '12'],
      ['防水材料', '7'],
      ['门窗幕墙', '5'],
      ['地基基础', '9'],
    ],
    sideTitle: '流转要点',
    sideFields: [
      ['入库位置', 'B-03-12'],
      ['留样期限', '30 天'],
      ['出库用途', '检测领样'],
      ['处置状态', '未处置'],
    ],
  },
  testing: {
    title: '检测任务工作台',
    primaryAction: '分配任务',
    secondaryActions: ['自动采集查询', '数据校核', '导出'],
    leftTitle: '检测科室',
    categories: [
      ['建材检测室', '28'],
      ['结构检测室', '11'],
      ['节能检测室', '8'],
      ['环境检测室', '6'],
      ['现场外检组', '14'],
    ],
    sideTitle: '检测要点',
    sideFields: [
      ['执行标准', 'GB/T 50081-2019'],
      ['自动采集', '已同步 6 条'],
      ['异常原因', '未见异常'],
      ['原始记录', '待主检确认'],
    ],
  },
  finance: {
    title: '财务结算工作台',
    primaryAction: '登记收款',
    secondaryActions: ['确认收款', '开具发票', '导出'],
    leftTitle: '财务状态',
    categories: [
      ['待计价', '13'],
      ['待收款', '22'],
      ['待确认', '7'],
      ['待开票', '16'],
      ['退款处理', '3'],
    ],
    sideTitle: '财务要点',
    sideFields: [
      ['应收金额', '¥18,600'],
      ['实收金额', '¥10,000'],
      ['发票状态', '未开票'],
      ['外部ERP同步', '已推送'],
    ],
  },
  quality: {
    title: '质量体系台账',
    primaryAction: '新增台账',
    secondaryActions: ['期间核查', '检定计划', '导出'],
    leftTitle: '质量资源',
    categories: [
      ['设备台账', '86'],
      ['供应商评价', '14'],
      ['标准物质', '31'],
      ['易耗品', '126'],
      ['检测标准库', '248'],
    ],
    sideTitle: '质量要点',
    sideFields: [
      ['设备状态', '在用'],
      ['本月检定', '12 台'],
      ['期间核查', '3 项待完成'],
      ['科室视图', '按数据范围'],
    ],
  },
  system: {
    title: '系统配置工作台',
    primaryAction: '新增配置',
    secondaryActions: ['发布流程', '同步权限', '导出'],
    leftTitle: '配置域',
    categories: [
      ['审批设置', '8'],
      ['运行参数', '32'],
      ['项目流程', '46'],
      ['接口配置', '5'],
      ['用户与日志', '128'],
    ],
    sideTitle: '配置要点',
    sideFields: [
      ['审批模式', '多级审批'],
      ['权限策略', '按角色授权'],
      ['接口状态', '外部ERP/短信启用'],
      ['日志审计', '全量留痕'],
    ],
  },
  default: {
    title: '业务工作台',
    primaryAction: '新增',
    secondaryActions: ['批量完成', '附件', '导出'],
    leftTitle: '项目分类',
    categories: [
      ['混凝土类', '18'],
      ['钢筋及连接', '12'],
      ['防水材料', '7'],
      ['门窗幕墙', '5'],
      ['地基基础', '9'],
    ],
    sideTitle: '选中记录',
    sideFields: [
      ['样品编号', 'HN-S-202512-001'],
      ['报告编号', 'BG-202512-0148'],
      ['委托单位', '示例建设集团'],
      ['当前页面', '业务办理'],
    ],
  },
} as const

export const reportRows = [
  { name: '检测批次同环比', period: '2025 年 12 月', department: '建材检测室', scope: '委托检测', value: '126', trend: '同比 +8.5%' },
  { name: '检测项目产值汇总', period: '2025 年 12 月', department: '结构检测室', scope: '监督抽检', value: '¥428,600', trend: '环比 +4.1%' },
  { name: '报告超期查询', period: '近 30 天', department: '报告中心', scope: '全部', value: '18', trend: '需跟进' },
  { name: '员工工作量统计', period: '本月', department: '全部科室', scope: '检测数量', value: '612', trend: '已生成' },
]

export const reportWorkRows = [
  {
    reportNo: 'BG-202512-0148',
    sampleNo: 'HN-S-202512-001',
    project: '混凝土抗压',
    client: '示例建设集团',
    template: 'REPORT_CONCRETE_PRESS',
    version: 'V3.2',
    status: '待审核',
    sign: '主检已签',
    deadline: '超期 2 天',
    department: '建材检测室',
    owner: '李主检',
  },
  {
    reportNo: 'BG-202512-0152',
    sampleNo: 'HN-S-202512-002',
    project: '钢筋拉伸',
    client: '示例华东客户',
    template: 'REPORT_STEEL_TENSILE',
    version: 'V2.8',
    status: '待批准',
    sign: '审核已签',
    deadline: '正常',
    department: '结构检测室',
    owner: '王主检',
  },
  {
    reportNo: 'BG-202512-0155',
    sampleNo: 'HN-S-202512-003',
    project: '防水卷材',
    client: '城投开发',
    template: 'REPORT_WATERPROOF',
    version: 'V1.9',
    status: '待打印',
    sign: '批准已签',
    deadline: '加急',
    department: '建材检测室',
    owner: '赵主检',
  },
  {
    reportNo: 'BG-202512-0158',
    sampleNo: 'HN-S-202512-006',
    project: '水泥胶砂强度',
    client: '示例建设集团',
    template: 'REPORT_CEMENT_MORTAR',
    version: 'V1.2',
    status: '待审核',
    sign: '主检已签',
    deadline: '正常',
    department: '建材检测室',
    owner: '李主检',
  },
  {
    reportNo: 'BG-202512-0160',
    sampleNo: 'HN-S-202512-008',
    project: '钢绞线拉伸',
    client: '示例华东客户',
    template: 'REPORT_STRAND_TENSILE',
    version: 'V1.0',
    status: '待审核',
    sign: '主检已签',
    deadline: '即将到期',
    department: '结构检测室',
    owner: '王主检',
  },
  {
    reportNo: 'BG-202512-0161',
    sampleNo: 'HN-S-202512-009',
    project: '保温板导热系数',
    client: '城投开发',
    template: 'REPORT_THERMAL',
    version: 'V2.1',
    status: '待发放',
    sign: '批准已签',
    deadline: '正常',
    department: '建材检测室',
    owner: '赵主检',
  },
]

export interface ReportWorkDetail {
  projectName: string
  summary: { title: string; fields: [string, string][] }[]
  checks: { group: string; status: string; type: 'success' | 'warning' | 'danger'; items: [string, string][] }[]
  attachments: { name: string; type: string; source: string; status: string }[]
}

export const reportWorkDetails: Record<string, ReportWorkDetail> = {
  'BG-202512-0148': {
    projectName: '星河湾三期',
    summary: [
      {
        title: '委托信息',
        fields: [
          ['委托编号', 'WT-202512-0031'],
          ['委托单位', '示例建设集团'],
          ['工程名称', '星河湾三期'],
          ['盖章要求', 'CMA + CNAS'],
        ],
      },
      {
        title: '样品信息',
        fields: [
          ['样品编号', 'HN-S-202512-001'],
          ['样品名称', '混凝土试块'],
          ['规格型号', 'C30 / 3 组'],
          ['流转状态', '检测完成，留样待处置'],
        ],
      },
      {
        title: '实验信息',
        fields: [
          ['检测项目', '混凝土抗压'],
          ['检测日期', '2025-12-04'],
          ['主检人', '李主检'],
          ['执行标准', 'GB/T 50081-2019'],
        ],
      },
      {
        title: '原始记录',
        fields: [
          ['记录编号', 'YJ-202512-0148'],
          ['记录条数', '8 条已确认'],
          ['采集方式', '压力机自动采集'],
          ['校核状态', '校核通过'],
        ],
      },
    ],
    checks: [
      {
        group: '标准与一单一库校验',
        status: '通过',
        type: 'success',
        items: [
          ['检测标准', 'GB/T 50081-2019，标准库已收录'],
          ['能力范围', '混凝土抗压在资质能力范围内'],
          ['一单一库', '委托单、样品、报告项目一致'],
        ],
      },
      {
        group: '仪器有效性校验',
        status: '通过',
        type: 'success',
        items: [
          ['仪器名称', '压力试验机 YAW-2000'],
          ['受控状态', '在受控仪器清单内'],
          ['有效期', '2025-01-01 至 2026-01-01，检测日期有效'],
        ],
      },
      {
        group: '盖章范围校验',
        status: '需关注',
        type: 'warning',
        items: [
          ['委托要求', 'CMA + CNAS'],
          ['CMA', '项目在 CMA 范围内'],
          ['CNAS', '需审核人确认报告结论页标识'],
        ],
      },
    ],
    attachments: [
      { name: '系统生成封面.pdf', type: 'PDF', source: '模板生成', status: '已生成' },
      { name: '混凝土抗压报告正文.docx', type: 'Word', source: '检测人员上传', status: '已转 PDF' },
      { name: '原始记录扫描件.pdf', type: 'PDF', source: '附件上传', status: '已合并' },
    ],
  },
  'BG-202512-0152': {
    projectName: '云岭学校扩建',
    summary: [
      {
        title: '委托信息',
        fields: [
          ['委托编号', 'WT-202512-0032'],
          ['委托单位', '示例华东客户'],
          ['工程名称', '云岭学校扩建'],
          ['盖章要求', 'CMA'],
        ],
      },
      {
        title: '样品信息',
        fields: [
          ['样品编号', 'HN-S-202512-002'],
          ['样品名称', '钢筋试件'],
          ['规格型号', 'HRB400 Φ20 / 6 根'],
          ['流转状态', '检测完成，检毕样品待处理'],
        ],
      },
      {
        title: '实验信息',
        fields: [
          ['检测项目', '钢筋拉伸'],
          ['检测日期', '2025-12-05'],
          ['主检人', '王主检'],
          ['执行标准', 'GB/T 228.1-2021'],
        ],
      },
      {
        title: '原始记录',
        fields: [
          ['记录编号', 'YJ-202512-0152'],
          ['记录条数', '12 条已确认'],
          ['采集方式', '万能试验机自动采集'],
          ['校核状态', '校核通过'],
        ],
      },
    ],
    checks: [
      {
        group: '标准与一单一库校验',
        status: '通过',
        type: 'success',
        items: [
          ['检测标准', 'GB/T 228.1-2021，标准库已收录'],
          ['能力范围', '钢筋拉伸在资质能力范围内'],
          ['一单一库', '委托单、样品、报告项目一致'],
        ],
      },
      {
        group: '仪器有效性校验',
        status: '通过',
        type: 'success',
        items: [
          ['仪器名称', '万能试验机 WAW-1000'],
          ['受控状态', '在受控仪器清单内'],
          ['有效期', '2025-03-15 至 2026-03-15，检测日期有效'],
        ],
      },
      {
        group: '盖章范围校验',
        status: '通过',
        type: 'success',
        items: [
          ['委托要求', 'CMA'],
          ['CMA', '项目在 CMA 范围内'],
          ['CNAS', '委托未要求，无需标识'],
        ],
      },
    ],
    attachments: [
      { name: '系统生成封面.pdf', type: 'PDF', source: '模板生成', status: '已生成' },
      { name: '钢筋拉伸报告正文.docx', type: 'Word', source: '检测人员上传', status: '已转 PDF' },
    ],
  },
  'BG-202512-0155': {
    projectName: '滨江商务区 B 地块',
    summary: [
      {
        title: '委托信息',
        fields: [
          ['委托编号', 'WT-202512-0035'],
          ['委托单位', '城投开发'],
          ['工程名称', '滨江商务区 B 地块'],
          ['盖章要求', 'CMA + CNAS'],
        ],
      },
      {
        title: '样品信息',
        fields: [
          ['样品编号', 'HN-S-202512-003'],
          ['样品名称', 'SBS 改性沥青防水卷材'],
          ['规格型号', '4mm / 2 卷'],
          ['流转状态', '检测完成，留样保存'],
        ],
      },
      {
        title: '实验信息',
        fields: [
          ['检测项目', '防水卷材'],
          ['检测日期', '2025-12-06'],
          ['主检人', '赵主检'],
          ['执行标准', 'GB 18242-2008'],
        ],
      },
      {
        title: '原始记录',
        fields: [
          ['记录编号', 'YJ-202512-0155'],
          ['记录条数', '6 条已确认'],
          ['采集方式', '人工录入'],
          ['校核状态', '校核通过'],
        ],
      },
    ],
    checks: [
      {
        group: '标准与一单一库校验',
        status: '需关注',
        type: 'warning',
        items: [
          ['检测标准', 'GB 18242-2008，标准库已收录'],
          ['版本提示', '该标准存在替代版本，需确认委托约定版本'],
          ['一单一库', '委托单、样品、报告项目一致'],
        ],
      },
      {
        group: '仪器有效性校验',
        status: '不通过',
        type: 'danger',
        items: [
          ['仪器名称', '电子拉力机 XL-250'],
          ['受控状态', '在受控仪器清单内'],
          ['有效期', '检定有效期至 2025-11-30，检测日期 2025-12-06 已超期'],
        ],
      },
      {
        group: '盖章范围校验',
        status: '需关注',
        type: 'warning',
        items: [
          ['委托要求', 'CMA + CNAS'],
          ['CMA', '项目在 CMA 范围内'],
          ['CNAS', '防水卷材不在 CNAS 认可范围，需与委托方确认'],
        ],
      },
    ],
    attachments: [
      { name: '系统生成封面.pdf', type: 'PDF', source: '模板生成', status: '已生成' },
      { name: '防水卷材报告正文.docx', type: 'Word', source: '检测人员上传', status: '待上传' },
    ],
  },
  'BG-202512-0158': {
    projectName: '星河湾三期二标段',
    summary: [
      {
        title: '委托信息',
        fields: [
          ['委托编号', 'WT-202512-0036'],
          ['委托单位', '示例建设集团'],
          ['工程名称', '星河湾三期二标段'],
          ['盖章要求', 'CMA'],
        ],
      },
      {
        title: '样品信息',
        fields: [
          ['样品编号', 'HN-S-202512-006'],
          ['样品名称', '水泥胶砂试件'],
          ['规格型号', 'P·O 42.5 / 3 组'],
          ['流转状态', '检测完成，留样保存'],
        ],
      },
      {
        title: '实验信息',
        fields: [
          ['检测项目', '水泥胶砂强度'],
          ['检测日期', '2025-12-07'],
          ['主检人', '李主检'],
          ['执行标准', 'GB/T 17671-2021'],
        ],
      },
      {
        title: '原始记录',
        fields: [
          ['记录编号', 'YJ-202512-0158'],
          ['记录条数', '6 条已确认'],
          ['采集方式', '抗折抗压一体机自动采集'],
          ['校核状态', '待校核'],
        ],
      },
    ],
    checks: [
      {
        group: '标准与一单一库校验',
        status: '通过',
        type: 'success',
        items: [
          ['检测标准', 'GB/T 17671-2021，标准库已收录'],
          ['能力范围', '水泥胶砂强度在资质能力范围内'],
          ['一单一库', '委托单、样品、报告项目一致'],
        ],
      },
      {
        group: '仪器有效性校验',
        status: '通过',
        type: 'success',
        items: [
          ['仪器名称', '抗折抗压一体机 KZY-300'],
          ['受控状态', '在受控仪器清单内'],
          ['有效期', '2025-06-20 至 2026-06-20，检测日期有效'],
        ],
      },
      {
        group: '盖章范围校验',
        status: '通过',
        type: 'success',
        items: [
          ['委托要求', 'CMA'],
          ['CMA', '项目在 CMA 范围内'],
          ['CNAS', '委托未要求，无需标识'],
        ],
      },
    ],
    attachments: [
      { name: '系统生成封面.pdf', type: 'PDF', source: '模板生成', status: '已生成' },
      { name: '水泥胶砂强度报告正文.docx', type: 'Word', source: '检测人员上传', status: '已转 PDF' },
    ],
  },
  'BG-202512-0160': {
    projectName: '云岭学校扩建',
    summary: [
      {
        title: '委托信息',
        fields: [
          ['委托编号', 'WT-202512-0038'],
          ['委托单位', '示例华东客户'],
          ['工程名称', '云岭学校扩建'],
          ['盖章要求', 'CMA + CNAS'],
        ],
      },
      {
        title: '样品信息',
        fields: [
          ['样品编号', 'HN-S-202512-008'],
          ['样品名称', '预应力钢绞线'],
          ['规格型号', '1×7 Φ15.2 / 3 根'],
          ['流转状态', '检测完成，检毕样品待处理'],
        ],
      },
      {
        title: '实验信息',
        fields: [
          ['检测项目', '钢绞线拉伸'],
          ['检测日期', '2025-12-08'],
          ['主检人', '王主检'],
          ['执行标准', 'GB/T 5224-2023'],
        ],
      },
      {
        title: '原始记录',
        fields: [
          ['记录编号', 'YJ-202512-0160'],
          ['记录条数', '9 条已确认'],
          ['采集方式', '万能试验机自动采集'],
          ['校核状态', '校核通过'],
        ],
      },
    ],
    checks: [
      {
        group: '标准与一单一库校验',
        status: '通过',
        type: 'success',
        items: [
          ['检测标准', 'GB/T 5224-2023，标准库已收录'],
          ['能力范围', '钢绞线拉伸在资质能力范围内'],
          ['一单一库', '委托单、样品、报告项目一致'],
        ],
      },
      {
        group: '仪器有效性校验',
        status: '需关注',
        type: 'warning',
        items: [
          ['仪器名称', '万能试验机 WAW-1000'],
          ['受控状态', '在受控仪器清单内'],
          ['有效期', '校准证书 2025-12-20 到期，建议尽快安排复校'],
        ],
      },
      {
        group: '盖章范围校验',
        status: '通过',
        type: 'success',
        items: [
          ['委托要求', 'CMA + CNAS'],
          ['CMA', '项目在 CMA 范围内'],
          ['CNAS', '项目在 CNAS 认可范围内'],
        ],
      },
    ],
    attachments: [
      { name: '系统生成封面.pdf', type: 'PDF', source: '模板生成', status: '已生成' },
      { name: '钢绞线拉伸报告正文.docx', type: 'Word', source: '检测人员上传', status: '已转 PDF' },
    ],
  },
  'BG-202512-0161': {
    projectName: '滨江商务区 B 地块',
    summary: [
      {
        title: '委托信息',
        fields: [
          ['委托编号', 'WT-202512-0039'],
          ['委托单位', '城投开发'],
          ['工程名称', '滨江商务区 B 地块'],
          ['盖章要求', 'CMA'],
        ],
      },
      {
        title: '样品信息',
        fields: [
          ['样品编号', 'HN-S-202512-009'],
          ['样品名称', '挤塑聚苯保温板'],
          ['规格型号', 'XPS 50mm / 3 块'],
          ['流转状态', '检测完成，留样保存'],
        ],
      },
      {
        title: '实验信息',
        fields: [
          ['检测项目', '保温板导热系数'],
          ['检测日期', '2025-12-03'],
          ['主检人', '赵主检'],
          ['执行标准', 'GB/T 10294-2008'],
        ],
      },
      {
        title: '原始记录',
        fields: [
          ['记录编号', 'YJ-202512-0161'],
          ['记录条数', '4 条已确认'],
          ['采集方式', '导热系数测定仪自动采集'],
          ['校核状态', '校核通过'],
        ],
      },
    ],
    checks: [
      {
        group: '标准与一单一库校验',
        status: '通过',
        type: 'success',
        items: [
          ['检测标准', 'GB/T 10294-2008，标准库已收录'],
          ['能力范围', '导热系数在资质能力范围内'],
          ['一单一库', '委托单、样品、报告项目一致'],
        ],
      },
      {
        group: '仪器有效性校验',
        status: '通过',
        type: 'success',
        items: [
          ['仪器名称', '导热系数测定仪 DRX-300'],
          ['受控状态', '在受控仪器清单内'],
          ['有效期', '2025-04-10 至 2026-04-10，检测日期有效'],
        ],
      },
      {
        group: '盖章范围校验',
        status: '通过',
        type: 'success',
        items: [
          ['委托要求', 'CMA'],
          ['CMA', '项目在 CMA 范围内'],
          ['CNAS', '委托未要求，无需标识'],
        ],
      },
    ],
    attachments: [
      { name: '系统生成封面.pdf', type: 'PDF', source: '模板生成', status: '已生成' },
      { name: '保温板导热系数报告正文.docx', type: 'Word', source: '检测人员上传', status: '已转 PDF' },
      { name: '批准签字页.pdf', type: 'PDF', source: '电子签名', status: '已合并' },
    ],
  },
}

export const reportNodeActions: Record<string, { editableScope: string; returnTargets: string[] }> = {
  review: {
    editableScope: '审核环节只能查看报告和填写审核意见，不允许修改报告正文、检测数据或附件。',
    returnTargets: ['委托更改', '检测数据更改', '委托和检测数据都更改'],
  },
  approval: {
    editableScope: '批准环节只允许预览、下载、批准或退回，不允许直接修改。',
    returnTargets: ['委托更改', '检测数据更改', '委托和检测数据都更改'],
  },
  print: {
    editableScope: '打印环节不可修改报告内容，只能套打正式版 PDF。',
    returnTargets: ['报告批准'],
  },
  default: {
    editableScope: '当前节点只读，修改需走报告更改申请流程。',
    returnTargets: ['报告更改申请'],
  },
}

export const reportTimeline = [
  ['数据提交', '检测数据已确认，原始记录 8 条'],
  ['报告生成', '按 Word 模板 REPORT_CONCRETE_PRESS 生成'],
  ['报告审核', '检查结论、依据标准、电子签名'],
  ['报告批准', '批准人签名后锁定正式版'],
  ['报告签发', '电子签署与签章确认后签发'],
  ['报告归档', '签发完成后直接归档'],
]

export const approvalTypes = [
  '报告更改',
  '合同更改',
  '价格调整',
  '任务取消',
  '日常事务',
  '设备采购',
  '收款登记',
  '账号退款',
]

export const approvalRows = [
  {
    no: 'AP-202512-001',
    type: '报告更改',
    target: 'BG-202512-0148',
    department: '报告中心',
    person: '张工',
    status: '审批中',
    node: '部门负责人',
    date: '2025-12-08',
    reason: '委托单位名称需按合同主体更正',
  },
  {
    no: 'AP-202512-002',
    type: '收款登记',
    target: 'SK-202512-0086',
    department: '财务部',
    person: '刘会计',
    status: '待审批',
    node: '财务负责人',
    date: '2025-12-08',
    reason: '客户线下转账已到账，需确认收款',
  },
  {
    no: 'AP-202512-003',
    type: '设备采购',
    target: 'CG-202512-0019',
    department: '质量部',
    person: '赵工',
    status: '已通过',
    node: '完成',
    date: '2025-12-07',
    reason: '期间核查设备需补充采购',
  },
]

export const capabilityFields = {
  integration: [
    ['外部ERP接口是否打开', '是'],
    ['外部ERP接口地址', 'https://erp.example/api'],
    ['client_id', 'kd_demo_client'],
    ['推送间隔', '10 分钟'],
  ],
  template: [
    ['报告模板标识', 'REPORT_DEFAULT'],
    ['报告展现方式', 'Word 模板'],
    ['是否打印电子签名', '是'],
    ['同份报告最大组数', '4'],
  ],
  collection: [
    ['自动采集字段是否可编辑', '按项目控制'],
    ['采集状态', '已同步'],
    ['异常原因字典', '自动采集异常原因'],
    ['查询入口', '记录查询 / 自动采集数据查询'],
  ],
  notification: [
    ['短信接口是否打开', '是'],
    ['短信签名', 'LIMS 实验室'],
    ['变量替换', '委托单位、报告编号、取报告地址'],
    ['邮件发送', '启用 SMTP'],
  ],
  auth: [
    ['账号密码登录', '启用'],
    ['加密狗登录', '启用'],
    ['指纹登录', '启用'],
    ['电子签名绑定', '按用户绑定'],
  ],
} as const

export const capabilityLogs = {
  integration: [
    { time: '2025-12-08 10:20', object: 'WT-202512-0031', action: '推送外部ERP合同', result: '成功', operator: '系统' },
    { time: '2025-12-08 09:42', object: 'BG-202512-0148', action: '推送项目类型', result: '成功', operator: '报告中心' },
    { time: '2025-12-07 17:18', object: 'WT-202512-0033', action: '重新推送外部ERP', result: '失败：缺合同编号', operator: '市场受理' },
  ],
  template: [
    { time: '2025-12-08 10:03', object: 'REPORT_CONCRETE_PRESS', action: '发布模板 V3.2', result: '已启用', operator: '系统管理员' },
    { time: '2025-12-07 15:22', object: 'REPORT_STEEL_TENSILE', action: '配置电子签名区域', result: '已保存', operator: '报告中心' },
    { time: '2025-12-07 11:09', object: 'REPORT_DEFAULT', action: '套打偏移校准', result: '已保存', operator: '打印室' },
  ],
  collection: [
    { time: '2025-12-08 10:11', object: '压力试验机 YAW-2000', action: '采集数据 6 条', result: '成功', operator: '自动采集服务' },
    { time: '2025-12-08 09:54', object: '拉力试验机', action: '采集数据', result: '失败：设备离线', operator: '自动采集服务' },
    { time: '2025-12-07 16:40', object: '万能材料试验机', action: '采集字段映射', result: '已更新', operator: '质量部' },
  ],
  notification: [
    { time: '2025-12-08 10:35', object: 'BG-202512-0148', action: '发送取报告短信', result: '成功', operator: '报告中心' },
    { time: '2025-12-08 09:16', object: 'WT-202512-0033', action: '资料退回邮件', result: '成功', operator: '市场受理' },
    { time: '2025-12-07 18:05', object: 'AP-202512-002', action: '审批待办提醒', result: '成功', operator: '系统' },
  ],
  auth: [
    { time: '2025-12-08 10:05', object: '张工', action: '绑定电子签名', result: '成功', operator: '管理员' },
    { time: '2025-12-08 09:30', object: '李主检', action: '采集指纹信息', result: '成功', operator: '管理员' },
    { time: '2025-12-07 14:21', object: '周审核', action: '绑定加密狗', result: '成功', operator: '管理员' },
  ],
} as const

export const templateRows = [
  { code: 'REPORT_CONCRETE_PRESS', name: '混凝土抗压报告', version: 'V3.2', sign: '主检/审核/批准', print: '套打', status: '启用' },
  { code: 'REPORT_STEEL_TENSILE', name: '钢筋拉伸报告', version: 'V2.8', sign: '主检/审核/批准', print: '导出 Word', status: '启用' },
  { code: 'REPORT_WATERPROOF', name: '防水卷材报告', version: 'V1.9', sign: '主检/批准', print: '套打', status: '试用' },
]

export const notificationVariables = [
  ['{client}', '委托单位'],
  ['{reportNo}', '报告编号'],
  ['{sampleNo}', '样品编号'],
  ['{deadline}', '承诺完成时间'],
  ['{pickupAddress}', '取报告地址'],
]

export const authRows = [
  { name: '张工', department: '报告中心', password: '启用', dongle: '未绑定', fingerprint: '已采集', sign: '已绑定' },
  { name: '李主检', department: '建材检测室', password: '启用', dongle: '已绑定', fingerprint: '已采集', sign: '已绑定' },
  { name: '周审核', department: '结构检测室', password: '启用', dongle: '已绑定', fingerprint: '未采集', sign: '已绑定' },
]
