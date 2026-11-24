export const CAPABILITY_SITE_FULL_ADDRESSES: Record<string, string[]> = {
  示例站点A: ['示例市科技园区一号院1号楼'],
  示例站点B: ['示例市东区实验大道2号'],
  示例站点C: ['示例园区实验楼 A 座'],
  示例站点D: ['示例市南区高新街7号5号楼', '示例市南区科研西路30号院'],
  示例站点E: ['示例市华南工业园西区12号'],
  示例站点F: ['示例市华北产业园兴业大街6号'],
  示例站点G: ['示例市华东检测基地166号'],
  示例站点H: ['示例市齐鲁产业园88号'],
  示例站点I: ['示例市海滨实验园2号'],
}

export function capabilitySiteForAddress(value: string): string {
  const normalized = String(value || '').trim()
  for (const [site, addresses] of Object.entries(CAPABILITY_SITE_FULL_ADDRESSES)) {
    if (site === normalized || addresses.includes(normalized)) return site
  }
  const rules: [string, string][] = [
    ['示例站点E', '示例站点E'], ['示例站点F', '示例站点F'], ['示例站点A', '示例站点A'], ['示例站点B', '示例站点B'],
    ['示例站点C', '示例站点C'], ['示例站点G', '示例站点G'], ['示例站点H', '示例站点H'], ['示例站点I', '示例站点I'], ['示例站点D', '示例站点D'],
  ]
  return rules.find(([token]) => normalized.includes(token))?.[1] || ''
}

export function commonCapabilitySites(siteGroups: string[][]): string[] {
  if (!siteGroups.length || siteGroups.some((sites) => !sites.length)) return []
  const normalized = siteGroups.map((sites) => [...new Set(
    sites.filter((site) => CAPABILITY_SITE_FULL_ADDRESSES[site]?.length),
  )])
  if (normalized.some((sites) => !sites.length)) return []
  return normalized.slice(1).reduce(
    (common, sites) => common.filter((site) => sites.includes(site)),
    normalized[0] || [],
  )
}

export function fullAddressesForSites(sites: string[]): string[] {
  return [...new Set(sites.flatMap((site) => CAPABILITY_SITE_FULL_ADDRESSES[site] || []))]
}
