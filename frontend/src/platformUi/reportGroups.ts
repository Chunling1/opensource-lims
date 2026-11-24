import config from './reportGroups.json'

export const reportGroupOptions = config.groups.map(group => group.value).concat('未归组')
export function isAcDepartment(value: unknown): boolean {
  const name = String(value || '').trim()
  return name === config.department || config.departmentAliases.includes(name) || name.startsWith(config.department + '-')
}
export function reportGroupChoices(session: any): {value: string; label: string}[] {
  const department = String(session?.dataScope?.department || '').trim()
  const all = session?.dataScope?.scopeType === 'all' || !!session?.fullPlatformAuthority || !!session?.canCorrectBusinessData
  const ac = isAcDepartment(department)
  const choices = [{value:'',label:ac ? config.department : all ? '全部部门' : department || '当前部门'}]
  if (all && !ac) choices.push({value:'__ac_department__',label:config.department})
  if (ac || all) choices.push(...reportGroupOptions.map(value=>({value,label:value})))
  return choices
}
export function matchesReportGroup(row: Record<string, any>, group: unknown): boolean {
  if (!group) return true
  const source = row.source || row
  if (!isAcDepartment(source.department)) return false
  if (group === '__ac_department__') return true
  const number = String(source.reportNo || row.reportCode || '').trim().toUpperCase().replaceAll('（', '(').replaceAll('）', ')').replaceAll('Ⅱ', 'II').replaceAll('Ⅰ', 'I').replaceAll('Ⅲ', 'III')
  const match = /^(?:[A-Z]+-)?[0-9]{4}(.+?)-[0-9]+(?:$|[-(（])/.exec(number)
  const actual = config.groups.find(item => item.codes.includes(match?.[1] || ''))?.value || '未归组'
  return actual === group
}
