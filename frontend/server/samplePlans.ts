import type { TestPlanNode } from '../src/types/commissions/sampleForm'

// The catalogue stays on the mock server; expand and search requests return one page.
const groups = [
  ['thermal', '空调设备检测部（热湿）', '热湿性能检测', 'RS'],
  ['ventilation', '空调设备检测部（通风）', '通风设备性能检测', 'TF'],
  ['clean', '空调设备检测部（净化）', '净化设备性能检测', 'JH'],
  ['engineering', '空调设备检测部（空调工程）', '空调工程检测', 'GC'],
  ['pressure', '风速、压力校准实验室', '风量罩校准|压力校准|风速仪校准', 'FZ|SY|FS'],
  ['enthalpy', '焓差实验室校准', '焓差实验室校准', 'HC'],
  ['temperature', '温度校准实验室', '温度计校准', 'WD'],
  ['general', '综合检测部', '常规检测方案|工程材料检测方案|产品质量检测方案', 'CG|CL|CP'],
  ['branch', '第二检测部', '专项检测方案', 'ZX'],
]
export const testPlanGroups: (TestPlanNode & { departmentId: string })[] = groups.map(([id, name]) => ({ id: id!, name: name!, kind: 'group', code: '', groupName: '', departmentId: id === 'branch' ? 'lab2' : 'lab' }))
export const testPlans = groups.flatMap(([groupId, groupName, names, codes]) => {
  const titles = names!.split('|'), identifiers = codes!.split('|')
  const count = groupId === 'temperature' ? 26 : titles.length
  return Array.from({ length: count }, (_, index) => ({
    id: `${groupId}-${index + 1}`, parentId: groupId!, groupName: groupName!, kind: 'plan' as const,
    name: titles[index % titles.length]! + (groupId === 'temperature' ? `（${index + 1}）` : ''),
    code: identifiers[index % identifiers.length]! + (groupId === 'temperature' ? String(index + 1).padStart(3, '0') : ''),
    departmentId: groupId === 'branch' ? 'lab2' : 'lab',
  }))
})
export function publicTestPlan({ id, name, kind, code, groupName, parentId }: TestPlanNode): TestPlanNode { return { id, name, kind, code, groupName, ...(parentId ? { parentId } : {}) } }
