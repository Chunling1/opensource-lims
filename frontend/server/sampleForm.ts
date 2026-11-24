import { parseReportSettings } from './sampleReportSettings'
import { AppError } from '../src/services/common/errors'
import { parseTestBasisIds, parseBasisSeparators } from './sampleTestBases'
import { emptySampleCommission, sampleCommissionKeys, type SampleCommissionInfo } from '../src/types/commissions/sampleCommission'
import { emptySampleSubproject, sampleSubprojectFields, sampleSubprojectReceiptTypes, emptySampleDetails, sampleTextKeys, sampleDateKeys, sampleFlagKeys, type SampleFormOptions, type SampleFormDetails } from '../src/types/commissions/sampleForm'

const subprojectOptions = [
  { name: '空气过滤器检测', accountingDepartment: '环境控制检测部', businessCategory: '其他产品及设备检测' },
  { name: '通风设备检测', accountingDepartment: '通风设备检测部', businessCategory: '通风设备检测' },
  { name: '空调设备检测', accountingDepartment: '空调设备检测部', businessCategory: '空调设备检测' },
  { name: '洁净室检测', accountingDepartment: '洁净技术检测部', businessCategory: '洁净工程检测' },
  { name: '环境热工检测', accountingDepartment: '环境热工检测部', businessCategory: '环境热工检测' },
]

export function parseSampleDetails(input: unknown): SampleFormDetails {
  const result = emptySampleDetails()
  if (input === undefined) return result
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '样品资料格式有误。')
  const data = input as Record<string, unknown>
  result.reportSettings = parseReportSettings(data.reportSettings)
  if (data.testBasisIds !== undefined) result.testBasisIds = parseTestBasisIds(data.testBasisIds)
  result.testBasisSeparators = parseBasisSeparators(data.testBasisSeparators, result.testBasisIds.length)
  if (data.assessmentStandardIds !== undefined) result.assessmentStandardIds = parseTestBasisIds(data.assessmentStandardIds)
  result.assessmentStandardSeparators = parseBasisSeparators(data.assessmentStandardSeparators, result.assessmentStandardIds.length)
  for (const key of sampleTextKeys) {
    if (data[key] === undefined) continue
    if (typeof data[key] !== 'string' || data[key].length > (key === 'testBasis' || key === 'assessmentStandard' ? 20000 : 2000)) throw new AppError('VALIDATION', '请检查样品资料字段长度。')
    result[key] = data[key].trim()
  }
  if (result.reportForm && !['纸质', '电子'].includes(result.reportForm)) throw new AppError('VALIDATION', '报告形式只能选择纸质或电子。')
  for (const key of sampleFlagKeys) {
    if (data[key] === undefined) continue
    if (typeof data[key] !== 'boolean') throw new AppError('VALIDATION', '样品选项格式有误。')
    result[key] = data[key]
  }
  for (const key of sampleDateKeys) {
    const value = result[key]
    if (value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) throw new AppError('VALIDATION', '请填写有效的样品日期。')
  }
  for (const key of ['standardPrice', 'paidAmount', 'samplingQuantity', 'samplingBase', 'reportCopies'] as const) {
    if (result[key] && (!Number.isFinite(Number(result[key])) || Number(result[key]) < 0)) throw new AppError('VALIDATION', '数量和费用须为非负数。')
  }
  if (result.reportCopies && !Number.isInteger(Number(result.reportCopies))) throw new AppError('VALIDATION', '报告交付份数须为整数。')
  if (!result.useAssessmentStandard) {
    result.assessmentStandard = ''; result.assessmentStandardIds = []; result.assessmentStandardSeparators = []; result.assessmentEnglishBookMarks = false
  }
  if (!result.hasExternalDueDate) result.externalDueDate = ''
  if (!result.hasInternalDueDate) result.internalDueDate = ''
  if (!result.hasAppointment) result.appointmentDate = ''
  if (data.trademarkImage != null) {
    const image = data.trademarkImage as Record<string, unknown>
    if (!image || typeof image !== 'object' || typeof image.name !== 'string' || !image.name.trim() || image.name.length > 200 || typeof image.dataUrl !== 'string' || image.dataUrl.length > 2800000) throw new AppError('VALIDATION', '商标图片格式有误。')
    const match = /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})$/.exec(image.dataUrl)
    if (!match) throw new AppError('VALIDATION', '商标图片仅支持 PNG、JPEG、WebP。')
    const bytes = Buffer.from(match[2]!, 'base64')
    const valid = match[1] === 'png' ? bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) : match[1] === 'jpeg' ? bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255 : bytes.subarray(0, 4).toString() === 'RIFF' && bytes.subarray(8, 12).toString() === 'WEBP'
    if (!valid || bytes.length > 2 * 1024 * 1024) throw new AppError('VALIDATION', '请选择不超过 2 MB 的有效商标图片。')
    result.trademarkImage = { name: image.name.trim(), dataUrl: image.dataUrl }
  }
  if (data.subprojects !== undefined) {
    if (!Array.isArray(data.subprojects) || data.subprojects.length > 200) throw new AppError('VALIDATION', '子项目信息格式有误，最多 200 条。')
    const ids = new Set<string>()
    result.subprojects = data.subprojects.map(input => {
      if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '子项目信息格式有误。')
      const source = input as Record<string, unknown>, row = emptySampleSubproject()
      for (const key of ['id', ...sampleSubprojectFields.map(field => field.key)] as const) {
        const value = source[key]
        if (typeof value !== 'string' || value.length > (key === 'id' ? 100 : 500)) throw new AppError('VALIDATION', '请检查子项目字段格式和长度。')
        row[key] = value.trim()
      }
      if (!row.id || ids.has(row.id) || !row.name) throw new AppError('VALIDATION', '子项目名称不能为空，记录编号不能重复。')
      if (!subprojectOptions.some(option => option.name === row.name)) throw new AppError('VALIDATION', '请选择列表中的子项目名称。')
      ids.add(row.id)
      if (row.receiptType && !sampleSubprojectReceiptTypes.some(type => type === row.receiptType)) throw new AppError('VALIDATION', '请选择有效的子项目收款类型。')
      for (const value of [row.amount, row.receivedAmount]) if (value && !/^\d{1,12}(\.\d{1,2})?$/.test(value)) throw new AppError('VALIDATION', '子项目金额须为非负数，最多两位小数及 12 位整数。')
      return row
    })
  }
  return result
}

