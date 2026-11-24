import { randomUUID } from 'node:crypto'
import { AppError } from '../src/services/common/errors'
import { emptyPersonnelProfile, personnelAttachmentKinds, type PersonnelProfile, type PersonnelHistory } from '../src/types/quality/personnel'
import type { DemoAttachment } from '../src/types/commissions/registration'
const invalid = (message: string, key?: string): never => { throw new AppError('VALIDATION', message, { fieldErrors: key ? { [key]: message } : undefined }) }
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : invalid('人员资料格式有误。')
function text(value: unknown, label: string, required = false, key?: string) {
  if (value === undefined) value = ''
  if (typeof value !== 'string' || value.length > 1000 || required && !value.trim()) return invalid(`请正确填写${label}。`, key)
  return value.trim()
}
export function parsePersonnelProfile(value: unknown): PersonnelProfile {
  if (value === undefined) return emptyPersonnelProfile()
  const input = object(value), profile = emptyPersonnelProfile()
  let total = 0, count = 0
  function attachments(value: unknown): DemoAttachment[] {
    if (value === undefined) return []
    if (!Array.isArray(value)) return invalid('附件格式有误。')
    return value.map(raw => {
      const file = object(raw), name = text(file.name, '附件名称', true), type = text(file.type, '附件类型')
      if (name.length > 255 || typeof file.size !== 'number' || !Number.isSafeInteger(file.size) || file.size < 0 || typeof file.dataUrl !== 'string') return invalid('附件格式有误。')
      const encoded = file.dataUrl.match(/^data:[^,]*;base64,([A-Za-z0-9+/]*={0,2})$/)?.[1]
      if (encoded === undefined || encoded.length % 4 !== 0 || Buffer.from(encoded, 'base64').length !== file.size) return invalid('附件内容或大小不正确。')
      total += file.size; count++
      if (total > 20 * 1024 * 1024 || count > 100) return invalid('人员资料附件总计不能超过 20 MB、100 个。')
      return { id: randomUUID(), name, type, size: file.size, dataUrl: file.dataUrl }
    })
  }
  for (const key of ['accountId', 'formerName', 'birthAddress', 'socialSecurityNumber', 'degree'] as const) profile[key] = text(input[key], '人员资料', false, key)
  const files = input.attachments === undefined ? {} : object(input.attachments)
  for (const f of personnelAttachmentKinds) profile.attachments[f.key] = attachments(files[f.key])
  for (const key of ['awards', 'trainings'] as const) {
    const records = input[key] ?? []
    if (!Array.isArray(records) || records.length > 200) return invalid('获奖或继续教育记录最多 200 条。')
    profile[key] = records.map(raw => {
      const row = object(raw), result: PersonnelHistory = { id: randomUUID(), date: '', name: '', project: '', issuer: '', place: '', content: '', result: '', attachments: attachments(row.attachments) }
      for (const f of ['date', 'name', 'project', 'issuer', 'place', 'content', 'result'] as const) result[f] = text(row[f], key === 'awards' ? '获奖信息' : '继续教育记录', f === 'date' || (key === 'awards' ? f === 'name' : f === 'content'))
      if (!/^\d{4}-\d{2}-\d{2}$/.test(result.date) || !Number.isFinite(Date.parse(result.date)) || new Date(result.date).toISOString().slice(0, 10) !== result.date) return invalid('获奖日期或培训时间须为有效日期。')
      return result
    })
  }
  return profile
}
