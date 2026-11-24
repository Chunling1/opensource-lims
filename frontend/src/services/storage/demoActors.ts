import type { Actor } from '../../types/lims'
export const demoActors: Actor[] = [
  { id: 'admin', name: '演示用户', roles: ['admin'], departmentId: 'lab', scope: 'all' },
  { id: 'business', name: '张受理', roles: ['commissions', 'samples', 'sampling'], departmentId: 'lab', scope: 'department' },
  { id: 'analyst', name: '李检测', roles: ['testing', 'samples'], departmentId: 'lab', scope: 'department' },
  { id: 'reviewer', name: '王复核', roles: ['reviewer', 'testing', 'reports', 'quality'], departmentId: 'lab', scope: 'all' },
  { id: 'approver', name: '陈批准', roles: ['approver', 'reports', 'quality'], departmentId: 'lab', scope: 'all' },
  { id: 'finance', name: '赵财务', roles: ['finance'], departmentId: 'lab', scope: 'all' },
  { id: 'quality', name: '刘质量', roles: ['quality'], departmentId: 'lab', scope: 'all' },
  { id: 'sampler', name: '孙采样', roles: ['sampling', 'samples'], departmentId: 'lab', scope: 'department' },
  { id: 'equipment', name: '郑设备', roles: ['equipment'], departmentId: 'lab', scope: 'department' },
  { id: 'inventory', name: '吴物资', roles: ['inventory'], departmentId: 'lab', scope: 'department' },
  { id: 'other', name: '第二实验室检测员', roles: ['testing', 'samples'], departmentId: 'lab2', scope: 'department' },
]
