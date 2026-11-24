import { AppError } from '../src/services/common/errors'
import { demoActors } from '../src/services/storage/demoActors'
import { registrationDepartments } from '../src/types/commissions/commissionForm'
import type { RegistrationSample } from '../src/types/commissions/registration'
import type { Actor } from '../src/types/lims'
import type { EntryPeoplePage, EntryPersonCandidate, EntryPersonRole, EntryPeopleScope } from '../src/types/testing/dataEntryDetail'
import { entryPresetIds } from './autoAssignment'

const departmentName = (id: string) => registrationDepartments.find(row => row.id === id)?.name || id
export function entryPeople(role: EntryPersonRole, people: readonly Actor[] = demoActors): EntryPersonCandidate[] {
  const requiredRole = role === 'tester' ? 'testing' : role
  return people.filter(person => person.active !== false && person.roles.some(value => value === 'admin' || value === requiredRole))
    .map(person => ({ id: person.id, name: person.name, departmentId: person.departmentId, departmentName: departmentName(person.departmentId), certificateNumber: person.certificateNumber || '', phone: person.phone || '' }))
}
function roleValue(value: unknown): EntryPersonRole {
  if (typeof value !== 'string' || !['tester', 'reviewer', 'approver'].includes(value)) throw new AppError('BAD_REQUEST', '人员角色有误。')
  return value as EntryPersonRole
}
function text(value: unknown, limit: number) {
  if (value === undefined) return ''
  if (typeof value !== 'string' || value.length > limit) throw new AppError('BAD_REQUEST', '人员查询条件有误。')
  return value.trim()
}
export function queryEntryPeople(sample: RegistrationSample, actor: Actor, input: Record<string, unknown>, people: readonly Actor[] = demoActors, presetIds?: string[]): EntryPeoplePage {
  const role = roleValue(input.role), presets = presetIds ?? entryPresetIds(sample.details?.testPlanId || '', role)
  const presetConfigured = presets.length > 0, scope = input.scope ?? (presetConfigured ? 'preset' : 'department')
  if (typeof scope !== 'string' || !['preset', 'department', 'all'].includes(scope)) throw new AppError('BAD_REQUEST', '人员范围有误。')
  const keyword = text(input.keyword, 200).toLocaleLowerCase(), excludeId = text(input.excludeId, 100)
  const requestedPage = input.page ?? 1, pageSize = input.pageSize ?? 10
  if (!Number.isSafeInteger(requestedPage) || Number(requestedPage) < 1 || ![10, 20, 50].includes(Number(pageSize)) || typeof pageSize !== 'number') throw new AppError('BAD_REQUEST', '人员分页参数有误。')
  const rows = entryPeople(role, people).filter(person => (scope === 'all' || scope === 'department' && person.departmentId === actor.departmentId || scope === 'preset' && presets.includes(person.id))
    && (!keyword || person.name.toLocaleLowerCase().includes(keyword) || person.id.toLocaleLowerCase().includes(keyword)))
    .sort((a, b) => a.id.localeCompare(b.id, 'zh-CN', { numeric: true }))
    .map(person => ({ ...person, ...(role === 'tester' && person.id === excludeId ? { disabledReason: '已选为另一位试验人' } : {}) }))
  const total = rows.length, page = Math.min(Number(requestedPage), Math.max(1, Math.ceil(total / Number(pageSize))))
  return { items: rows.slice((page - 1) * Number(pageSize), page * Number(pageSize)), total, page, pageSize: Number(pageSize), scope: scope as EntryPeopleScope, presetConfigured, departmentName: departmentName(actor.departmentId) }
}
export function resolveEntryPerson(input: Record<string, unknown>): EntryPersonCandidate {
  const role = roleValue(input.role), id = text(input.id, 100), excludeId = text(input.excludeId, 100)
  const person = entryPeople(role).find(row => row.id === id)
  if (!person) throw new AppError('VALIDATION', '人员已不可选，请重新查询。')
  if (role === 'tester' && person.id === excludeId) throw new AppError('VALIDATION', '两位试验人不能重复。')
  return person
}
