// The import template contains basic information only; histories and files use their own forms.
export const equipmentImportFields = [
  { key: 'code', label: '档案号' }, { key: 'name', label: '仪器设备名称' },
  { key: 'model', label: '规格型号' }, { key: 'accuracy', label: '准确度' }, { key: 'range', label: '量程' },
  { key: 'equipmentType', label: '设备类型' }, { key: 'status', label: '设备状态' },
  { key: 'purchasedAt', label: '购入日期' }, { key: 'price', label: '购入价格' }, { key: 'keeper', label: '仪器保管人' },
  { key: 'manufacturer', label: '生产厂家' }, { key: 'serial', label: '仪器出厂号' }, { key: 'location', label: '放置单位' },
  { key: 'testOrganization', label: '检定/测试单位' }, { key: 'tester', label: '检定人' }, { key: 'cycle', label: '周期' },
  { key: 'validity', label: '有效期' }, { key: 'lastTestDate', label: '最近检定/测试日期' },
  { key: 'plannedTestDate', label: '计划检定/测试日期' }, { key: 'actualTestDate', label: '实际检定/测试日期' },
  { key: 'department', label: '所属部门' }, { key: 'notes', label: '备注' },
] as const
