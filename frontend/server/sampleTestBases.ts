import { AppError } from '../src/services/common/errors'
import type { Actor } from '../src/types/lims'
import { maxTestBasisSelection, type TestBasisStandard, type TestBasisQuery, type TestBasisPage, type TestBasisSelection } from '../src/types/commissions/testBasis'
import { basisLabel, joinBasisText, validBasisSeparator } from '../src/services/commissions/testBasisText'
import { testPlans } from './samplePlans'

// Fictional standards for UI development, associated with individual mock plans.
const standards = testPlans.flatMap(plan => Array.from({ length: 32 }, (_, i) => ({
  id: `${plan.id}-basis-${i + 1}`, planId: plan.id,
  departmentId: i % 8 === 7 ? 'lab2' : plan.departmentId,
  departmentCategory: i % 2 ? '检测类' : '校准类',
  controlNumber: `SK-${plan.code}-${String(i + 1).padStart(3, '0')}`,
  qualification: ['一单一库+CNAS+CMA', 'CNAS', 'CMA'][i % 3]!,
  code: `STD-${plan.code}-${String(i + 1).padStart(3, '0')}-2026`,
  name: `${plan.name}技术规范（${i + 1}）`,
  category: ['CNAS、CMA授权', 'CNAS授权', 'CMA授权'][i % 3]!,
  location: i % 2 ? '标准资料室' : '示例站点B',
  implementedDate: `2026-${String(i % 9 + 1).padStart(2, '0')}-01`,
  revokedDate: i % 11 === 10 ? '2026-08-01' : '',
  extensionDays: i % 7 === 6 ? 30 : null,
  replacementCode: i % 11 === 10 ? `STD-${plan.code}-${String(i + 2).padStart(3, '0')}-2026` : '',
  notes: i % 3 === 0 ? '此标准为非一单一库标准' : '',
})))
function accessible(actor: Actor, row: { departmentId: string }) { return actor.scope === 'all' || row.departmentId === actor.departmentId }
function planStandards(actor: Actor, planId: string) {
  if (!planId) throw new AppError('VALIDATION', '请先选择检测方案。')
  if (!testPlans.some(plan => plan.id === planId && accessible(actor, plan))) throw new AppError('NOT_FOUND', '检测方案不存在或已不可访问。')
  return standards.filter(row => row.planId === planId && accessible(actor, row))
}
function publicStandard(row: typeof standards[number]): TestBasisStandard {
  const { id, controlNumber, qualification, code, name, category, location, implementedDate, revokedDate, extensionDays, replacementCode, notes } = row
  return { id, controlNumber, qualification, code, name, category, location, implementedDate, revokedDate, extensionDays, replacementCode, notes }
}
export function parseTestBasisIds(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > maxTestBasisSelection || value.some(id => typeof id !== 'string' || !id || id.length > 100)) throw new AppError('VALIDATION', `请选择最多 ${maxTestBasisSelection} 项有效检测依据。`)
  return [...new Set(value)] as string[]
}
export function queryTestBases(actor: Actor, query: TestBasisQuery): TestBasisPage {
  const available = planStandards(actor, query.planId)
  const departmentCategories = [...new Set(available.map(row => row.departmentCategory))]
  const qualifications = [...new Set(available.map(row => row.qualification).filter(Boolean))]
  const [sort, direction] = (query.sort || 'code:asc').split(':') as [keyof TestBasisStandard, string]
  const matches = available.filter(row => {
    if (query.ownDepartment && row.departmentId !== actor.departmentId || query.departmentCategory && row.departmentCategory !== query.departmentCategory || query.ids && !query.ids.includes(row.id)) return false
    return (['code', 'name', 'category', 'qualification', 'controlNumber'] as const).every(key => !query[key] || row[key].toLocaleLowerCase().includes(query[key]!.trim().toLocaleLowerCase()))
  }).sort((a, b) => (String(a[sort]).localeCompare(String(b[sort]), 'zh-CN', { numeric: true }) || a.id.localeCompare(b.id)) * (direction === 'desc' ? -1 : 1))
  const pageSize = query.pageSize || 10, page = Math.max(1, Math.min(query.page || 1, Math.ceil(matches.length / pageSize) || 1))
  return { items: matches.slice((page - 1) * pageSize, page * pageSize).map(publicStandard), total: matches.length, page, pageSize, departmentCategories, qualifications }
}
export function resolveTestBases(actor: Actor, planId: string, ids: string[], englishBookMarks = false, separatorInput?: unknown): TestBasisSelection {
  const available = planStandards(actor, planId), selected = parseTestBasisIds(ids).map(id => available.find(row => row.id === id))
  if (selected.some(row => !row)) throw new AppError('VALIDATION', '部分检测依据不属于当前方案或已不可访问，请重新选择。')
  const separators = parseBasisSeparators(separatorInput, selected.length)
  const text = joinBasisText(selected.map(row => basisLabel(row!, englishBookMarks)), separators)
  return { ids: selected.map(row => row!.id), text, englishBookMarks, separators }
}

export function parseBasisSeparators(input: unknown, count: number): string[] {
  const length = Math.max(0, count - 1)
  if (input === undefined) return Array.from({ length }, () => '；')
  if (!Array.isArray(input) || input.length !== length || input.some(value => !validBasisSeparator(value))) throw new AppError('VALIDATION', '每两项检测依据之间须填写 1 至 2 个分隔符号、空格或换行，依据内容请从列表选择。')
  return [...input] as string[]
}
