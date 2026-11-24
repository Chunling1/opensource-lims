import { demoActors } from '../src/services/storage/demoActors'
import { AppError } from '../src/services/common/errors'
import type { RegistrationSample } from '../src/types/commissions/registration'
import { parseAssignmentSubmission } from './testingAssignment'

export interface AssignmentRule { revision: number; dataEntryPerson?: string; tester1?: string; tester2?: string; reviewerIds?: string[]; approverIds?: string[] }
// Demo-only presets. Personnel configuration UI is a separate feature.
const demoRules: Record<string, AssignmentRule> = { 'general-1': { revision: 1, dataEntryPerson: 'analyst', tester1: 'analyst' } }
export function entryPresetIds(planId: string, role: 'tester' | 'reviewer' | 'approver'): string[] {
  const rule = demoRules[planId]
  return rule ? role === 'tester' ? [...new Set([rule.tester1, rule.tester2].filter((id): id is string => !!id))] : role === 'reviewer' ? rule.reviewerIds || [] : rule.approverIds || [] : []
}
type Person = { id: string; name: string }
export function createAutoAssignment(rules: () => Record<string, AssignmentRule> = () => demoRules, people: () => readonly Person[] = () => demoActors) {
  return {
    resolve(sample: RegistrationSample, actor: Person, date: string) {
      const planId = sample.details?.testPlanId || '', rule = rules()[planId], personnel = people()
      const issues: string[] = []
      if (!planId) issues.push('该样品未设置检测方案，请手动分配。')
      else if (!rule) issues.push('该检测方案尚未配置自动分配人员，请手动分配。')
      else {
        for (const [key, label] of [['dataEntryPerson', '数据录入人'], ['tester1', '检测人1'], ['tester2', '检测人2']] as const) {
          const id = rule[key]
          if (id && !personnel.some(person => person.id === id)) issues.push(`预设${label}已不存在，请手动分配。`)
          else if (!id && key !== 'tester2') issues.push(`该检测方案未配置${label}，请手动分配。`)
        }
        if (rule.tester1 && rule.tester1 === rule.tester2) issues.push('预设检测人1与检测人2重复，请手动分配。')
      }
      if (issues.length) throw new AppError('VALIDATION', issues.join(''))
      return parseAssignmentSubmission({ account: actor.id, name: actor.name, dataEntryPerson: rule!.dataEntryPerson, tester1: rule!.tester1, tester2: rule!.tester2 || '', date }, personnel)
    },
  }
}
