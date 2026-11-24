export interface EnvironmentPlan { id: string; name: string; code: string }
export interface TestEnvironment { id: string; name: string; departmentId: string; planIds: string[]; version: number }
export interface EnvironmentDetail extends TestEnvironment { plans: EnvironmentPlan[] }
export interface EnvironmentQuery { name?: string; page?: number; pageSize?: number; ids?: string[] }
export interface EnvironmentPage { items: TestEnvironment[]; total: number; page: number; pageSize: number }
export const environmentColumns = [{ key: 'name', label: '试验环境', required: true, wrap: true }] as const
export const environmentPlanColumns = [{ key: 'name', label: '检测方案', wrap: true }, { key: 'code', label: '方案代码' }] as const
