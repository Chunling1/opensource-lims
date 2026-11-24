// Exact, reviewed aliases only. Never merge arbitrary sites by district/city.
export function parameterAddressKey(address: string): string {
  const key = address.replace(/\s+/g, '')
  return key === '示例市华北产业园兴业大街6号' ? '示例市华北产业园兴业大街6号' : key
}
export function parameterAddresses(rows: { address?: string; itemName: string }[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const row of rows) {
    const address = (row.address || '').trim()
    if (!address) continue
    const key = parameterAddressKey(address)
    if (!seen.has(key)) { seen.add(key); result.push(key) }
  }
  return result
}

export type ManualParameterLocation = { mode: 'library' | 'selected'; addresses: string[] }
export type ManualParameterLocations = Record<string, ManualParameterLocation>

export function actualParameterAddresses(rows: { address?: string; itemName: string }[], context: {
  isOnsiteTesting: boolean; onsiteTestLocation: string; manualCapabilityItems: string[]; manualTestLocation: string;
  manualParameterLocations?: ManualParameterLocations | null;
}, strict = true): string[] {
  if (context.isOnsiteTesting) return [context.onsiteTestLocation.trim()].filter(Boolean)
  const source = parameterAddresses(rows)
  if (!context.manualCapabilityItems.length) return source
  if (context.manualParameterLocations != null) {
    const addresses = [...source]
    for (const name of context.manualCapabilityItems) {
      const choice = context.manualParameterLocations[name]
      if (choice?.mode === 'library' && source.length) continue
      if (choice?.mode === 'selected' && choice.addresses?.length) {
        addresses.push(...parameterAddresses(choice.addresses.map(address => ({ address, itemName: name }))))
      } else if (strict) {
        throw new Error(`「${name}」${choice?.mode === 'library' ? '需先选择有地点的库内参数，或单独选择地点' : '请选择库外检测地点'}`)
      }
    }
    return parameterAddresses(addresses.map(address => ({ address, itemName: '' })))
  }
  if (!strict && !context.manualTestLocation.trim()) return source
  if (!context.manualTestLocation.trim()) throw new Error('请填写库外项目完整检测地址')
  return parameterAddresses([...source.map(address => ({ address, itemName: '' })),
    { address: context.manualTestLocation, itemName: '库外项目' }])
}
