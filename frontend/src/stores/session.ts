import { AppError } from '../services/common/errors'
import { computed, shallowRef } from 'vue'
import { profile, refreshProfile } from '../services/platform/auth'
import type { Actor, BusinessRecord, LimsDatabase } from '../types/lims'
import { moduleMap } from '../services/business/modules'
import { canApplyDailyRequests, canApproveDailyRequests } from '../types/quality/dailyRequests'
export const currentActor = shallowRef<Actor>({ id: '', name: '', roles: [], departmentId: '', scope: 'department' })
export const authenticated = computed(() => !!profile.value)
export const sessionLocked = shallowRef(false)
export const roleLabels: Record<string, string> = { admin: '管理员', commissions: '业务受理', samples: '样品管理', testing: '检测', reviewer: '审核', approver: '批准', reports: '报告管理', finance: '财务', quality: '质量管理', system: '系统管理' }
export async function identities() { return profile.value ? [{ id: profile.value.account, name: profile.value.userName }] : [] }
export async function refreshIdentity(strict = false, useLoadedProfile = false) {
  try {
    // App mounts only after PlatformSession has refreshed the current login.
    // Explicit/focus/permission refreshes retain the default network read.
    const value = useLoadedProfile && profile.value ? profile.value : await refreshProfile()
    const groups: Record<string, string> = { entrust: 'commissions', sample: 'samples', report: 'reports', testing: 'testing', finance: 'finance', quality: 'quality', system: 'system' }
    const roles = [...new Set(value.permissions.map(code => groups[code.split('.')[0]!] || '').filter(Boolean))]
    const roleMap: Record<string, string> = { admin: 'admin', reviewer: 'reviewer', approver: 'approver' }
    if (roleMap[value.roleKey]) roles.push(roleMap[value.roleKey]!)
    currentActor.value = { ...value.personal, id: value.account, name: value.userName, roles, departmentId: value.dataScope.department, scope: value.dataScope.scopeType === 'all' ? 'all' : 'department' }
  } catch (e) { if (strict) throw e }
}
export function resolveActor(_state: LimsDatabase, id: string): Actor {
  if (id !== currentActor.value.id || !id) throw new AppError('UNAUTHORIZED', '请重新登录平台。')
  return currentActor.value
}
export async function switchIdentity(_id: string) { throw new AppError('FORBIDDEN', '平台账号不能切换演示身份，请退出后重新登录。') }
export const hasRole = (actor: Actor, roles: string[]) => actor.roles.includes('admin') || roles.some(r => actor.roles.includes(r))
export function canRead(actor: Actor, kind: string) {
  if (kind === 'dailyRequests') return canApplyDailyRequests(actor)
  if (kind === 'dailyApprovals') return canApproveDailyRequests(actor)
  const group = moduleMap[kind]?.group
  if (['customers', 'projects', 'methods', 'departments', 'sites', 'locations'].includes(kind) && actor.roles.length) return true
  if (['commissions', 'outsourcing'].includes(kind) && hasRole(actor, ['finance', 'testing', 'sampling', 'samples', 'reports'])) return true
  return hasRole(actor, moduleMap[kind]?.roles ?? [group ?? kind]) || (['reviewer', 'approver'].some(r => actor.roles.includes(r)) && !['users', 'settings', 'approvalConfigs'].includes(kind))
}
export function inScope(actor: Actor, entity: Pick<BusinessRecord, 'departmentId'>) { return actor.scope === 'all' || actor.departmentId === entity.departmentId }
export function assertScope(actor: Actor, entity: Pick<BusinessRecord, 'departmentId'>) { if (!inScope(actor, entity)) throw new AppError('FORBIDDEN', '无权访问其他部门的数据。') }
export function assertRole(actor: Actor, roles: string[]) { if (!hasRole(actor, roles)) throw new AppError('FORBIDDEN', '当前身份没有执行此操作的权限。') }
