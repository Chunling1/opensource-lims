import type { TableColumn } from '../../types/common/table'

// Operator columns show the latest successful real action; assignments are not completion evidence.
export const reportQueryColumns: TableColumn[] = [
  {
    "key": "code",
    "label": "样品编号",
    "group": "报告概况",
    "required": true
  },
  {
    "key": "reportCode",
    "label": "报告编号",
    "group": "报告概况"
  },
  {
    "key": "customer",
    "label": "委托单位",
    "group": "报告概况",
    "wrap": true
  },
  {
    "key": "name",
    "label": "检测项目",
    "group": "报告概况",
    "wrap": true
  },
  {
    "key": "dataStatus",
    "label": "数据状态",
    "group": "报告概况"
  },
  {
    "key": "sampleStatus",
    "label": "样品状态",
    "group": "报告概况"
  },
  {
    "key": "version",
    "label": "报告版本",
    "group": "报告概况"
  },
  {
    "key": "deadline",
    "label": "时限",
    "group": "报告概况"
  },
  {
    "key": "reportFormat",
    "label": "报告类型",
    "group": "报告概况"
  },
  {
    "key": "reportCategory",
    "label": "报告类别",
    "group": "报告概况"
  },
  {
    "key": "sealRequirement",
    "label": "盖章要求",
    "group": "报告概况"
  },
  {
    "key": "entrustNo",
    "label": "委托编号",
    "group": "委托信息"
  },
  {
    "key": "erpProjectNo",
    "label": "外部ERP项目编号",
    "group": "委托信息"
  },
  {
    "key": "erpContractNo",
    "label": "外部ERP合同编号",
    "group": "委托信息"
  },
  {
    "key": "entrustDate",
    "label": "委托日期",
    "group": "委托信息"
  },
  {
    "key": "handler",
    "label": "委托经办人",
    "group": "委托信息"
  },
  {
    "key": "handlerDepartment",
    "label": "经办部门",
    "group": "委托信息"
  },
  {
    "key": "consignor",
    "label": "委托联系人",
    "group": "委托信息"
  },
  {
    "key": "consignorPhone",
    "label": "联系人电话",
    "group": "委托信息"
  },
  {
    "key": "clientAddress",
    "label": "委托单位地址",
    "group": "委托信息",
    "wrap": true
  },
  {
    "key": "paymentMethod",
    "label": "登记支付方式",
    "group": "委托信息"
  },
  {
    "key": "sampleOrProjectName",
    "label": "样品／工程名称",
    "group": "样品信息",
    "wrap": true
  },
  {
    "key": "specification",
    "label": "规格型号",
    "group": "样品信息"
  },
  {
    "key": "manufacturer",
    "label": "生产单位",
    "group": "样品信息"
  },
  {
    "key": "sampleQuantity",
    "label": "样品数量",
    "group": "样品信息"
  },
  {
    "key": "productCode",
    "label": "出厂编号",
    "group": "样品信息"
  },
  {
    "key": "productionDate",
    "label": "生产日期",
    "group": "样品信息"
  },
  {
    "key": "sendDate",
    "label": "送样日期",
    "group": "样品信息"
  },
  {
    "key": "sampleAppearance",
    "label": "样品外观",
    "group": "样品信息"
  },
  {
    "key": "samplingUnit",
    "label": "抽样单位",
    "group": "样品信息"
  },
  {
    "key": "sampler",
    "label": "抽样人",
    "group": "样品信息"
  },
  {
    "key": "samplingTime",
    "label": "抽样日期",
    "group": "样品信息"
  },
  {
    "key": "samplingLocation",
    "label": "抽样地点",
    "group": "样品信息"
  },
  {
    "key": "sampleInboundDate",
    "label": "入库日期",
    "group": "出入库"
  },
  {
    "key": "sampleOutboundDate",
    "label": "出库日期",
    "group": "出入库"
  },
  {
    "key": "sampleReceiver",
    "label": "领样人",
    "group": "出入库"
  },
  {
    "key": "samplePickupDate",
    "label": "领取日期",
    "group": "出入库"
  },
  {
    "key": "testDepartment",
    "label": "检测部门",
    "group": "检测信息"
  },
  {
    "key": "schemeDisplay",
    "label": "检测方案",
    "group": "检测信息"
  },
  {
    "key": "testingLocation",
    "label": "检测地点",
    "group": "检测信息"
  },
  {
    "key": "testBasis",
    "label": "检测依据",
    "group": "检测信息",
    "wrap": true
  },
  {
    "key": "assessmentStandard",
    "label": "判定依据",
    "group": "检测信息",
    "wrap": true
  },
  {
    "key": "testStartDate",
    "label": "检测开始日期",
    "group": "检测信息"
  },
  {
    "key": "testEndDate",
    "label": "检测结束日期",
    "group": "检测信息"
  },
  {
    "key": "testResult",
    "label": "检测结果",
    "group": "检测信息",
    "wrap": true
  },
  {
    "key": "commissionCreatedBy",
    "label": "委托登记人",
    "group": "流程操作人"
  },
  {
    "key": "commissionCreatedAt",
    "label": "委托登记操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "commissionCompletedBy",
    "label": "委托完成人",
    "group": "流程操作人"
  },
  {
    "key": "commissionCompletedAt",
    "label": "委托完成操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "sampleRegisteredBy",
    "label": "样品登记完成人",
    "group": "流程操作人"
  },
  {
    "key": "sampleRegisteredAt",
    "label": "样品登记完成操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "contractReviewedBy",
    "label": "合同评审通过人",
    "group": "流程操作人"
  },
  {
    "key": "contractReviewedAt",
    "label": "合同评审通过操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "sampleInboundBy",
    "label": "入库人",
    "group": "流程操作人"
  },
  {
    "key": "sampleInboundAt",
    "label": "入库操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "sampleOutboundBy",
    "label": "出库领取人",
    "group": "流程操作人"
  },
  {
    "key": "sampleOutboundAt",
    "label": "出库领取操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "sampleReturnedBy",
    "label": "回库人",
    "group": "流程操作人"
  },
  {
    "key": "sampleReturnedAt",
    "label": "回库操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "dataSavedBy",
    "label": "检测数据保存人",
    "group": "流程操作人"
  },
  {
    "key": "dataSavedAt",
    "label": "检测数据保存操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "dataCompletedBy",
    "label": "检测录入完成人",
    "group": "流程操作人"
  },
  {
    "key": "dataCompletedAt",
    "label": "检测录入完成操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "reportCheckedBy",
    "label": "报告校核通过人",
    "group": "流程操作人"
  },
  {
    "key": "reportCheckedAt",
    "label": "报告校核通过操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "reportReviewedBy",
    "label": "报告审核通过人",
    "group": "流程操作人"
  },
  {
    "key": "reportReviewedAt",
    "label": "报告审核通过操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "reportApprovedBy",
    "label": "报告批准通过人",
    "group": "流程操作人"
  },
  {
    "key": "reportApprovedAt",
    "label": "报告批准通过操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "sealConfirmedBy",
    "label": "签章确认人",
    "group": "流程操作人"
  },
  {
    "key": "sealConfirmedAt",
    "label": "签章确认操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "reportIssuedBy",
    "label": "签发完成人",
    "group": "流程操作人"
  },
  {
    "key": "reportIssuedAt",
    "label": "签发完成操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "reportReleasedBy",
    "label": "历史报告发放人",
    "group": "流程操作人"
  },
  {
    "key": "reportReleasedAt",
    "label": "历史报告发放操作时间",
    "group": "流程操作时间"
  },
  {
    "key": "reportArchivedBy",
    "label": "报告归档人",
    "group": "流程操作人"
  },
  {
    "key": "reportArchivedAt",
    "label": "报告归档操作时间",
    "group": "流程操作时间"
  },
  { key: 'checkDate', label: '校核日期', group: '业务日期' },
  { key: 'auditDate', label: '审核日期', group: '业务日期' },
  { key: 'approvalDate', label: '批准日期', group: '业务日期' },
  { key: 'printDate', label: '签发日期', group: '业务日期' },
  { key: 'archiveDate', label: '归档日期', group: '业务日期' },
  { key: 'distributionDate', label: '发放日期', group: '业务日期' },
]
