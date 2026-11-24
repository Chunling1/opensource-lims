export function organizationNames(value: string): string[] {
  return [...new Set(value.split(/[；;\r\n]+/).map(name => name.trim()).filter(Boolean))]
}
