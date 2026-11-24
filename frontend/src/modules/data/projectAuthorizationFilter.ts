export interface ProjectFilter { codes: string[]; departments: string[]; locations: string[] }
export interface FilterableProject { id: number; code: string; name: string; department: string; location?: string | null }
export const emptyProjectFilter = (): ProjectFilter => ({ codes: [], departments: [], locations: [] })
export function filterAuthorizationProjects<T extends FilterableProject>(projects: T[], filter: ProjectFilter, keyword = ''): T[] {
  const text = keyword.trim().toLowerCase()
  return projects.filter(p => (!filter.codes.length || filter.codes.includes(p.code))
    && (!filter.departments.length || filter.departments.includes(p.department))
    && (!filter.locations.length || filter.locations.includes(p.location || ''))
    && (!text || `${p.code} ${p.name} ${p.department} ${p.location || ''}`.toLowerCase().includes(text)))
}
export function selectFilteredIds(current: number[], filtered: number[], checked: boolean): number[] {
  const visible = new Set(filtered)
  return checked ? [...new Set([...current, ...visible])] : current.filter(id => !visible.has(id))
}
export function templateFunctionUnion(current: string[], templates: { permissionCodes: string[] }[], allowed: string[]): string[] {
  const ceiling = new Set(allowed)
  return [...new Set([...current, ...templates.flatMap(t => t.permissionCodes)])].filter(code => ceiling.has(code)).sort()
}
