import { randomBytes, randomUUID, scryptSync } from 'node:crypto'
import { AppError, problem } from '../src/services/common/errors'
import type { RegistrationDependencies } from '../src/types/commissions/registration'
import { canManageCustomerAccounts, customerAccountColumns, emptyCustomerAccount, type CustomerAccount, type CustomerAccountDetail } from '../src/types/customers/accounts'
import { registrationCsv } from './registrationDomain'
import { registrationContracts } from './registrationReferences'

export function createCustomerAccounts(deps: RegistrationDependencies) {
  const read = () => deps.read!()!
  function actor(write = false) {
    const user = deps.actor()
    if (deps.locked?.() || !user.roles.length || write && !canManageCustomerAccounts(user)) throw new AppError('FORBIDDEN', '无权执行客户账号操作。')
    return user
  }
  const visible = (row: CustomerAccount) => { const user = actor(); return user.scope === 'all' || row.departmentId === user.departmentId }
  function detail(id: unknown): CustomerAccountDetail {
    actor(); const row = read().customerAccounts?.find(row => row.id === id)
    if (!row || !visible(row)) throw new AppError('NOT_FOUND', '客户账号不存在或无权访问。')
    return { ...row, contracts: registrationContracts.filter(contract => row.contractIds.includes(contract.id)) }
  }
  function query(input: Record<string, unknown>, all = false) {
    actor()
    for (const field of ['code', 'name']) if (input[field] !== undefined && (typeof input[field] !== 'string' || (input[field] as string).length > 200)) throw new AppError('VALIDATION', '查询条件有误。')
    const pageSize = input.pageSize ?? 10, requested = input.page ?? 1
    if (typeof pageSize !== 'number' || ![10, 20, 50].includes(pageSize) || !Number.isSafeInteger(requested) || Number(requested) < 1) throw new AppError('VALIDATION', '分页参数有误。')
    if (input.ids !== undefined && (!Array.isArray(input.ids) || input.ids.length > 1000 || input.ids.some(id => typeof id !== 'string' || !id || id.length > 100) || new Set(input.ids).size !== input.ids.length)) throw new AppError('VALIDATION', '所选账号有误。')
    const ids = input.ids as string[] | undefined
    const items = (read().customerAccounts || []).filter(visible).filter(row => (!ids || ids.includes(row.id)) && ['code', 'name'].every(field => row[field as 'code' | 'name'].toLocaleLowerCase().includes(String(input[field] || '').trim().toLocaleLowerCase())))
    const page = Math.min(Number(requested), Math.max(1, Math.ceil(items.length / pageSize)))
    return { items: all ? items : items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, pageSize }
  }
  function save(input: Record<string, unknown>) {
    const user = actor(true), previous = input.id === undefined ? undefined : detail(input.id), draft = emptyCustomerAccount()
    for (const field of ['name', 'postcode', 'address', 'contact', 'mobile', 'phone', 'fax', 'email', 'notes'] as const) {
      const value = input[field], max = field === 'notes' ? 2000 : field === 'address' ? 500 : 200
      if (typeof value !== 'string' || value.length > max) throw problem('VALIDATION', `字段内容不能超过 ${max} 个字符。`, field)
      draft[field] = value.trim()
    }
    if (!draft.name) throw problem('VALIDATION', '请填写客户名称。', 'name')
    if (draft.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.email)) throw problem('VALIDATION', '请填写有效的电子邮箱。', 'email')
    if (draft.postcode && !/^\d{6}$/.test(draft.postcode)) throw problem('VALIDATION', '邮政编码应为六位数字。', 'postcode')
    if (!Array.isArray(input.contractIds) || input.contractIds.length > 1000 || input.contractIds.some(id => typeof id !== 'string') || new Set(input.contractIds).size !== input.contractIds.length) throw problem('VALIDATION', '关联合同参数有误。', 'contractIds')
    const departmentId = previous?.departmentId || user.departmentId
    for (const id of input.contractIds) {
      const contract = registrationContracts.find(contract => contract.id === id)
      if (!contract || user.scope !== 'all' && contract.departmentId !== user.departmentId && !previous?.contractIds.includes(id)) throw problem('VALIDATION', '请选择权限范围内的有效合同。', 'contractIds')
    }
    draft.contractIds = input.contractIds as string[]
    const state = structuredClone(read()), accounts = state.customerAccounts ||= []
    const nextCode = Math.max(0, ...accounts.map(row => Number(row.code.slice(2)) || 0)) + 1
    const saved: CustomerAccount = { ...draft, id: previous?.id || randomUUID(), code: previous?.code || `KH${String(nextCode).padStart(6, '0')}`, departmentId }
    if (previous) accounts[accounts.findIndex(row => row.id === previous.id)] = saved; else accounts.push(saved)
    deps.write!(state); return detail(saved.id)
  }
  function resetPassword(input: Record<string, unknown>) {
    const user = actor(true), row = detail(input.id), password = `Aa1!${randomBytes(12).toString('base64url')}`, salt = randomBytes(16).toString('hex')
    const state = structuredClone(read())
    ;(state.customerCredentials ||= {})[row.id] = { salt, hash: scryptSync(password, salt, 64).toString('hex'), mustChangePassword: true, resetAt: new Date().toISOString(), resetBy: user.id }
    deps.write!(state)
    return { code: row.code, password, mustChangePassword: true }
  }
  return { query, detail, save, resetPassword, export: (input: Record<string, unknown>) => registrationCsv([customerAccountColumns.map(column => column.label), ...query(input, true).items.map(row => customerAccountColumns.map(column => row[column.key]))]) }
}