export function parseSampleCommission(input: unknown): SampleCommissionInfo {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new AppError('VALIDATION', '样品委托信息格式有误。')
  const source = input as Record<string, unknown>, result = emptySampleCommission()
  for (const key of [...sampleCommissionKeys, 'code', 'owner'] as const) {
    if (source[key] === undefined) continue
    if (typeof source[key] !== 'string' || source[key].length > 500) throw new AppError('VALIDATION', '请检查样品委托信息字段格式。')
    result[key] = source[key].trim()
  }
  return result
}

export function sampleFormOptions(departmentNames: string[]): SampleFormOptions {
  return { subprojectOptions: subprojectOptions.map(option => ({ ...option })), choices: {
    testingDepartment: departmentNames, testingLocation: ['实验室', '现场'],
    nameplate: ['有', '无'], appearance: ['正常', '异常'], inspector: ['演示用户', '赵样品'],
    taskRecipient: ['演示用户', '李受理'],
    taskSource: ['委托送样', '现场抽样'], paymentMethod: ['银行转账', '现金', '银行承兑汇票', '商业承兑汇票', '无追索权保理', '有追索权保理', '转账支票'], paymentStatus: ['委托时缴纳', '取报告时缴纳', '委托时已缴费合同额'],
    disposalMethod: ['客户取回', '中心处置', '委托中心托运'], reportDelivery: ['自取', '邮寄', '其他'], reportForm: ['纸质', '电子'],
    onsiteArrangement: ['正常', '客户指定', '联系后确认'],
  } }
}
