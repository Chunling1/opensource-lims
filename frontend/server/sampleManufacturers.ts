import type { Manufacturer } from '../src/types/commissions/manufacturer'

// Mock catalogue owned by the backend; manufacturer types are supplied with query results.
export const manufacturers: (Manufacturer & { departmentId: string })[] = Array.from({ length: 37 }, (_, index) => {
  const type = ['空调', '通风', '净化'][index % 3]!
  const number = String(index + 1).padStart(3, '0')
  return { id: `manufacturer-${index + 1}`, code: `CJ${number}`, name: `示范${type}设备有限公司（${number}）`, type, departmentId: index % 10 === 9 ? 'lab2' : 'lab' }
})
