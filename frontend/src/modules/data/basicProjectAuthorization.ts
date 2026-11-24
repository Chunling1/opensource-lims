// Basic functions are department-scoped, not explicit project appointments.
export const BASIC_PROJECT_PERMISSIONS: Record<string, string> = {
  entrust_register: 'entrust.registration.view',
  sample_inbound: 'sample.inbound.view',
  sample_outbound: 'sample.outbound.view',
  report_print: 'report.print.view',
}

export function isDepartmentBasicRole(scope: string, role: string): boolean {
  return scope === 'department_project' && Object.prototype.hasOwnProperty.call(BASIC_PROJECT_PERMISSIONS, role)
}

export function basicRoleEnabled(codes: string[], role: string): boolean {
  return codes.includes(BASIC_PROJECT_PERMISSIONS[role] || '')
}

export function setBasicRoleEnabled(codes: string[], role: string, enabled: boolean, allowed: string[]): string[] {
  const code = BASIC_PROJECT_PERMISSIONS[role]
  if (!code || (enabled && !allowed.includes(code))) return [...codes]
  if (enabled) return codes.includes(code) ? [...codes] : [...codes, code]
  return codes.filter(item => item !== code)
}
