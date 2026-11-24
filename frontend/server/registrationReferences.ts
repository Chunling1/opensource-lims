import type { RegistrationContract, RegistrationOrganization } from '../src/types/commissions/commissionForm'
import { demoCustomers } from '../src/services/commissions/registrationService'

// Server-only catalogue: the browser requests one matching page at a time.
export const registrationOrganizations: (RegistrationOrganization & { departmentId: string })[] = Array.from({ length: 83 }, (_, i) => ({
  id: `organization-${i + 1}`,
  name: i < demoCustomers.length ? demoCustomers[i]! : `示范${['建设', '环境', '食品', '工程'][i % 4]}有限公司（${String(i + 1).padStart(3, '0')}）`,
  departmentId: i % 10 === 9 ? 'lab2' : 'lab',
}))

export const registrationContracts: RegistrationContract[] = Array.from({ length: 60 }, (_, i) => ({
  id: `contract-${i + 1}`, code: `20260918${String(i + 1).padStart(8, '0')}HT`,
  name: ['环境检测服务合同', '建设工程检测合同', '食品检测服务合同'][i % 3]! + `（${i + 1}）`,
  customer: demoCustomers[i % 3]!, departmentId: i % 10 === 9 ? 'lab2' : 'lab',
  erpContract: `KD2026${String(i + 1).padStart(4, '0')}`,
  erpProjectType: ['环境检测', '工程检测', '食品检测'][i % 3]!,
  signedDate: `2026-${String(Math.floor(i / 6) + 1).padStart(2, '0')}-${String(i % 6 + 1).padStart(2, '0')}`,
  projectName: ['园区环境监测工程', '综合楼建设工程', '食品生产基地工程'][i % 3]! + `（${i + 1}）`,
  projectAddress: `示范园区建设路 ${i + 1} 号`, constructionCompany: ['远景建设集团', '城建工程有限公司', '兴业建设有限公司'][i % 3]!,
  registrationStatus: '已登记',
}))
