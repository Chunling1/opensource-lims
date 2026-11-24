import type { SampleCommissionInfo } from './sampleCommission'
export interface BulkCommissionTarget { id: string; version: number }
export interface BulkCommissionContext {
  commissionId: string; commissionCode: string
  items: (BulkCommissionTarget & { code: string; commissionInfo: SampleCommissionInfo })[]
}
export interface BulkCommissionResult { items: BulkCommissionTarget[]; count: number }
